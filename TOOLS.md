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
