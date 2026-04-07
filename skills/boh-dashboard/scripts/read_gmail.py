#!/usr/bin/env python3
"""
read_gmail.py — Read a user's Gmail inbox on behalf of Hazel

Usage:
  python3 read_gmail.py list [--max 10] [--query "from:someone"] [--user-id <uuid>] [--email <addr>]
  python3 read_gmail.py get <message_id> [--user-id <uuid>] [--email <addr>]
  python3 read_gmail.py search "invoice OR bid" [--max 10] [--user-id <uuid>] [--email <addr>]

Reads from gmail_tokens table using stored OAuth token.
Tokens are per-user — pass --user-id or --email to identify which inbox.
Falls back to first available token if neither is specified.
"""
import argparse, base64, json, os, sys, requests
from datetime import datetime, timezone, timedelta

SUPABASE_URL = "https://zrolyrtaaaiauigrvusl.supabase.co"
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
GMAIL_CLIENT_ID     = os.getenv("GMAIL_CLIENT_ID", "")
GMAIL_CLIENT_SECRET = os.getenv("GMAIL_CLIENT_SECRET", "")

SB = {}  # populated after env load


def decode_token(ciphertext):
    if not ciphertext:
        return ""
    try:
        return base64.b64decode(ciphertext.encode()).decode()
    except Exception:
        return ciphertext


def encode_token(plaintext):
    return base64.b64encode(plaintext.encode()).decode()


def get_token_row(user_id=None, email=None):
    params = {
        "select": "firm_id,user_id,email,access_token,refresh_token,expiry",
        "limit": "1",
    }
    if user_id:
        params["user_id"] = f"eq.{user_id}"
    elif email:
        params["email"] = f"eq.{email}"

    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/gmail_tokens",
        headers=SB,
        params=params,
        timeout=10,
    )
    if not r.ok or not r.json():
        who = email or user_id or "any user"
        print(f"ERROR: No Gmail token found for {who}. Connect Gmail in the dashboard Settings tab.", file=sys.stderr)
        sys.exit(1)
    return r.json()[0]


def refresh_access_token(row):
    refresh_token = decode_token(row.get("refresh_token", ""))
    if not refresh_token:
        print("ERROR: No refresh token available.", file=sys.stderr)
        sys.exit(1)
    r = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": GMAIL_CLIENT_ID,
            "client_secret": GMAIL_CLIENT_SECRET,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=10,
    )
    if not r.ok:
        print(f"ERROR: Token refresh failed: {r.text[:200]}", file=sys.stderr)
        sys.exit(1)
    tokens = r.json()
    new_access = tokens["access_token"]
    expires_in = tokens.get("expires_in", 3600)
    new_expiry = (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat()
    # Update by email (unique per user) to avoid firm_id ambiguity
    patch_params = {"email": f"eq.{row['email']}"} if row.get("email") else {"firm_id": f"eq.{row['firm_id']}", "user_id": f"eq.{row['user_id']}"}
    requests.patch(
        f"{SUPABASE_URL}/rest/v1/gmail_tokens",
        headers={**SB, "Content-Type": "application/json"},
        params=patch_params,
        json={"access_token": encode_token(new_access), "expiry": new_expiry},
        timeout=5,
    )
    return new_access


def get_access_token(user_id=None, email=None):
    row = get_token_row(user_id=user_id, email=email)
    expiry_str = row.get("expiry", "")
    try:
        expiry = datetime.fromisoformat(expiry_str)
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) >= expiry - timedelta(minutes=5):
            return refresh_access_token(row)
    except Exception:
        pass
    return decode_token(row.get("access_token", ""))


def parse_message(msg):
    headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}

    def extract_body(part):
        if part.get("mimeType") == "text/plain":
            data = part.get("body", {}).get("data", "")
            if data:
                return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
        for subpart in part.get("parts", []):
            result = extract_body(subpart)
            if result:
                return result
        return ""

    payload = msg.get("payload", {})
    body = extract_body(payload)
    if not body:
        data = payload.get("body", {}).get("data", "")
        if data:
            body = base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")

    return {
        "id": msg.get("id"),
        "thread_id": msg.get("threadId"),
        "from": headers.get("from", ""),
        "to": headers.get("to", ""),
        "subject": headers.get("subject", "(no subject)"),
        "date": headers.get("date", ""),
        "snippet": msg.get("snippet", ""),
        "body": body.strip()[:3000] if body else msg.get("snippet", ""),
        "labels": msg.get("labelIds", []),
    }


def cmd_list(args):
    access_token = get_access_token(user_id=args.user_id, email=args.email)
    params = {"maxResults": str(args.max), "labelIds": "INBOX"}
    if args.query:
        params["q"] = args.query
    r = requests.get(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages",
        headers={"Authorization": f"Bearer {access_token}"},
        params=params,
        timeout=10,
    )
    if not r.ok:
        print(f"ERROR: Gmail list failed: {r.status_code} {r.text[:200]}", file=sys.stderr)
        sys.exit(1)
    messages = r.json().get("messages", [])
    if not messages:
        print("No messages found.")
        return
    print(f"Found {len(messages)} message(s):\n")
    for m in messages:
        detail = requests.get(
            f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{m['id']}",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"format": "metadata", "metadataHeaders": ["From", "Subject", "Date"]},
            timeout=10,
        )
        if detail.ok:
            parsed = parse_message(detail.json())
            print(f"ID:      {parsed['id']}")
            print(f"From:    {parsed['from']}")
            print(f"Subject: {parsed['subject']}")
            print(f"Date:    {parsed['date']}")
            print(f"Snippet: {parsed['snippet'][:120]}")
            print()


def cmd_get(args):
    access_token = get_access_token(user_id=args.user_id, email=args.email)
    r = requests.get(
        f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{args.message_id}",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"format": "full"},
        timeout=10,
    )
    if not r.ok:
        print(f"ERROR: Gmail get failed: {r.status_code} {r.text[:200]}", file=sys.stderr)
        sys.exit(1)
    parsed = parse_message(r.json())
    print(f"From:    {parsed['from']}")
    print(f"To:      {parsed['to']}")
    print(f"Subject: {parsed['subject']}")
    print(f"Date:    {parsed['date']}")
    print(f"Labels:  {', '.join(parsed['labels'])}")
    print(f"\n--- Body ---\n{parsed['body']}")


def load_env():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../.env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())
    global SUPABASE_KEY, GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, SB
    SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
    GMAIL_CLIENT_ID = os.getenv("GMAIL_CLIENT_ID", "")
    GMAIL_CLIENT_SECRET = os.getenv("GMAIL_CLIENT_SECRET", "")
    SB = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    }


def add_identity_args(p):
    p.add_argument("--user-id", default=None, help="Filter by Supabase user UUID")
    p.add_argument("--email", default=None, help="Filter by Gmail address (e.g. jake@haventechsolutions.com)")


def main():
    load_env()

    p = argparse.ArgumentParser(description="Read Gmail inbox for Hazel")
    sub = p.add_subparsers(dest="cmd")

    ls = sub.add_parser("list", help="List inbox messages")
    ls.add_argument("--max", type=int, default=10)
    ls.add_argument("--query", "-q", default="", help="Gmail search query")
    add_identity_args(ls)

    sr = sub.add_parser("search", help="Search inbox")
    sr.add_argument("query", help="Search query")
    sr.add_argument("--max", type=int, default=10)
    add_identity_args(sr)

    gt = sub.add_parser("get", help="Get full message")
    gt.add_argument("message_id")
    add_identity_args(gt)

    args = p.parse_args()
    if not args.cmd:
        p.print_help()
        sys.exit(1)

    if args.cmd == "list":
        cmd_list(args)
    elif args.cmd == "search":
        args.query = args.query
        cmd_list(args)
    elif args.cmd == "get":
        cmd_get(args)


if __name__ == "__main__":
    main()
