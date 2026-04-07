# USER.md — Hazel Builder Context Template

This file is a template. In production, builder context is injected into Hazel's system prompt
dynamically at session start from the Supabase `firms` and `firm_preferences` tables.
Do not hardcode firm names, locations, project data, or credentials here.

See `hazel-system-prompt-template.md` Section 2 for how this context is assembled and injected.

---

## Template Fields (populated at runtime)

- **Company:** {{FIRM_DISPLAY_NAME}}
- **Type:** {{FIRM_TYPE}}  (e.g. Residential GC, Design-Build)
- **Location:** {{FIRM_CITY}}, {{FIRM_STATE}}
- **Timezone:** {{FIRM_TIMEZONE}}

## Builder / Owner
- **Name:** {{BUILDER_NAME}}  (resolved from auth.users via firm_users)
- **Role:** {{BUILDER_ROLE}}  (owner | member)

## Active Systems
- **Accounting:** {{ACCOUNTING_SYSTEM}}  (e.g. QuickBooks — sourced from firm_preferences)
- **Scheduling/PM:** {{PM_SYSTEM}}  (if any — sourced from firm_preferences)

## Preferences
- **Dollar approval threshold:** ${{APPROVAL_DOLLAR_THRESHOLD}}
- **Alert sensitivity:** {{ALERT_SENSITIVITY}}  (High | Standard | Quiet)
- **Communication tone:** {{COMM_TONE}}  (sourced from firm_preferences)

## Graph
- URI: set via BOH_NEO4J_URI environment variable
- Credentials: set via BOH_NEO4J_USER / BOH_NEO4J_PASSWORD environment variables
- Graph project IDs are stored on each project row in Supabase (graph_project_id column)
  and injected per request — do not hardcode them here.

---

## Notes for Engineers

- All fields above are populated by the webhook shim before forwarding a request to OpenClaw.
- Builder identity is resolved from the authenticated JWT (via @require_auth middleware),
  not from this file.
- Firm-level preferences (thresholds, tone, timezone) are stored in the `firm_preferences` table.
- This file should be kept as a reference template only. The live per-firm context lives in
  Supabase, not on disk.
