# Thornton ADU

**Graph ID:** PROJ-THORNTON-001
**Supabase ID:** a1a1a1a1-0000-0000-0000-000000000002
**Status:** Active — pre-construction, on track
**Address:** 1103 Cedar Ave, Kirkland, WA
**PM:** Marcus Webb
**Client:** James & Linda Thornton (CUST-THORNTON-001) — james.thornton@email.com

## Budget
- Contract value: $128,500
- Spent to date: $44,200 (34%) — Design & Permitting phase complete

## Timeline
- Design & Permitting: complete (Feb–Apr 2026)
- Construction start: May 5, 2026
- Estimated completion: Aug 22, 2026

## Schedule (query graph for live data)
```
MATCH (p:Project {project_id: 'PROJ-THORNTON-001'})-[:PROJECT_HAS_JOB]->(j:Job)
RETURN j.name, j.status, j.planned_start, j.planned_end, j.actual_start, j.actual_end
ORDER BY j.sort_order
```

Current state:
- Design & Permitting: complete
- All construction phases: not_started (kick off May 5)
- Permit: KLD-2026-00847

## Notes
- Estimate EST-THORNTON-001 accepted 2026-03-01
- Referred client
