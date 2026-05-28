
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
- configurable client payment discipline rating
- reusable rating UI component
- rating visibility across operational client tables
- isolated work database for real-data validation
- incremental ingestion workflow
- historical behavioral analytics
- branch-level operational analytics

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
- branch-card navigation

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
- historical debt analytics
- behavioral indicators
- historical debt structure analysis
- reactive period filtering

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
- v_client_rating_base
- v_client_rating
- v_client_daily_history
- v_parent_org_daily_history
- v_branch_daily_history

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
- reusable branch filtering component
- multi-select branch filtering
- synchronized KPI recalculation
- synchronized aging visualization
- reusable frontend widgets
- unified operational filtering behavior
- reusable Plotly analytics layer
- reusable historical KPI components
- reusable behavioral indicator layer

---

# Recently implemented

## Real-data work environment

Status: READY LOCALLY

Implemented:
- separate local work database: `debt_management_work`
- `.env`-driven ingestion configuration
- isolated raw work directory
- incremental ingestion workflow
- historical behavioral analytics
- branch-level operational analytics
- file archive / failed-file workflow
- latest-snapshot operational views

## Client payment discipline rating

Status: READY LOCALLY

Implemented:
- YAML-configurable rating rules
- PostgreSQL rating configuration tables
- rolling-window rating base view
- final client rating view
- LOW / MEDIUM / FULL confidence levels
- colored star rendering
- reusable rating UI component

Rating is currently shown in:
- Client card
- Dashboard operational client queue
- Dynamics client changes table
- Overdue clients table
- Due today clients table
- Due soon clients table
- Parent organization counterparties table

## Frontend filtering refactor

Status: READY

Implemented:
- reusable branch filter component
- multi-select branch filtering
- synchronized dashboard KPI recalculation
- synchronized aging visualization
- unified filtering logic across operational pages
- reusable frontend filtering architecture

## PHASE 2 — Historical Behavioral Analytics Layer

Status: READY

Implemented:
- client historical analytics
- parent-organization historical analytics
- branch historical analytics
- reusable Plotly chart components
- operational debt structure visualization
- reactive period filtering (28 / 90 / 180 / All)
- behavioral interpretation indicators
- historical KPI summaries
- branch drill-down navigation
- reusable frontend analytics architecture

Behavioral indicators currently include:
- debt trend analysis
- overdue behavior analysis
- volatility indicators
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

## Advanced behavioral analytics
- rating dynamics
- behavioral anomaly detection
- predictive collection risk indicators
- payment behavior profiling

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

1. Continue daily snapshot accumulation
2. Validate behavioral indicators on longer history
3. Implement rating dynamics
4. Prepare executive overview dashboard
5. Begin production hardening phase