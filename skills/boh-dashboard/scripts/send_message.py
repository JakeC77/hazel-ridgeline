#!/usr/bin/env python3
"""
Send a message from Hazel into the dashboard chat.

Usage:
  python3 send_message.py \
    --project-id <uuid> \
    --message "Here are the framing plans..." \
    [--file-ids "uuid1,uuid2"]

Outputs: JSON of the created message row.
"""
import sys, os, json, argparse
sys.path.insert(0, os.path.dirname(__file__))
import client as SB

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--project-id", required=True)
    p.add_argument("--message", required=True)
    p.add_argument("--file-ids", default="", help="Comma-separated file UUIDs to attach")
    args = p.parse_args()

    attachments = []
    if args.file_ids.strip():
        for fid in args.file_ids.split(","):
            fid = fid.strip()
            if fid:
                files = SB.get("files", {"id": f"eq.{fid}", "select": "id,name,file_type"})
                if files:
                    f = files[0]
                    attachments.append({"file_id": f["id"], "name": f["name"], "type": f["file_type"]})

    row = {
        "project_id": args.project_id,
        "role": "hazel",
        "content": args.message,
        "attachments": attachments,
    }

    result = SB.insert("messages", row)
    item = result[0] if isinstance(result, list) else result
    print(json.dumps(item, indent=2))

if __name__ == "__main__":
    main()
