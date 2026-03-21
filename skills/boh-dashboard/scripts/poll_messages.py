#!/usr/bin/env python3
"""
Poll for new messages from the builder in the dashboard chat.
Call this to check if the builder has asked Hazel something via the dashboard.

Usage:
  python3 poll_messages.py \
    --project-id <uuid> \
    [--since "2026-03-20T23:00:00Z"]  # ISO timestamp, only return messages after this

Outputs: JSON list of builder messages with id, content, attachments, created_at.
Use the latest created_at from the response as --since on next poll.
"""
import sys, os, json, argparse
sys.path.insert(0, os.path.dirname(__file__))
import client as SB

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--project-id", required=True)
    p.add_argument("--since", default=None, help="ISO timestamp — only return messages after this")
    args = p.parse_args()

    params = {
        "project_id": f"eq.{args.project_id}",
        "role": "eq.builder",
        "select": "id,content,attachments,created_at",
        "order": "created_at.asc",
    }
    if args.since:
        params["created_at"] = f"gt.{args.since}"

    messages = SB.get("messages", params)
    print(json.dumps(messages, indent=2))

if __name__ == "__main__":
    main()
