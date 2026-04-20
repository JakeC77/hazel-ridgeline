# Hazel Engineering Onboarding Guide
## How to Use the Behavioral Spec Files

**For:** [Engineer Name]
**From:** Robert / Haven Technology Solutions
**Date:** March 2026

This guide explains the specification files you have been given and how to use them together when building Hazel. Read this document before reading the spec files, and read the spec files before writing any code.

---

## What These Files Are

We have built a detailed product requirements document (`haven_trust_ux_requirements.docx`) that defines exactly how Hazel should behave — the trust model, the approval system, the audit log, the communication rules, and more. That document is written from a product perspective. The files below translate it into engineering inputs.

**`CLAUDE.md`** — This file lives in the project root. Claude Code reads it automatically at the start of every session and uses it to govern how it writes code. It defines architectural rules, naming conventions, patterns to follow, and decisions that have already been made. Think of it as standing instructions to the AI assistant doing the development work.

**`ARCHITECTURE.md`** — The system architecture document written by the lead engineer. It defines the full component topology: OpenClaw as the agent runtime, Supabase as the shared data layer, the dashboard frontend, the webhook shim, and the ClawdTalk messaging channel. It also contains the canonical database schema, data flow diagrams, build phase status, and realtime subscription patterns. Read this before touching any data layer code.

**`behavioral-spec.md`** — This is your primary reference during implementation. It translates the product requirements into data models, decision trees, TypeScript interfaces, and implementation notes. When you hit an ambiguous case, check here first.

---

## The System in One Paragraph

Hazel is an AI agent that runs on **OpenClaw** (the agent runtime on a Digital Ocean droplet). Builders interact with Hazel through two channels: **ClawdTalk** (SMS/voice, phone number +12066032566) and the **browser dashboard** (static HTML/Alpine.js hosted on GitHub Pages). Both channels write to and read from **Supabase**, which is the shared data layer. Project intelligence — schedules, budgets, subs, change order history, invoices — lives in Supabase tables (`projects`, `qbo_job_cost_cache`, `project_milestones`, `change_orders`, `invoices`) and is queried via the `boh-dashboard` skill. When Hazel needs to interact with the dashboard (write queue drafts, process files, handle chat messages), it uses the same `boh-dashboard` skill. The dashboard connects to Supabase directly via the JS client using realtime subscriptions. Dashboard chat messages reach Hazel through the `hazel-plugin` OpenClaw plugin, which enriches each turn with a `[FIRM CONTEXT]` block (firm name, tone, thresholds, jurisdictions) pulled fresh from Supabase per-turn.

---

## How to Use Each File

### CLAUDE.md

Place this file in the project root before starting any Claude Code session. Claude Code discovers and reads it automatically. You do not need to reference it in prompts.

What it does for you: it keeps Claude Code consistent across sessions. Architectural decisions made in week one will still be respected in week four because CLAUDE.md holds them. It also defines the "never do this" rules — patterns that would violate the trust model — so Claude Code will not accidentally build something that contradicts the product spec.

You should update CLAUDE.md when:
- A product decision is made that changes an architectural rule
- You resolve one of the open questions listed at the bottom of the file
- A new pattern or convention is established that should be followed consistently

Do not change CLAUDE.md to work around a product constraint. If a rule in CLAUDE.md feels like it is getting in the way, bring it to Robert before changing it.

### ARCHITECTURE.md

Read this before writing any data layer code, any agent integration code, or any webhook code. Key things to pull from it:

**Canonical table names.** The schema in ARCHITECTURE.md defines the exact column names, types, and status/type enum values for every table. Use these exactly — do not invent synonyms. The `queue_items` table uses `status` values `active`, `snoozed`, `approved`, `rejected` and `type` values `change-order`, `email`, `invoice`, `daily-log`.

**Build phase status.** ARCHITECTURE.md has a checklist of what is already done and what is not yet built. Check it before starting any new work to avoid duplicating completed work or building on an assumption that hasn't been wired up yet.

**Realtime subscription patterns.** The dashboard subscribes to `queue_items`, `files`, and `messages` via Supabase Realtime. The patterns are defined in ARCHITECTURE.md. Use them as-is.

**The dashboard chat path.** Dashboard chat is handled by the `hazel-plugin` OpenClaw plugin (endpoints `/hazel/chat`, `/hazel/email` on port 18789). The plugin fetches project info and firm context from Supabase on every turn and prepends them to the user message before forwarding to the agent. The Flask backend (`hazel-chat-webhook` on port 8700) is API-only now — no chat forwarding.

**File storage.** Files are stored in the `project-files` Supabase Storage bucket with the path structure `{project_id}/{category}/`. The dashboard uploads directly; Hazel accesses via service role key.

### behavioral-spec.md

This is the document you will reference most often during implementation. Key sections:

**Section 1 (Core Behavioral Model)** has the decision tree for every agent action. When you are implementing a new agent capability and are not sure whether something should go through the approval queue, walk it through the decision tree.

**Section 2 (Trust Tier Reference)** has the full tier definition, advancement rules, minimum time floors, and the permanently supervised action types. The permanently supervised list is important — those action types must never have tier advancement logic applied to them.

**Section 3 (Approval Queue)** has the TypeScript interface for queue items and the hold behavior implementation. Note that the `status` field uses `snoozed` (not `held`) to match the ARCHITECTURE.md schema. The card rendering rule is important for front-end work: the decision buttons must always be visible and tappable, even when the draft content is expanded.

**Section 4 (Client Communication Classification)** has the classification function structure and the routing rules by class. The specific NLP signals (delay language keywords, escalation signals) are an open question — implement the classification with a configurable pattern set so they can be tuned without code changes. Do not hardcode keyword lists.

**Section 5 (Audit Log)** has the full schema and write order. The write order matters: write the audit log entry before executing the action, then update it after. If the action fails, update the log entry with the error — never skip the write because something went wrong.

**Section 6 (Risk Detection)** has the risk category table with default thresholds. All thresholds must be stored in the database as configurable values — not hardcoded. The defaults from the table are what you seed for new accounts.

**Section 9 (Open Questions)** is the list of decisions that have not been made yet. If you encounter one of these during implementation, add a code comment flagging it and bring it to Robert. Do not make an independent call on any of them.

**Section 10 (Decision Log)** is where you record significant implementation decisions as you make them. Date, question, decision, who decided. This keeps the spec and the codebase in sync as the project evolves.

---

## The One Rule That Matters Most

Everything in these files serves one product principle: **Hazel drafts and queues; the builder decides.** No action leaves the system without either (a) passing through the `queue_items` approval queue, or (b) having been explicitly granted autonomous authority by the builder through the trust tier system.

If you find yourself writing a code path that bypasses the approval queue for any reason — performance, convenience, "it's just a low-stakes action" — stop and check the spec before proceeding. The staging layer is not optional plumbing. It is the product.

---

## What To Do When the Spec Doesn't Have the Answer

1. Check `behavioral-spec.md` first
2. Check `ARCHITECTURE.md` for system-level questions
3. Check `haven_trust_ux_requirements.docx` (the full product requirements document Robert can share)
4. If the question is in the Open Questions list, flag it and wait for a decision — do not guess
5. If the question is not in any of these documents, bring it to Robert with a specific framing: "I need to make a decision about X. The two options are A and B. My instinct is A because [reason]. Does that align with the product intent?"

The goal is not to slow down development. It is to make sure that the decisions made in the first two weeks of development do not have to be undone in week six because they conflicted with the product spec. These documents exist to make those conversations faster, not longer.

---

## File Locations in the Repository

```
/ (project root)
├── CLAUDE.md                                  ← Claude Code reads this automatically
├── ARCHITECTURE.md                            ← System architecture and canonical schema
├── SOUL.md                                    ← Hazel's identity, behavioral foundation
├── AGENTS.md                                  ← Startup orchestration and skill reference
├── TRUST.md                                   ← Trust tier model and hard constraints
├── USER.md                                    ← Builder context template (dynamic at runtime)
├── TOOLS.md                                   ← Platform-level tool credentials and endpoints
└── behavioral-spec.md                         ← Your primary implementation reference
```

Note: `behavioral-spec.md` is at the project root, not in a `docs/` subdirectory.
If you move it, update all cross-references in CLAUDE.md, ARCHITECTURE.md, and
engineer-guide.md accordingly.

Source of truth hierarchy when documents conflict:

1. `haven_trust_ux_requirements.docx` — behavioral and product rules
2. `ARCHITECTURE.md` — system architecture, table names, schema, build status
3. `behavioral-spec.md` — implementation-level decisions
4. `CLAUDE.md` — derived from the above; flag conflicts upward

---

## Questions

Reach out to Robert at robert@haventechsolutions.com. For product questions, include which section of the spec you are working from and what the specific ambiguity is. That framing will get you a faster answer.
