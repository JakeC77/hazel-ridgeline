# BOH Graph Skill — Ridgeline Builders

Use this skill to query the builder's Neo4j knowledge graph.
Run queries via: `python3 skills/boh-graph/query.py "<cypher>"`
Results return as JSON. Always LIMIT large result sets.
Graph is READ-ONLY. Never write or delete.

---

## Connection
- URI: bolt://localhost:7687 (set BOH_NEO4J_URI to override)
- User: neo4j (set BOH_NEO4J_USER to override)
- Password: set BOH_NEO4J_PASSWORD env var

---

## Schema — Node Labels & Key Properties

**Company** (1 node)
  name, trade, region, owner_name, phone, email

**Customer** (13 nodes)
  id (CUST-NNN), name, email, phone, type (residential|commercial),
  payment_terms (net_15|net_30|net_45|due_on_receipt),
  source (referral|repeat|google|yard_sign|direct_outreach), status

**Vendor** (10 nodes)
  id (VEN-NNN), name, type (supplier|subcontractor|equipment_rental|professional_service),
  trade, phone, email, payment_terms, insurance_expiry, rating, w9_on_file

**Employee** (5 nodes)
  id (EMP-NNN), name, role (owner|foreman|journeyman),
  base_rate, burden_rate, bill_rate, status (active|terminated),
  hire_date, termination_date

**Project** (51 nodes) — central hub
  project_id (PROJ-UUID), name, archetype, type, status,
  site_address, start_date, end_date, actual_start, actual_end,
  contract_amount, markup_pct, retention_pct, retention_released,
  permit_required, permit_number

  Archetypes: repair_service, bathroom_remodel, kitchen_remodel,
              deck_addition, room_addition, new_construction, tenant_improvement

**Job** (279 nodes) — cost codes within projects
  job_id (JOB-UUID), project_id, code (e.g. 03-FRAMING), name,
  budgeted_labor_hours, budgeted_labor_cost, budgeted_material_cost,
  budgeted_sub_cost, status, actual_start, actual_end

**Estimate** (100 nodes)
  estimate_id, estimate_number (EST-NNNN), customer_id, archetype,
  status (sent|accepted|declined|expired), total, cost_estimate,
  markup_pct, created_at, sent_at, valid_until, accepted_at, project_id

**EstimateLineItem** (1173 nodes)
  line_id, estimate_id, cost_code, description, category (labor|material|subcontractor),
  unit_cost, unit_price, line_total

**TimeEntry** (1710 nodes)
  entry_id, employee_id, project_id, job_id, date,
  hours_regular, hours_overtime, cost, notes

**Bill** (745 nodes)
  bill_id, vendor_id, project_id (null=overhead), job_id,
  status, received_date, due_date, total, paid_date,
  category (material|subcontractor|rent|vehicles|utilities|software|insurance|tools)

**Invoice** (134 nodes)
  invoice_id, invoice_number (INV-NNNN), project_id, customer_id,
  type (progress|final|retention), status, issued_date, due_date,
  subtotal, retention_held, total_due

**Payment** (134 nodes)
  payment_id, invoice_id, project_id, customer_id,
  amount, method (ach|check|credit_card), received_date, deposited_date

**NarrativeEvent** (3 nodes)
  event_id, event_type (loc_draw|overtime_mandate|pricing_change),
  date, description, amount, event_metadata

---

## Schema — Relationships

```
(Customer)-[:HAS_ESTIMATE]->(Estimate)
(Customer)-[:HAS_PROJECT]->(Project)
(Estimate)-[:BECOMES_PROJECT]->(Project)
(Estimate)-[:HAS_LINE_ITEM]->(EstimateLineItem)
(EstimateLineItem)-[:MAPS_TO_JOB]->(Job)
(Project)-[:HAS_JOB]->(Job)
(Project)-[:HAS_INVOICE]->(Invoice)
(Project)-[:HAS_BILL]->(Bill)
(Job)-[:HAS_TIME_ENTRY]->(TimeEntry)
(Job)-[:HAS_BILL]->(Bill)
(Employee)-[:LOGS_TIME]->(TimeEntry)
(Vendor)-[:HAS_BILL]->(Bill)
(Invoice)-[:HAS_PAYMENT]->(Payment)
(Company)-[:EMPLOYS]->(Employee)
```

---

## Common Query Patterns

### Project status
```cypher
MATCH (p:Project {name: 'Morrison Kitchen'})
RETURN p.status, p.contract_amount, p.start_date, p.end_date
```

### Budget vs actual by job
```cypher
MATCH (p:Project)-[:HAS_JOB]->(j:Job)
WHERE p.name CONTAINS 'Morrison'
RETURN j.name, j.budgeted_labor_cost + j.budgeted_material_cost + j.budgeted_sub_cost AS budget,
       sum(j.budgeted_labor_hours) AS budgeted_hours
```

### Who's working what today
```cypher
MATCH (e:Employee)-[:LOGS_TIME]->(t:TimeEntry)-[:FOR_PROJECT]->(p:Project)
WHERE t.date = date()
RETURN e.name, p.name, t.hours_regular, t.notes
```

### Outstanding invoices (unpaid)
```cypher
MATCH (p:Project)-[:HAS_INVOICE]->(i:Invoice)
WHERE i.status <> 'paid'
RETURN p.name, i.invoice_number, i.total_due, i.due_date
ORDER BY i.due_date
```

### Bills due this week
```cypher
MATCH (b:Bill)
WHERE b.status <> 'paid' AND b.due_date <= date() + duration('P7D')
RETURN b.bill_id, b.total, b.due_date, b.category
ORDER BY b.due_date
```

### Job costing — actual vs estimate
```cypher
MATCH (p:Project)-[:HAS_JOB]->(j:Job)
OPTIONAL MATCH (j)-[:HAS_TIME_ENTRY]->(t:TimeEntry)
OPTIONAL MATCH (j)-[:HAS_BILL]->(b:Bill)
WITH p, j,
     coalesce(sum(t.cost), 0) AS actual_labor,
     coalesce(sum(b.total), 0) AS actual_materials
RETURN p.name, j.name,
       j.budgeted_labor_cost AS budget_labor, actual_labor,
       j.budgeted_material_cost AS budget_materials, actual_materials
```

### Historical cost by archetype
```cypher
MATCH (p:Project)-[:HAS_JOB]->(j:Job)
OPTIONAL MATCH (j)-[:HAS_BILL]->(b:Bill)
OPTIONAL MATCH (j)-[:HAS_TIME_ENTRY]->(t:TimeEntry)
WHERE p.archetype = 'kitchen_remodel'
WITH p, sum(coalesce(b.total,0)) + sum(coalesce(t.cost,0)) AS actual_cost
RETURN p.name, p.contract_amount, actual_cost,
       p.contract_amount - actual_cost AS margin
ORDER BY p.actual_end DESC LIMIT 10
```

### Vendor insurance expiring soon
```cypher
MATCH (v:Vendor)
WHERE v.insurance_expiry IS NOT NULL
  AND v.insurance_expiry <= date() + duration('P30D')
RETURN v.name, v.type, v.insurance_expiry
ORDER BY v.insurance_expiry
```

### Crew availability (no active time entries today)
```cypher
MATCH (e:Employee {status: 'active'})
WHERE NOT EXISTS {
  MATCH (e)-[:LOGS_TIME]->(t:TimeEntry)
  WHERE t.date = date()
}
RETURN e.name, e.role
```

---

## Response Guidelines
- Keep answers SHORT for voice/WhatsApp. Numbers, names, dates only.
- Offer "want more detail?" rather than dumping everything.
- If a query returns nothing, say so plainly — don't guess.
- Dollar amounts: round to nearest dollar, use $ prefix.
- Dates: speak as "March 18th" not "2026-03-18".
