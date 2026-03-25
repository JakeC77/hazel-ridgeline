#!/usr/bin/env python3
"""
send_email.py — Hazel's outbound email via AgentMail

Usage (reply to a thread):
  python3 send_email.py --thread-id <id> --to "Name <email>" --text "..."

Usage (new email):
  python3 send_email.py --to "Name <email>" --subject "..." --text "..."

Optional:
  --inbox-id  defaults to itshazel@agentmail.to
  --html      HTML body (in addition to or instead of --text)
  --cc        CC address(es), comma-separated
"""
import argparse, json, os, sys, requests

AGENTMAIL_API  = "https://api.agentmail.to/v0"
AGENTMAIL_KEY  = os.getenv("AGENTMAIL_API_KEY", "am_us_inbox_33ee4f6ed2340d8011205338ad70214985b3527a449b7b01478d8ef88ebad434")
DEFAULT_INBOX  = "itshazel@agentmail.to"


def headers():
    return {
        "Authorization": f"Bearer {AGENTMAIL_KEY}",
        "Content-Type": "application/json",
    }


def create_draft(inbox_id, to, subject, text, html, cc, thread_id):
    payload = {}
    if to:
        payload["to"] = [to] if isinstance(to, str) else to
    if subject:
        payload["subject"] = subject
    if text:
        payload["text"] = text
    if html:
        payload["html"] = html
    if cc:
        payload["cc"] = [cc] if isinstance(cc, str) else cc
    if thread_id:
        payload["thread_id"] = thread_id

    r = requests.post(
        f"{AGENTMAIL_API}/inboxes/{inbox_id}/drafts",
        headers=headers(),
        json=payload,
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def send_draft(inbox_id, draft_id):
    r = requests.post(
        f"{AGENTMAIL_API}/inboxes/{inbox_id}/drafts/{draft_id}/send",
        headers=headers(),
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def main():
    p = argparse.ArgumentParser(description="Send email as Hazel via AgentMail")
    p.add_argument("--inbox-id",  default=DEFAULT_INBOX)
    p.add_argument("--to",        required=True, help="Recipient: email or 'Name <email>'")
    p.add_argument("--subject",   help="Subject (optional for replies)")
    p.add_argument("--text",      help="Plain-text body")
    p.add_argument("--html",      help="HTML body")
    p.add_argument("--cc",        help="CC address(es), comma-separated")
    p.add_argument("--thread-id", help="Thread ID for replies")
    args = p.parse_args()

    if not args.text and not args.html:
        print("ERROR: must provide --text or --html", file=sys.stderr)
        sys.exit(1)

    cc_list = [a.strip() for a in args.cc.split(",")] if args.cc else None

    print(f"Creating draft → {args.to}")
    draft = create_draft(
        inbox_id=args.inbox_id,
        to=args.to,
        subject=args.subject,
        text=args.text,
        html=args.html,
        cc=cc_list,
        thread_id=args.thread_id,
    )
    draft_id = draft.get("draft_id") or draft.get("id")
    if not draft_id:
        print(f"ERROR: no draft_id in response: {json.dumps(draft)}", file=sys.stderr)
        sys.exit(1)

    print(f"Sending draft {draft_id}...")
    result = send_draft(args.inbox_id, draft_id)
    print(f"Sent. message_id={result.get('message_id', 'unknown')}")


if __name__ == "__main__":
    main()
