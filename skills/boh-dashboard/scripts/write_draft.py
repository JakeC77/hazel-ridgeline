#!/usr/bin/env python3
"""
Write a draft item to the builder's approval queue.

Usage:
  python3 write_draft.py \
    --project-id <uuid> \
    --type change-order|email|invoice|daily-log \
    --title "CO-006 · Deck Addition" \
    --meta "To: Sarah Harlow · $8,200 add" \
    --draft-type plaintext|structured \
    --draft '{"content": "..."}' \
    [--escalated] [--escalate-reason "..."]

Draft format:
  plaintext:  --draft '"Email body text here"'
  structured: --draft '{"fields": [{"label": "Amount", "value": "$4,800"}]}'

Outputs: JSON with the created queue_item row (includes id).
"""
import sys, os, json, argparse
sys.path.insert(0, os.path.dirname(__file__))
import client as SB

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--project-id", required=True)
    p.add_argument("--type", required=True, choices=["change-order","email","invoice","daily-log"])
    p.add_argument("--title", required=True)
    p.add_argument("--meta", default="")
    p.add_argument("--draft-type", default="plaintext", choices=["plaintext","structured"])
    p.add_argument("--draft", required=True, help="JSON-encoded draft content")
    p.add_argument("--escalated", action="store_true")
    p.add_argument("--escalate-reason", default=None)
    args = p.parse_args()

    draft = json.loads(args.draft)

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

    result = SB.insert("queue_items", row)
    # Insert returns a list when using return=representation
    item = result[0] if isinstance(result, list) else result

    # Log to audit_log
    SB.insert("audit_log", {
        "project_id": args.project_id,
        "icon": "🤖",
        "message": f"Hazel drafted {args.type}: {args.title}",
        "actor": "Hazel",
        "actor_type": "agent",
    })

    print(json.dumps(item, indent=2))

if __name__ == "__main__":
    main()
