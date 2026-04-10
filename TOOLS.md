# TOOLS.md — Hazel Platform

## Graph (Neo4j)
Set via environment variables — don't hardcode here.
- BOH_NEO4J_URI
- BOH_NEO4J_USER
- BOH_NEO4J_PASSWORD

## Supabase (Builder Dashboard)
Set via environment variables — never hardcode credentials.
- SUPABASE_URL
- SUPABASE_SERVICE_KEY

The backend (hazel-chat-webhook/server.py) reads these from the systemd service environment.
The agent-side skill (skills/boh-dashboard/scripts/client.py) reads from env vars — no hardcoded key.

Supabase dashboard: https://supabase.com/dashboard/project/zrolyrtaaaiauigrvusl

## Projects
Never hardcode project UUIDs. Always look up project IDs dynamically at runtime.
See AGENTS.md for the canonical dynamic lookup pattern.

## ClawdTalk (SMS / Voice)
- Base URL: https://clawdtalk.com
- Auth: set via CLAWTALK_API_KEY in .env
- Hazel's number: +12066032566
- Send SMS: POST /v1/messages/send  {"to": "+1...", "message": "..."}
- Outbound call: POST /v1/calls     {"to": "+1...", "greeting": "..."}

## Builder Dashboard
- Production URL: https://hazel.haventechsolutions.com/
- Builder identity is resolved from auth.users / firm_users at session time.
  Do not hardcode builder names or contact details in this file.

## Email (AgentMail)
- **Inbox:** itshazel@agentmail.to
- **API base:** https://api.agentmail.to/v0
- **API key:** set via AGENTMAIL_API_KEY in .env

### Send a reply
```bash
python3 skills/boh-dashboard/scripts/send_email.py \
  --thread-id <thread_id> \
  --to "Name <email@example.com>" \
  --subject "Re: Original Subject" \
  --text "your reply"
```

### Send a new email
```bash
python3 skills/boh-dashboard/scripts/send_email.py \
  --to "Name <email@example.com>" \
  --subject "Subject line" \
  --text "body"
```

### How inbound email works
Emails to itshazel@agentmail.to fire a webhook → hazel-chat-webhook shim → OpenClaw.
Each thread gets its own session key: `hook:hazel:email:{thread_id}`
The inbound message includes From, Subject, Thread ID, body, and pre-filled reply command.

## Punch List
Write punch list items to a project:
```bash
python3 skills/boh-dashboard/scripts/write_punch_list.py \
  --project-id <uuid> \
  --items '[{"description": "Issue description", "trade": "Tile", "location": "master bath"}]' \
  --source voice|sms|photo|dashboard_text \
  [--source-file-id <uuid>]
```
- `--items`: JSON array of items, each with `description` (required), `trade` (optional), `location` (optional)
- `--source`: how the items were reported
- Batch insert — pass multiple items in one call
- See AGENTS.md "Punch List Capture" section for trade keyword map and confirmation flow
