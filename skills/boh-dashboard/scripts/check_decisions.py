#!/usr/bin/env python3
"""
Poll for builder decisions on queue items (approved or rejected).
Call this after writing drafts to see what the builder has acted on.

Usage:
  python3 check_decisions.py --project-id <uuid> [--mark-seen]

--mark-seen: after returning approved items, update them so they won't
             be returned again (adds 'executed' to status).

Outputs: JSON list of decided items. Each has:
  - id, type, title, status (approved|rejected)
  - current_draft (the final version the builder approved)
  - decided_at, decided_by
"""
import sys, os, json, argparse
sys.path.insert(0, os.path.dirname(__file__))
import client as SB

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--project-id", required=True)
    p.add_argument("--mark-seen", action="store_true", help="Mark approved items as executed after returning them")
    args = p.parse_args()

    params = {
        "project_id": f"eq.{args.project_id}",
        "status": "in.(approved,rejected)",
        "select": "id,type,title,meta,status,draft_type,current_draft,original_draft,decided_at,decided_by,escalated",
        "order": "decided_at.asc",
    }

    items = SB.get("queue_items", params)

    if args.mark_seen and items:
        for item in items:
            if item["status"] == "approved":
                SB.update("queue_items", {"status": "executed"}, {"id": item["id"]})
                SB.insert("audit_log", {
                    "project_id": args.project_id,
                    "icon": "⚡",
                    "message": f"Hazel executing approved {item['type']}: {item['title']}",
                    "actor": "Hazel",
                    "actor_type": "agent",
                })

    print(json.dumps(items, indent=2))

if __name__ == "__main__":
    main()
