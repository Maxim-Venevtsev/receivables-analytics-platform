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
- client rating history snapshots
- client rating dynamics
- parent-organization weighted portfolio rating
- branch weighted portfolio rating
- executive overview dashboard
- executive management signal drill-down pages
- green debt quality monitoring
- hidden-risk client detection
- branch executive risk profile

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
- rating dynamics strip

---

## Parent organization card
Status: READY

Features:
- aggregated monitoring
- consolidated debt visibility
- cross-client analysis
- invoice-level drill-down
- branch filtering
- weighted portfolio rating
- portfolio rating dynamics

---

## Branch card
Status: READY

Features:
- branch-level monitoring
- branch KPI overview
- branch aging structure
- historical debt analytics
- historical debt structure analysis
- behavioral indicators
- client and invoice drill-down
- weighted portfolio rating
- portfolio rating dynamics

---


## Executive Overview Dashboard
Status: READY LOCALLY

Features:
- executive KPI overview
- portfolio status / verdict
- total debt and overdue dynamics
- debt structure by day
- reliable debt vs debt requiring control
- green debt maturity structure by payment-term buckets
- weighted average payment-term trend
- long green exposure trend
- rating-bin exposure analysis
- management signal cards
- drill-down navigation from management signals

Implemented drill-down pages:
- /executive/long-green
- /executive/overdue
- /executive/branches
- /executive/hidden-risk
- /executive/term-shifts

The Executive layer is designed for company owners / senior managers and focuses on portfolio quality, hidden risk and branch-level accountability.

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
- client_rating_history
- v_client_rating_dynamics
- v_client_rating_latest_dynamics
- v_client_rating_change_events
- v_parent_org_rating_dynamics
- v_branch_rating_dynamics
- v_client_daily_history
- v_parent_org_daily_history
- v_branch_daily_history
- v_executive_overview_kpi
- v_executive_portfolio_daily_history
- v_executive_green_debt_maturity_history
- v_executive_payment_term_history
- v_executive_long_green_exposure
- v_executive_rating_exposure
- v_executive_branch_health
- v_executive_long_green_clients
- v_executive_long_green_invoices
- v_executive_overdue_clients
- v_executive_hidden_risk_clients
- v_term_shift_events
- v_term_shift_invoice_summary
- v_executive_term_shift_clients
- v_invoice_snapshot_lifecycle
- v_recent_paid_invoices

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
- reusable rating dynamics component
- reusable executive charts
- executive drill-down pages
- management signal navigation
- contextual return navigation from client and branch cards

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
- client rating history snapshots
- client rating dynamics
- parent-organization weighted portfolio rating
- branch weighted portfolio rating
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
- reactive period filtering
- rating dynamics strip (28 / 90 / 180 / All)
- behavioral interpretation indicators
- historical KPI summaries
- branch drill-down navigation
- reusable frontend analytics architecture

Behavioral indicators currently include:
- debt trend analysis
- overdue behavior analysis
- volatility indicators


## PHASE 3.1 — Rating Dynamics Layer

Status: READY

Implemented:
- client rating history table
- automatic rating snapshot creation during ingestion
- client rating dynamics views
- latest client rating dynamics view
- rating change events view
- client card rating dynamics strip
- parent-organization weighted portfolio rating
- branch weighted portfolio rating
- reusable rating dynamics frontend component

This phase turns the rating engine from a current-state score into a historical behavioral monitoring layer.---

## PHASE 3.2 — Executive Risk Signals & Invoice Lifecycle

Status: READY LOCALLY

Implemented:

### Executive management signals

- long-green exposure monitoring
- overdue exposure monitoring
- hidden-risk client detection
- branch health monitoring
- payment-term extension monitoring
- management signal drill-down navigation

Implemented drill-down pages:

- /executive/long-green
- /executive/overdue
- /executive/branches
- /executive/hidden-risk
- /executive/term-shifts

### Invoice lifecycle analytics

Implemented:

- invoice lifecycle view
- payment event detection
- full payment detection
- partial payment detection
- due-date extension integration
- actual payment-term estimation

### Client payment behavior analytics

Implemented:

- recent payment events block
- full and partial payment visualization
- actual vs contractual payment-term analysis
- delay vs due-date monitoring
- paid-invoice term-shift indicators

This phase provides the foundation for future credit-quality ratings and payment-behavior analytics.

# Next active milestone

## Executive Overview Dashboard
Status: READY LOCALLY

Implemented capabilities:
- portfolio quality overview
- rating distribution
- overdue dynamics
- green debt quality monitoring
- branch health monitoring
- executive KPI layer
- management signal drill-down

Next active milestone

## Credit Policy Monitoring (ARS_New / НО)
Status: IN DESIGN

Planned capabilities:

- ARS_New exposure monitoring
- НО exposure monitoring
- client migration between analytics
- cash-sale bypass detection
- branch-level policy monitoring
- parent-organization policy monitoring
- early-stage credit-risk detection

Future improvements:

- bubble matrix: rating × payment term × amount
- branch-level green debt maturity charts
- rating v2 (credit-quality rating)
- portfolio credit-quality score
- production deployment

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
- rating trend visualization
- downgrade / upgrade alerts
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
2. Validate behavioral indicators and rating dynamics on longer history
3. Implement term-shift detection for manual due-date extensions
4. Add rating × payment-term × amount bubble matrix
5. Design downgrade / upgrade alert logic
6. Begin production hardening phase