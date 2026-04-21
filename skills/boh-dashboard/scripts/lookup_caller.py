#!/usr/bin/env python3
"""
lookup_caller.py — Resolve a phone number to user identity + Gmail status.

Multi-tenant: --firm-id is REQUIRED when falling back to local memory files,
since memory is now firm-scoped (memory/<firm-id>/people/*.md). The Supabase
contacts lookup is already firm-scoped by the contacts row's firm_id, but the
local-file fallback needs an explicit firm-id to know which subdirectory to
search. For the Ridgeline dev persona pass --firm-id ridgeline.

Usage:
  python3 lookup_caller.py --firm-id <firm_uuid_or_ridgeline> --phone "+12069631303"

Returns JSON with: name, firm_id, user_id, email, gmail_connected, gmail_email
"""
import argparse
import json
import os
import re
import glob

# Try Supabase first, fall back to local files
try:
    from client import supabase_get
    HAS_CLIENT = True
except ImportError:
    HAS_CLIENT = False


def normalize_phone(phone):
    """Strip to digits only, ensure leading 1 for US numbers."""
    digits = re.sub(r'\D', '', phone)
    if len(digits) == 10:
        digits = '1' + digits
    return digits


def lookup_supabase(phone_digits, firm_id):
    """Try to find user by phone in contacts scoped to this firm."""
    if not HAS_CLIENT or not firm_id or firm_id == "ridgeline":
        # "ridgeline" is the literal dev-persona slug — no matching row in contacts.
        return None
    # Check contacts table for matching phone, firm-scoped
    try:
        results = supabase_get("contacts", params={
            "firm_id": f"eq.{firm_id}",
            "phone": f"ilike.%{phone_digits[-10:]}%",
            "select": "id,name,email,firm_id",
            "limit": "1"
        })
        if results:
            return results[0]
    except Exception:
        pass
    return None


def lookup_people_files(phone_digits, firm_id):
    """Search memory/<firm-id>/people/*.md for a phone number match."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Walk up to find memory/<firm-id>/people/
    # (From scripts/ that's ../../../memory/<firm-id>/people/)
    for base in [
        os.path.join(script_dir, '..', '..', '..', 'memory', firm_id, 'people'),
        os.path.join(os.getcwd(), 'memory', firm_id, 'people'),
    ]:
        base = os.path.normpath(base)
        if not os.path.isdir(base):
            continue
        for md_file in glob.glob(os.path.join(base, '*.md')):
            try:
                with open(md_file, 'r') as f:
                    content = f.read()
                # Check if phone digits appear in this file
                content_digits = re.sub(r'\D', '', content)
                if phone_digits[-10:] in content_digits:
                    # Extract name from first heading
                    name_match = re.search(r'^#\s+(.+)', content, re.MULTILINE)
                    name = name_match.group(1).split('—')[0].strip() if name_match else os.path.basename(md_file).replace('.md', '')
                    # Extract email
                    email_match = re.search(r'\*?\*?Email:?\*?\*?\s*(\S+@\S+)', content, re.IGNORECASE)
                    email = email_match.group(1) if email_match else None
                    # Extract firm_id
                    firm_match = re.search(r'Firm ID:?\*?\*?\s*([0-9a-f-]+)', content, re.IGNORECASE)
                    firm_id = firm_match.group(1) if firm_match else None
                    # Check gmail status
                    gmail_connected = bool(re.search(r'Gmail connected:?\s*yes', content, re.IGNORECASE))
                    # Extract gmail email if different
                    gmail_match = re.search(r'--email\s+(\S+@\S+)', content)
                    gmail_email = gmail_match.group(1) if gmail_match else email

                    return {
                        "name": name,
                        "email": email,
                        "firm_id": firm_id,
                        "gmail_connected": gmail_connected,
                        "gmail_email": gmail_email,
                        "source": os.path.basename(md_file),
                    }
            except Exception:
                continue
    return None


def lookup_gmail_status(firm_id, email):
    """Check gmail_tokens table for connection status."""
    if not HAS_CLIENT or not firm_id:
        return None
    try:
        results = supabase_get("gmail_tokens", params={
            "firm_id": f"eq.{firm_id}",
            "select": "email,user_id,watch_expiry",
        })
        if results:
            # If we have the caller's email, find their specific row
            for row in results:
                if email and row.get("email", "").lower() == email.lower():
                    return {"gmail_connected": True, "gmail_email": row["email"], "user_id": row.get("user_id")}
            # Otherwise return first match
            row = results[0]
            return {"gmail_connected": True, "gmail_email": row["email"], "user_id": row.get("user_id")}
        return {"gmail_connected": False}
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser(description="Look up caller identity by phone number")
    parser.add_argument(
        "--firm-id",
        required=True,
        help=(
            "Firm identifier (UUID for real firms, 'ridgeline' for the dev "
            "persona). REQUIRED — scopes both the Supabase contact search and "
            "the local memory/<firm-id>/people/ file search."
        ),
    )
    parser.add_argument("--phone", required=True, help="Phone number to look up")
    args = parser.parse_args()

    phone_digits = normalize_phone(args.phone)
    result = {"phone": args.phone, "phone_normalized": phone_digits, "firm_id": args.firm_id}

    # Try Supabase contacts first (firm-scoped)
    sb_match = lookup_supabase(phone_digits, args.firm_id)
    if sb_match:
        result.update(sb_match)
        result["source"] = "contacts"

    # Try local people files (firm-scoped)
    people_match = lookup_people_files(phone_digits, args.firm_id)
    if people_match:
        # Merge — people files have more context
        for k, v in people_match.items():
            if v and not result.get(k):
                result[k] = v
        if "source" not in result or result["source"] == "contacts":
            result["source"] = people_match.get("source", "people_files")

    # Check Gmail status if we have firm_id
    if result.get("firm_id"):
        gmail = lookup_gmail_status(result["firm_id"], result.get("email"))
        if gmail:
            result.update(gmail)

    if "name" not in result:
        result["identified"] = False
        result["message"] = f"No match found for phone {args.phone}"
    else:
        result["identified"] = True

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
