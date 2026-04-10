#!/usr/bin/env python3
"""
Write punch list items to a project.

Usage:
  python3 write_punch_list.py \
    --project-id <uuid> \
    --items '[{"description": "Tile grout cracking", "trade": "tile", "location": "master bath"}]' \
    --source voice|sms|photo|dashboard_text \
    [--source-file-id <uuid>]

Each item in the JSON array should have:
  - description (required): what the issue is
  - trade (optional): assigned trade (tile, painting, electrical, etc.)
  - location (optional): where in the building

Outputs: JSON array of created punch_list_items rows.
"""
import sys, os, json, argparse
sys.path.insert(0, os.path.dirname(__file__))
import client as SB


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--project-id", required=True)
    p.add_argument("--items", required=True, help="JSON array of {description, trade?, location?}")
    p.add_argument("--source", required=True, choices=["voice", "sms", "photo", "dashboard_text"])
    p.add_argument("--source-file-id", default=None, help="File ID if source is photo")
    args = p.parse_args()

    items = json.loads(args.items)
    if not isinstance(items, list):
        items = [items]

    if not items:
        print(json.dumps({"error": "No items provided"}), file=sys.stderr)
        sys.exit(1)

    # Validate each item has a description
    for i, item in enumerate(items):
        if not item.get("description", "").strip():
            print(json.dumps({"error": f"Item {i+1} missing description"}), file=sys.stderr)
            sys.exit(1)

    # Look up firm_id from project
    try:
        proj = SB.get("projects", {"id": f"eq.{args.project_id}", "select": "firm_id", "limit": "1"})
        firm_id = proj[0]["firm_id"] if proj else None
    except Exception:
        firm_id = None

    created = []
    for item in items:
        row = {
            "project_id": args.project_id,
            "description": item["description"].strip(),
            "assigned_trade": item.get("trade", "").strip() or None,
            "location": item.get("location", "").strip() or None,
            "source": args.source,
            "source_file_id": args.source_file_id,
        }
        if firm_id:
            row["firm_id"] = firm_id

        result = SB.insert("punch_list_items", row)
        if isinstance(result, list):
            created.extend(result)
        else:
            created.append(result)

    # Log to audit_log
    audit = {
        "project_id": args.project_id,
        "icon": "📋",
        "message": f"Hazel logged {len(created)} punch list item{'s' if len(created) != 1 else ''} via {args.source}",
        "actor": "Hazel",
        "actor_type": "agent",
        "action_type": "punch_list_created",
        "triggered_by": "inbound_message",
    }
    if firm_id:
        audit["firm_id"] = firm_id
    SB.insert("audit_log", audit)

    print(json.dumps(created, indent=2))


if __name__ == "__main__":
    main()
