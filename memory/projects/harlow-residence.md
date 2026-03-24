# Harlow Residence

**Graph ID:** PROJ-HARLOW-001
**Supabase ID:** a1a1a1a1-0000-0000-0000-000000000001
**Status:** At-risk — 4 days behind baseline
**Address:** 4820 Ridgeline Dr, Bellevue, WA
**PM:** Marcus Webb
**Client:** Sarah Harlow (CUST-HARLOW-001) — sarah.harlow@email.com

## Budget
- Contract value: $482,000
- Spent to date: $319,200 (66%)

## Schedule (query graph for live data)
```
MATCH (p:Project {name: 'Harlow Residence'})-[:PROJECT_HAS_JOB]->(j:Job)
RETURN j.name, j.status, j.actual_start, j.actual_end, j.planned_start, j.planned_end
ORDER BY j.sort_order
```

Current state:
- Foundation → Insulation: complete
- Drywall: in_progress (started 2026-03-17, 4 days behind plan)
- Finishes: not_started (planned 2026-03-24)
- Punch List: not_started (planned 2026-04-14)

## Owner Supplied Materials
- **Blinds** — logged 2026-03-23. File: blinds-IMG_1601.jpg (id: 64bede49-6566-4277-be42-10bbc31855fb). Exclude from Ridgeline material cost/billing.

## Open Items
- CO-005 Gas Fireplace ($4,800) — drafted, pending client approval
- Pacific NW Framing LLC invoice $47,200 — $2,700 over approved contract ($44,500)

## Communication Notes
- Sarah Harlow prefers SMS for approvals
