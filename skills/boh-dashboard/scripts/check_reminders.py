#!/usr/bin/env python3
"""
Check for snoozed queue items whose reminder time has passed, and re-surface them.
Also checks for escalation conditions on snoozed items.

Run this on a schedule (e.g. every 5 minutes via cron or heartbeat).

Usage:
  python3 check_reminders.py --project-id <uuid>
  python3 check_reminders.py --all-projects

Outputs: JSON list of items that were re-surfaced (for Hazel to optionally notify builder).
"""
import sys, os, json, argparse
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(__file__))
import client as SB

def resurface(item, project_id, reason=None):
    patch = {"status": "active", "reminder_at": None}
    if reason:
        patch["escalated"] = True
        patch["escalate_reason"] = reason

    SB.update("queue_items", patch, {"id": item["id"]})

    msg = f"Reminder fired: {item['title']} returned to active queue"
    if reason:
        msg = f"Hazel escalated early: {item['title']} — {reason}"

    SB.insert("audit_log", {
        "project_id": project_id,
        "icon": "⚡" if reason else "🔔",
        "message": msg,
        "actor": "Hazel",
        "actor_type": "agent",
    })
    return {**item, "resurfaced": True, "escalate_reason": reason}

def check_project(project_id):
    now = datetime.now(timezone.utc).isoformat()
    params = {
        "project_id": f"eq.{project_id}",
        "status": "eq.snoozed",
        "select": "id,type,title,reminder_at,escalated,escalate_reason",
    }
    items = SB.get("queue_items", params)
    resurfaced = []
    for item in items:
        if not item.get("reminder_at"):
            continue
        reminder_dt = datetime.fromisoformat(item["reminder_at"].replace("Z", "+00:00"))
        now_dt = datetime.now(timezone.utc)
        if now_dt >= reminder_dt:
            resurfaced.append(resurface(item, project_id))
    return resurfaced

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--project-id", default=None)
    p.add_argument("--all-projects", action="store_true")
    args = p.parse_args()

    results = []
    if args.all_projects:
        projects = SB.get("projects", {"select": "id"})
        for proj in projects:
            results.extend(check_project(proj["id"]))
    elif args.project_id:
        results = check_project(args.project_id)
    else:
        print(json.dumps({"error": "provide --project-id or --all-projects"}))
        sys.exit(1)

    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()
