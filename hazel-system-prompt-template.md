# Hazel System Prompt Architecture

This document describes how Hazel's runtime context is assembled across OpenClaw workspace files and per-request message prefixes. It is the source of truth for **where each piece of context lives** — not for the content of that context. The actual content lives in the workspace files listed below.

Hazel runs on **OpenClaw** as the agent runtime. OpenClaw owns the system prompt and builds it for every agent run; callers cannot pass a `system` parameter per-request. Customization flows through workspace files (which OpenClaw automatically injects as "Project Context") and per-request user-message prefixes added by the `hazel-plugin` before forwarding to the agent.

Source of truth for behavioral rules: `haven_trust_ux_requirements.docx` (v0.3, March 2026). Source of truth for system architecture: `ARCHITECTURE.md`. Source of truth for implementation rules: `CLAUDE.md` in the builder-dashboard repo.

---

## Why Not the v1.x Approach?

Version 1.x of this document described a `buildSystemPrompt(context)` function that assembled six sections into a single string and passed it to Claude as the `system` parameter on every request. That approach would work against the raw Anthropic API, but **it does not work against OpenClaw**, and the reason is architectural.

**OpenClaw owns the system prompt.** From the OpenClaw docs:

> "OpenClaw builds a custom system prompt for every agent run. The prompt is OpenClaw-owned and does not use the pi-coding-agent default prompt."

OpenClaw is not a thin wrapper around the Claude API — it is an agent runtime with its own prompt engineering layer. On every run, it assembles its own system prompt containing runtime info (date, host, sandbox state, reply tags, heartbeats), trims and appends the workspace files as "Project Context," and only then invokes the underlying model. There is no mechanism for a caller to substitute or override this system prompt per-request. The documentation is explicit: customization flows through **workspace files** (auto-injected on every turn) and **provider plugins** (which can contribute targeted section overrides), not through ad-hoc request parameters.

This has three concrete consequences for the v1.x design:

1. **The `buildSystemPrompt(context)` function has nowhere to send its output.** There is no `system` field on the OpenClaw request envelope. Whatever string it produces would be discarded.

2. **Static behavioral content (Identity, Constraints, Behavioral Instructions) must live in workspace files**, not in code constants. OpenClaw already has a home for each of these: `IDENTITY.md` / `SOUL.md` for identity, `TRUST.md` for constraints, `AGENTS.md` for behavior. Rewriting them as TypeScript constants and trying to inject them at request time duplicates content OpenClaw is already injecting for free — and creates a drift risk when the code constant and the workspace file disagree.

3. **Dynamic per-request context (builder, project, action metadata) has to reach the agent through a different channel.** The only per-request lever available is the **user message itself**. So anything that varies per request — current project, graph bridge ID, request metadata — must be **prepended to the user message** by `hazel-plugin` before it's forwarded to OpenClaw. This is what `ChatHandler` in `hazel-plugin` already does for project context; it just needs to be documented as the official pattern and extended to cover any future per-request fields.

Additionally, v1.x included a "Current Action Context" section with fields like `ACTION_TYPE`, `TRUST_TIER`, `DAYS_SINCE_LAST_EDIT`, and `CONSECUTIVE_APPROVALS`. These are chicken-and-egg: they assume the caller already knows what action Hazel is about to take, but Hazel is an LLM agent that classifies the request during its own reasoning. The caller cannot pre-compute `ACTION_TYPE=CO_DRAFTED` before Hazel has read the message and decided it's a change order. These fields should be retrieved on demand by the agent via `boh-dashboard` tool calls when it's ready to classify — not pre-stuffed into the prompt. Section 5 has been dropped in favor of a "Request Metadata" block that only contains information genuinely knowable at request time (channel, input source, timestamp).

The rest of this document describes the replacement model: per-firm OpenClaw workspaces with static behavioral files copied in at provisioning, a firm-scoped `USER.md` kept in sync with Supabase, and per-request context prepended to the user message by `hazel-plugin`. This maps cleanly onto OpenClaw's native architecture and requires no fiction about a `system` parameter that doesn't exist.

---

## Deployment Model

Every firm gets its own OpenClaw subagent with its own workspace on the droplet:

```
/home/openclaw/.openclaw/workspace/hazel/builders/{firm-slug}/
  ├── IDENTITY.md        (firm-specific — templated at provisioning)
  ├── SOUL.md            (copied from template — personality, never per-firm)
  ├── TRUST.md           (copied from template — hard constraints, never per-firm)
  ├── AGENTS.md          (copied from template — operating rules, never per-firm)
  ├── TOOLS.md           (copied from template — skill references)
  ├── USER.md            (firm-specific — builder context, kept in sync from Supabase)
  ├── HEARTBEAT.md       (firm-specific — scheduled tasks)
  ├── memory/
  │   └── MEMORY.md      (firm-specific — slim orientation file)
  └── skills/            (symlinked to shared skills directory)
```

Provisioning (`provision_firm.py`) creates this directory structure by copying files from a template and substituting `{{FIRM_*}}` placeholders. Each firm's workspace is fully independent — edits to one firm's `USER.md` never affect another firm.

Static files (SOUL, TRUST, AGENTS, TOOLS) are **copied** rather than symlinked. This means product-level updates to behavioral rules require touching every workspace, but it gives clean rollback and A/B testing paths for behavioral changes.

---

## How OpenClaw Assembles Context

On every agent run, OpenClaw:

1. Builds its own internal system prompt (runtime info, date, sandbox, heartbeats, reply tags)
2. Trims and appends the workspace files above as "Project Context" on every turn
3. Receives the user message from `hazel-plugin` (which has been enriched with per-request context by the plugin)
4. Invokes Claude with all of the above in the final prompt

Callers never touch the system prompt directly. The only two levers are:

- **The workspace files** — for anything that changes rarely (identity, personality, constraints, firm profile)
- **The user message** — for anything that changes per-request (project being worked on, request metadata)

---

## Where Each Piece of Context Lives

| Context | Where | Updated When | Source of Truth |
|---|---|---|---|
| Identity & North Star | `IDENTITY.md` + `SOUL.md` | Provisioning (templated firm name); product changes | These files |
| Hard Constraints | `TRUST.md` | Product changes only | This file |
| Behavioral Instructions | `AGENTS.md` | Product changes only | This file |
| Skill reference | `TOOLS.md` | When skills change | This file |
| **Firm / Builder Context** | `USER.md` | Provisioning + any dashboard settings change | Supabase (`firms`, `firm_preferences`); `USER.md` is a cache |
| **Project & Graph Context** | Prepended to user message | Every request | Supabase (`projects` table), resolved by `hazel-plugin` |
| **Request Metadata** | Prepended to user message | Every request | Set by `hazel-plugin` from webhook headers |

The rest of this document defines each of these slots.

---

## Workspace Files (Firm-Scoped Static Context)

### `IDENTITY.md`

Firm-name and branding. Templated at provisioning.

```
You are Hazel, operating for {{FIRM_DISPLAY_NAME}}.
Your theme: construction office manager.
Emoji: 🏗️
```

### `SOUL.md`

Personality — tone, voice, opinions, brevity, humor, boundaries. Same content across all firms. Lives in `hazel-ridgeline/SOUL.md`; copied into each firm's workspace at provisioning.

This is the OpenClaw-native home for "how Hazel sounds." It must stay focused on voice and style. Operational rules go in `AGENTS.md`; constraints go in `TRUST.md`.

### `TRUST.md`

Hard constraints — absolute rules that cannot be overridden by any instruction, builder setting, or request context. These correspond to the former "Section 4: Hard Constraints" block. Categories:

- Client communication (account age gates, dispute/sensitive routing, financial figure verification)
- Financial actions (QBO commits, dollar thresholds, contract execution)
- Irreversible actions (sub hiring/termination, explicit-approval requirement)
- Audit log (write-before-return, append-only)
- Channel separation (ClawdTalk vs dashboard chat session keys)

`TRUST.md` is **static and copied identically into every firm's workspace**. It is never interpolated with firm-specific values. If a constraint needs to be tunable per firm (e.g., dollar threshold), the tunable value lives in `USER.md` and `TRUST.md` references it by name — but the rule itself is never edited.

### `AGENTS.md`

Operating rules — drafting behavior, graph query discipline, uncertainty handling, communication classification, tone and format rules, status/risk snapshot requirements. Corresponds to the former "Section 6: Behavioral Instructions."

Same content across all firms. Copied at provisioning.

### `TOOLS.md`

Reference for the skills Hazel has access to: `boh-graph` (Neo4j queries) and `boh-dashboard` (queue writes, file processing, dashboard chat, message polling, preference sync). Includes the command signatures each skill exposes.

Same content across all firms. Copied at provisioning.

### `USER.md` — The Firm-Scoped Dynamic File

This is the one workspace file that is **genuinely per-firm and changes over time**. It holds the builder context that would otherwise be injected into a system prompt.

```
BUILDER CONTEXT:
- Firm ID: {{FIRM_ID}}
- Firm display name: {{FIRM_DISPLAY_NAME}}
- Firm phone: {{FIRM_PHONE}}
- Location: {{FIRM_CITY}}, {{FIRM_STATE}}
- Timezone: {{TIMEZONE}}
- Primary contact: {{SIGN_OFF_NAME}}, {{SIGN_OFF_TITLE}}
- Primary operating jurisdiction: {{PRIMARY_JURISDICTION}}
- Account age: {{ACCOUNT_AGE_DAYS}} days
- Approval dollar threshold: ${{APPROVAL_DOLLAR_THRESHOLD}}
- Change order review threshold: ${{CHANGE_ORDER_REVIEW_THRESHOLD}}
- Client follow-up window: {{CLIENT_FOLLOW_UP_DAYS}} days
- Communication tone: {{TONE}}
- Daily digest enabled: {{DAILY_DIGEST_ENABLED}}
- Hazel phone number: {{HAZEL_PHONE}} (status: {{HAZEL_PHONE_STATUS}})
```

**`USER.md` is a cache.** Supabase is the source of truth. Whenever a builder updates preferences in the dashboard (via `PUT /api/preferences` or `PATCH /api/firm`), the webhook backend must regenerate `USER.md` so the next agent turn sees the updated values.

The sync mechanism is described below.

### `HEARTBEAT.md`

Per-firm scheduled tasks. For now, empty for all firms. Will hold things like "run daily digest at 7:30am local" once that moves off the central cron.

---

## Per-Request Context (Prepended to User Message)

`hazel-plugin/ChatHandler` receives a webhook from Supabase when a builder sends a dashboard message, enriches it with context, and forwards to the agent. The enrichment produces a user-message prefix like this:

```
[PROJECT CONTEXT]
- Project: {{CURRENT_PROJECT_NAME}}
- Supabase project ID: {{CURRENT_PROJECT_ID}}
- Neo4j graph ID: {{GRAPH_PROJECT_ID}}
- PM: {{PM_NAME}}
- Project age: {{CURRENT_PROJECT_AGE_DAYS}} days
- Status: {{PROJECT_STATUS}}
- Contract value: ${{CONTRACT_VALUE}}
- Spent to date: ${{SPENT_TO_DATE}}
- Schedule variance: {{SCHEDULE_VARIANCE_DAYS}} days

[REQUEST METADATA]
- Channel: {{CHANNEL}} (dashboard_chat / clawdtalk_sms / clawdtalk_voice / email_forward)
- Input source: {{INPUT_SOURCE}} (typed_message / voice_memo / photo / forwarded_email)
- Received at: {{TIMESTAMP}} ({{TIMEZONE}})

[BUILDER MESSAGE]
{{RAW_MESSAGE_BODY}}
```

**Implementation note:** `graph_project_id` is the key used in all Neo4j Cypher queries. Always use this value — do not attempt to match by project name in the graph. If `graph_project_id` is null, the plugin still forwards the request; Hazel handles the fallback and logs a warning.

**What this prefix does NOT contain:**

- **Trust tier** — Hazel queries this on demand via `boh-dashboard` when it's ready to classify an action. Pre-injecting it would require the plugin to know what action Hazel is about to take, which is unknowable.
- **Action type** — same reason. Hazel decides the action type during its own reasoning.
- **Consecutive approvals / days since last edit** — same. These are lookup values the agent retrieves when it's deciding whether to auto-act or queue.
- **Builder/firm context** — already in `USER.md`, auto-injected by OpenClaw.

---

## The `USER.md` Sync Flow

The dashboard writes builder preferences to Supabase. `USER.md` on the droplet must stay in sync. The flow:

```
Builder updates preference in dashboard
    ↓
PUT /api/preferences (or PATCH /api/firm)
    ↓
Backend updates Supabase row
    ↓
Backend calls _regenerate_user_md(firm_id)
    ↓
Backend reads firm + preferences from Supabase
    ↓
Backend writes USER.md to /home/openclaw/.openclaw/workspace/hazel/builders/{slug}/USER.md
    ↓
Next agent turn sees updated values via OpenClaw auto-inject
```

`_regenerate_user_md()` uses the `USER.md` template above and substitutes values from the `firms` and `firm_preferences` tables. Write is atomic (write to temp file, `os.rename` into place) to prevent the agent reading a half-written file mid-update.

**Build order:** This regeneration is not yet implemented. It is a prerequisite for per-firm agents to pick up preference changes without a workspace rebuild. Until it ships, builders would need to edit `USER.md` by hand after any dashboard settings change — which won't scale past the first few firms.

The `boh-dashboard/scripts/sync_preferences.py` skill script already reads preferences from Supabase and generates a preferences file. This is the starting point — the backend just needs to invoke an equivalent function after any settings write.

---

## Provisioning Flow (New Firm)

When a firm completes onboarding (`POST /api/onboarding/complete`):

1. Firm is already created in Supabase (from `POST /api/firm/setup` during the wizard)
2. Preferences exist (from `PUT /api/preferences` during the wizard)
3. First project may exist (from `POST /api/projects` during the wizard)
4. **[Future]** Provisioning job runs:
   - Slugifies firm name → `firm-slug`
   - Creates `/home/openclaw/.openclaw/workspace/hazel/builders/{firm-slug}/`
   - Copies `SOUL.md`, `TRUST.md`, `AGENTS.md`, `TOOLS.md` from template
   - Templates `IDENTITY.md` with firm name
   - Generates `USER.md` from Supabase firm + preferences
   - Symlinks `skills/` to the shared skills directory
   - Creates empty `HEARTBEAT.md` and `memory/MEMORY.md`
   - Registers the agent in `openclaw.json` with ID `hazel-{firm-slug}`
   - Restarts OpenClaw to load the new agent
5. **[Current]** Onboarding sends an email to `jake@haventechsolutions.com` asking for manual provisioning + ClawdTalk number allocation

Step 4 is the `provision_firm.py` script on the `feature/provisioning-system` branch. Step 5 is the current stub. The plan is for step 5 to call step 4 once provisioning is validated.

---

## What Not to Do

### Don't try to pass a `system` parameter per request

OpenClaw owns the system prompt. Any attempt to override it per-request will fail or be ignored. All customization flows through workspace files and the user-message prefix.

### Don't interpolate `TRUST.md` with firm-specific values

The hard constraints file must remain a static, identical string across every firm's workspace. Firm-specific thresholds (dollar amounts, jurisdictions, etc.) live in `USER.md` and are **referenced** by the constraints — not substituted into them.

### Don't pre-inject trust tier or action type

These are runtime decisions Hazel makes during its own reasoning. The agent queries trust state via `boh-dashboard` when it's ready to act. Pre-injecting them into the prompt would require the caller to know Hazel's classification in advance, which is a chicken-and-egg problem.

### Don't let `USER.md` drift from Supabase

If a builder updates preferences in the dashboard and `USER.md` isn't regenerated, the agent will operate on stale context for that firm until the next manual sync. Every write path that touches firm preferences must invoke the regeneration function.

### Don't merge ClawdTalk and dashboard session context

ClawdTalk (SMS/voice) and dashboard chat are separate channels with separate session histories in OpenClaw. The dashboard session key is `hook:hazel:dashboard:{project_id}`. Do not carry phone conversation context into a dashboard session or vice versa. This is a hard constraint in `TRUST.md` and also an implementation rule in the `hazel-plugin` `CoreBridge`.

---

## Audit Log Correlation

Every agent action writes to `audit_log`. The `system_prompt_version` field on each entry must match the version of this template document, so historical log entries can be correlated with the prompt architecture that governed them.

When this template changes, bump the version below and update the version string in `hazel-plugin/CoreBridge.ts` so new audit log entries record the new version.

---

## Versioning

**Current version: `2.0.0 — 2026-04-15`**

**Breaking change from 1.x:** Replaced the "system parameter assembly" model with OpenClaw's native workspace-file injection model. Dropped Section 5 (Action Context) in favor of a slimmed "Request Metadata" block prepended to the user message. Split firm-scoped context into per-firm workspace files (`USER.md`) and per-request metadata. Introduced the `USER.md` sync flow as a hard requirement. Template is now an architecture document rather than a prompt-assembly spec; workspace files are the source of truth for content.

**Previous versions:**

- `1.2.0 — 2026-04-07` — Added `firm_id` and `firm_display_name` to Section 2. Updated version format to include date.
- `1.1.0` — Added Neo4j graph context section, channel separation constraint, boh-graph/boh-dashboard skill references, input source field. Aligned table names and status values with ARCHITECTURE.md.
