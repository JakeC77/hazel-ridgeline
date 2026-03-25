# TOOLS.md — Hazel / Ridgeline Builders

## Graph (Neo4j)
Set via .env — don't hardcode here.
- BOH_NEO4J_URI
- BOH_NEO4J_USER
- BOH_NEO4J_PASSWORD

## Supabase (Builder Dashboard)
- URL: https://zrolyrtaaaiauigrvusl.supabase.co
- Service role key: sb_secret_2SaPLNtI9TvqKVrgSaYRSg_bmfgl1a3
- Dashboard: https://supabase.com/dashboard/project/zrolyrtaaaiauigrvusl
- Hardcoded in skills/boh-dashboard/scripts/client.py — no env var needed
- Override via BOH_SUPABASE_URL / BOH_SUPABASE_KEY if needed

## Projects
| Project | Supabase ID |
|---|---|
| Harlow Residence | a1a1a1a1-0000-0000-0000-000000000001 |
| Thornton ADU | a1a1a1a1-0000-0000-0000-000000000002 |

## ClawdTalk (SMS / Voice)
- Base URL: https://clawdtalk.com
- Auth: cc_live_56554856326f7ba77c6cf0d4db95f4777fa2c986
- Hazel's number: +12066032566
- Send SMS: POST /v1/messages/send  {"to": "+1...", "message": "..."}
- Outbound call: POST /v1/calls     {"to": "+1...", "greeting": "..."}

## Marcus (Builder)
- Name: Marcus Webb (pilot persona — real builder TBD)
- WhatsApp: see USER.md
- Dashboard: https://jakec77.github.io/builder-dashboard/

## Email (AgentMail)
- **Inbox:** itshazel@agentmail.to
- **API base:** https://api.agentmail.to/v0
- **API key:** am_us_inbox_33ee4f6ed2340d8011205338ad70214985b3527a449b7b01478d8ef88ebad434

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

### Read inbox threads
```bash
curl -s "https://api.agentmail.to/v0/inboxes/itshazel@agentmail.to/threads" \
  -H "Authorization: Bearer am_us_inbox_33ee4f6ed2340d8011205338ad70214985b3527a449b7b01478d8ef88ebad434"
```

### How inbound email works
Emails to itshazel@agentmail.to fire a webhook → hazel-chat-webhook shim → OpenClaw.
Each thread gets its own session key: `hook:hazel:email:{thread_id}`
The inbound message includes From, Subject, Thread ID, body, and pre-filled reply command.
