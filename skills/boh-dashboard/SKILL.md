# boh-dashboard — Hazel's Dashboard Skill

This skill connects Hazel to the builder's dashboard via Supabase.
Instead of acting immediately (sending emails, making calls), Hazel stages
drafts in the approval queue. The builder reviews, edits if needed, and approves.
Hazel then executes the approved action.

**Root:** `skills/boh-dashboard/`
**Scripts:** `skills/boh-dashboard/scripts/`

---

## Core Workflow

### The Draft → Approve → Execute Loop

1. **Hazel drafts** — instead of sending directly, call `write_draft.py` to stage it
2. **Builder reviews** — they see it on the dashboard, edit if needed, click Approve
3. **Hazel executes** — call `check_decisions.py --mark-seen` to get approved items, then act

**When to draft vs act directly:**
- Change orders, emails to clients, invoices → ALWAYS draft first
- Answering a builder's WhatsApp question → act directly (no draft needed)
- Morning standup call → act directly
- File categorization → act directly (low stakes, builder can correct on dashboard)

---

## Scripts

### 1. Write a Draft
```bash
python3 skills/boh-dashboard/scripts/write_draft.py \
  --project-id <uuid> \
  --type change-order \
  --title "CO-006 · Deck Addition — $8,200" \
  --meta "To: Sarah Harlow · $8,200 add" \
  --draft-type structured \
  --draft '{"fields": [
    {"label": "CO Number", "value": "CO-006"},
    {"label": "Description", "value": "Deck addition per client request"},
    {"label": "Amount", "value": "$8,200.00"},
    {"label": "Payment Terms", "value": "Net 30"},
    {"label": "Client Approval", "value": "SMS to Sarah Harlow"}
  ]}'
```

**Types and when to use them:**
| type | when |
|---|---|
| `change-order` | Any scope/cost change to existing contract |
| `email` | Client updates, sub notifications, weekly summaries |
| `invoice` | Invoice review requests, variance alerts |
| `daily-log` | End-of-day project logs |

**Draft formats:**
- `plaintext`: `--draft '"Email body text here"'` (JSON string)
- `structured`: `--draft '{"fields": [...], "to": "client@email.com"}'`

---

### 2. Check for Builder Decisions
```bash
# See what the builder has approved or rejected
python3 skills/boh-dashboard/scripts/check_decisions.py \
  --project-id <uuid> \
  --mark-seen
```

Returns a JSON list. For each `status: "approved"` item:
- Execute the action (send the email, log the CO, call the sub)
- The `current_draft` field contains the builder's final version (may be edited)
- For emails: use `current_draft` content to send
- For change orders: use `current_draft.fields` for the final values
- After executing, log a confirmation to audit_log

For `status: "rejected"` items — no action needed, already marked.

---

### 3. Dashboard Chat
The builder can message Hazel directly from the dashboard.
These messages appear in the `messages` table with `role = 'builder'`.

**Poll for new messages:**
```bash
python3 skills/boh-dashboard/scripts/poll_messages.py \
  --project-id <uuid> \
  --since "2026-03-20T23:00:00Z"
```

**Send a response:**
```bash
python3 skills/boh-dashboard/scripts/send_message.py \
  --project-id <uuid> \
  --message "Here is the framing plan. Looks like Rev3 is the latest." \
  --file-ids "uuid-of-file"   # optional, attaches files to response
```

**Chat handling rules:**
- Treat dashboard chat the same as WhatsApp — same Hazel persona, same capabilities
- File questions → search the `files` table, respond with file details or attach
- Project status → query boh-graph, summarize concisely
- If a question needs a drafted action → write_draft.py AND send a chat response explaining what was drafted

---

### 4. Check Reminders (run on schedule)
```bash
# Re-surface any snoozed items whose reminder time has passed
python3 skills/boh-dashboard/scripts/check_reminders.py \
  --all-projects
```

Run this every 5 minutes via cron or heartbeat.
Returns list of re-surfaced items — Hazel can optionally SMS the builder
("Hey, that CO reminder just fired — check your dashboard.").

---

### 5. HEIC Conversion Worker (Flow 2)

Converts iPhone HEIC photos to JPEG server-side so the dashboard can render previews.
Fires when a `files` row has a `.heic`/`.heif` storage_path and `converted_path IS NULL`.

**Run once (e.g. triggered after a file upload):**
```bash
python3 skills/boh-dashboard/scripts/heic_convert.py
```

**Run as a polling daemon (recommended — checks every 30s):**
```bash
python3 skills/boh-dashboard/scripts/heic_convert.py --daemon
python3 skills/boh-dashboard/scripts/heic_convert.py --daemon --interval 60
```

**One-time deps (install on droplet):**
```bash
pip install pillow-heif Pillow
```

**What it does per file:**
1. Selects `files` rows: `storage_path` ends in `.heic`/`.heif`, `converted_path IS NULL`, `archived = false`
2. Downloads the original HEIC from Supabase Storage (service role)
3. Converts to JPEG at quality 85, honouring EXIF orientation
4. Uploads JPEG to `project-files/{project_id}/photos/{stem}_converted.jpg`
5. Writes the JPEG path back to `files.converted_path`

On failure: logs the error, leaves `converted_path` NULL.
The dashboard shows a 📷 placeholder + "Download HEIC" CTA for unconverted files — acceptable fallback.

---

## Project IDs

| Project | ID |
|---|---|
| Harlow Residence | `a1a1a1a1-0000-0000-0000-000000000001` |
| Thornton ADU | `a1a1a1a1-0000-0000-0000-000000000002` |

Fetch all projects:
```bash
python3 -c "
import sys; sys.path.insert(0, 'skills/boh-dashboard/scripts')
import client as SB, json
print(json.dumps(SB.get('projects', {'select': 'id,name'}), indent=2))
"
```

---

## Execution Examples

### Example: Builder approved a change order — now execute it

```python
# check_decisions.py returned this approved item:
item = {
  "id": "...",
  "type": "change-order",
  "title": "CO-006 · Deck Addition",
  "current_draft": {"fields": [
    {"label": "Amount", "value": "$8,200.00"},
    {"label": "Client Approval", "value": "SMS to Sarah Harlow (+1 425-555-0191)"}
  ]},
  "decided_by": "builder"
}

# Execute: send SMS to client via ClawdTalk
# POST https://clawdtalk.com/v1/messages/send
# { "to": "+14255550191", "message": "CO-006 attached. Reply YES to approve." }

# Then log completion
SB.insert("audit_log", {
  "project_id": PROJECT_ID,
  "icon": "📤",
  "message": "CO-006 sent to Sarah Harlow for approval",
  "actor": "Hazel",
  "actor_type": "agent"
})
```

### Example: Draft a weekly email update

```bash
python3 skills/boh-dashboard/scripts/write_draft.py \
  --project-id a1a1a1a1-0000-0000-0000-000000000001 \
  --type email \
  --title "Weekly update — Harlow Residence" \
  --meta "To: sarah.harlow@email.com" \
  --draft-type plaintext \
  --draft '"Hi Sarah,\n\nQuick update on the Harlow Residence...\n\nBest,\nMarcus"'
```

---

## Creds
- URL and keys are hardcoded in `client.py` using the service role key (full access)
- Override via env: `BOH_SUPABASE_URL`, `BOH_SUPABASE_KEY`
- Dashboard (anon key): in TOOLS.md under Supabase — Hazel BOH
