#!/usr/bin/env python3
"""
Write a draft item to the builder's approval queue.

Usage:
  python3 write_draft.py \
    --project-id <uuid> \
    --type change-order|email|invoice|daily-log|needs-info \
    --title "CO-006 · Deck Addition" \
    --meta "To: Sarah Harlow · $8,200 add" \
    --draft-type plaintext|structured \
    --draft '{"content": "..."}' \
    [--escalated] [--escalate-reason "..."]

Draft format:
  plaintext:  --draft '"Email body text here"'
  structured: --draft '{"fields": [{"label": "Amount", "value": "$4,800"}]}'

Email drafts (--type email) MUST use structured format with:
  --draft '{"to": "Name <email@example.com>", "subject": "...", "body": "..."}'
  The "to" field MUST contain valid email addresses.
  Multiple recipients: "Name <a@b.com>, Other <c@d.com>"

Outputs: JSON with the created queue_item row (includes id).
"""
import sys, os, json, argparse, re
sys.path.insert(0, os.path.dirname(__file__))
import client as SB

EMAIL_REGEX = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')


def validate_email_draft(draft):
    """Validate that an email draft has required fields with valid email addresses.
    Returns (ok, error_message)."""
    if not isinstance(draft, dict):
        return False, (
            "Email drafts must be structured JSON with: to, subject, body.\n"
            'Example: --draft \'{"to": "Name <email@example.com>", "subject": "...", "body": "..."}\''
        )

    to = draft.get("to", "")
    subject = draft.get("subject", "")
    body = draft.get("body", "")

    errors = []

    if not to:
        errors.append('"to" field is required and must contain an email address.')
    elif not EMAIL_REGEX.search(to):
        errors.append(
            f'"to" field must contain a valid email address. Got: "{to}"\n'
            'Use format: "Name <email@example.com>" or just "email@example.com"'
        )

    if not subject:
        errors.append('"subject" field is required.')

    if not body:
        errors.append('"body" field is required.')

    if errors:
        return False, "Email draft validation failed:\n- " + "\n- ".join(errors)

    return True, ""


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--project-id", required=True)
    p.add_argument("--type", required=True, choices=["change-order","email","invoice","daily-log","needs-info"])
    p.add_argument("--title", required=True)
    p.add_argument("--meta", default="")
    p.add_argument("--draft-type", default="plaintext", choices=["plaintext","structured"])
    p.add_argument("--draft", required=True, help="JSON-encoded draft content")
    p.add_argument("--escalated", action="store_true")
    p.add_argument("--escalate-reason", default=None)
    args = p.parse_args()

    draft = json.loads(args.draft)

    # Validate email drafts
    if args.type == "email":
        ok, err = validate_email_draft(draft)
        if not ok:
            print(json.dumps({"error": err}), file=sys.stderr)
            sys.exit(1)

    row = {
        "project_id": args.project_id,
        "type": args.type,
        "title": args.title,
        "meta": args.meta,
        "status": "active",
        "draft_type": args.draft_type,
        "current_draft": draft,
        "original_draft": draft,
        "versions": [{"version": 1, "editor": "hazel", "createdAt": "now"}],
        "escalated": args.escalated,
        "escalate_reason": args.escalate_reason,
    }

    # Look up firm_id from project
    try:
        proj = SB.get("projects", {"id": f"eq.{args.project_id}", "select": "firm_id", "limit": "1"})
        firm_id = proj[0]["firm_id"] if proj else None
    except Exception:
        firm_id = None

    if firm_id:
        row["firm_id"] = firm_id

    result = SB.insert("queue_items", row)
    # Insert returns a list when using return=representation
    item = result[0] if isinstance(result, list) else result

    # Log to audit_log
    audit = {
        "project_id": args.project_id,
        "icon": "❓" if args.type == "needs-info" else "🤖",
        "message": f"Hazel drafted {args.type}: {args.title}",
        "actor": "Hazel",
        "actor_type": "agent",
        "action_type": "queue_created",
        "triggered_by": "inbound_message",
        "related_entity_type": "queue_item",
    }
    if firm_id:
        audit["firm_id"] = firm_id
    if item and item.get("id"):
        audit["related_entity_id"] = item["id"]
    SB.insert("audit_log", audit)

    print(json.dumps(item, indent=2))

if __name__ == "__main__":
    main()
