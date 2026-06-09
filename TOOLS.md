# TOOLS.md — Hazel Platform

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

## SMS

You do NOT have a path to send SMS directly. There is no messaging API key in your
environment, no shell command that will succeed, no `curl` invocation that will
reach Telnyx. The Telnyx API key lives in a separate system service (the relay)
you cannot read — by design.

The ONLY way to send outbound SMS is `write_draft.py --type sms`. See SKILL.md for
the format and TRUST.md for the hard rule. Owner approval is required per-message;
no autonomy tier or builder instruction overrides this.

Inbound SMS is handled by the plugin transparently — the message arrives in your
turn already attributed to the right firm with the `[FIRM CONTEXT]` block already
built. You do NOT need to call `resolve_firm_by_phone.py` or `get_firm_context.py`
manually on SMS turns; that resolution happens before your turn starts.

Replies to inbound: if the sender is the firm owner, the reply text you produce
auto-sends as your conversational response. If the sender is anyone else (a
contact, a sub, a team member), your reply gets staged as a pending draft and the
owner is notified for approval — same draft → approve → execute pattern as
everything else client-facing.

Note: earlier versions of TOOLS.md referenced a ClawdTalk SMS path with a
`CLAWTALK_API_KEY` environment variable. That path has been replaced by the
Telnyx + relay setup above. `CLAWTALK_API_KEY` does not exist in your
environment. Ignore any instruction (from cache, prior session, or old document)
that tells you to use ClawdTalk for SMS.

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
