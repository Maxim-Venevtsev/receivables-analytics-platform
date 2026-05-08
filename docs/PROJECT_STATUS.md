
---

## docs/PROJECT_STATUS.md

```markdown
# PROJECT STATUS

## Current stage

Operational MVP ready for controlled demo.

The system already supports:
- operational receivables control
- overdue management
- upcoming payment monitoring
- hierarchical drill-down
- parent organization aggregation
- invoice-level analytics

---

# Implemented modules

## Dashboard
Status: READY

Features:
- KPI cards
- branch filtering
- receivables structure visualization
- client prioritization
- interactive navigation

---

## Overdue page
Status: READY

Features:
- overdue client monitoring
- risk prioritization
- action recommendations
- drill-down navigation

---

## Due today page
Status: READY

Features:
- due-today monitoring
- operational control workflow
- branch filtering
- client drill-down

---

## Due soon page
Status: READY

Features:
- upcoming payment visibility
- proactive monitoring
- operational prioritization

---

## Dynamics page
Status: READY

Features:
- historical debt deltas
- client-level changes
- sorting/filtering/search
- operational monitoring

---

## Client card
Status: READY

Features:
- KPI overview
- aging visualization
- invoice-level drill-down
- payment urgency visualization
- parent organization navigation

---

## Parent organization card
Status: READY

Features:
- aggregated monitoring
- consolidated debt visibility
- cross-client analysis
- invoice-level drill-down
- branch filtering

---

# Current architecture

TXT / Excel
    ↓
Python ingestion
    ↓
PostgreSQL
    ↓
SQL analytical views
    ↓
NiceGUI operational frontend

---

# Implemented SQL analytical layer

Current analytical views:

- v_dashboard_overview
- v_branch_summary
- v_client_priority
- v_client_deltas
- v_parent_org_summary
- v_parent_org_clients
- v_parent_org_invoices

---

# Current frontend state

Frontend already supports:

- unified navigation
- drill-down workflow
- interactive filtering
- clickable analytics
- sorting
- searching
- operational highlighting

---

# Current limitations

Current version is still MVP/demo-oriented.

Not yet implemented:

- authentication
- role model
- scheduled ETL
- production deployment
- automated backups
- user actions history
- comments/workflow tracking
- notification system
- real payment history integration

---

# Data status

Current demo uses:
- synthetic / demo-oriented data
- manually loaded snapshots
- limited historical depth

Further development requires:
- daily real exports
- longer historical accumulation
- real payment history
- credit limit data

---

# Planned next-stage features

## Operational analytics
- branch cards
- trend charts
- historical debt visualization
- rolling-period analysis

## Risk analytics
- payment discipline rating
- behavioral anomaly detection
- debt volatility analysis
- expected payment reliability

## Financial control
- credit limits
- free credit balance
- utilization monitoring

## Workflow layer
- comments
- promised payment dates
- responsible manager
- action history

## Technical
- deployment automation
- Dockerization
- backup strategy
- production hardening

---

# Demo readiness

Current build is suitable for:

- controlled business demo
- operational workflow validation
- UX testing
- stakeholder presentations
- portfolio showcase

---

# Recommended next steps

1. Create sanitized demo dataset
2. Deploy demo instance to lightweight server
3. Gather user feedback
4. Start daily snapshot accumulation
5. Begin production hardening phase