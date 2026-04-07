# TOOLS.md — Hazel / Ridgeline Builders

## Graph (Neo4j)
Set via .env — don't hardcode here.
- BOH_NEO4J_URI
- BOH_NEO4J_USER
- BOH_NEO4J_PASSWORD

## Supabase (Builder Dashboard)
- URL: https://zrolyrtaaaiauigrvusl.supabase.co
- Key: set via SUPABASE_SERVICE_KEY or BOH_SUPABASE_KEY in .env
- Dashboard: https://supabase.com/dashboard/project/zrolyrtaaaiauigrvusl

## Projects
Query project IDs dynamically from Supabase — don't hardcode UUIDs here.

## ClawdTalk (SMS / Voice)
- Base URL: https://clawdtalk.com
- Auth: set via CLAWTALK_API_KEY in .env
- Hazel's number: +12066032566
- Send SMS: POST /v1/messages/send  {"to": "+1...", "message": "..."}
- Outbound call: POST /v1/calls     {"to": "+1...", "greeting": "..."}

## Builder Dashboard
- Dashboard: https://haventechsolutions.com
- Builder context comes from Supabase at runtime — see USER.md for session context

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
