# PROJECT STATUS

## Current stage

Status: **Advanced operational MVP / controlled-demo ready locally**.

The system now supports:

- operational receivables control;
- overdue management;
- upcoming payment monitoring;
- hierarchical drill-down;
- parent organization aggregation;
- invoice-level analytics;
- configurable base client rating;
- Credit Quality Rating V2;
- rating history and migration analytics;
- parent-organization weighted Credit Quality portfolio rating;
- branch weighted Credit Quality portfolio rating;
- historical behavioral analytics;
- branch-level operational analytics;
- executive overview dashboard;
- executive management signal drill-down pages;
- green debt quality monitoring;
- hidden-risk client detection;
- branch executive risk profile;
- term-shift detection;
- invoice lifecycle and recent paid invoice analytics.

Project timeline note:

- project scaffold appeared around **20 April 2026**;
- active product development accelerated around **20 May 2026**;
- by June 2026 the product reached an advanced local MVP stage with Credit Quality V2 implemented across core analytical views and main UI layers.

---

## Implementation status by module

### Dashboard

Status: **READY**

Implemented:

- KPI cards;
- branch filtering;
- receivables structure visualization;
- client prioritization;
- clickable navigation;
- branch-card navigation.

### Overdue page

Status: **READY**

Implemented:

- overdue client monitoring;
- risk prioritization;
- action recommendations;
- drill-down navigation.

### Due today page

Status: **READY**

Implemented:

- due-today monitoring;
- operational control workflow;
- branch filtering;
- client drill-down.

### Due soon page

Status: **READY**

Implemented:

- upcoming payment visibility;
- proactive monitoring;
- operational prioritization.

### Dynamics page

Status: **READY**

Implemented:

- historical debt deltas;
- client-level changes;
- sorting / filtering / search;
- operational monitoring.

### Client Card

Status: **READY — Credit Quality V2 integrated**

Implemented:

- KPI overview;
- Credit Quality V2 rating card;
- Credit Quality severity strip;
- rating migration strip;
- aging visualization;
- invoice-level drill-down;
- payment urgency visualization;
- parent organization navigation;
- branch navigation;
- historical debt analytics;
- behavioral indicators;
- historical debt structure analysis;
- reactive period filtering;
- active invoices table;
- recent paid invoices table;
- term-shift markers.

### Parent Organization Card

Status: **READY — Credit Quality V2 integrated**

Implemented:

- aggregated monitoring;
- consolidated debt visibility;
- cross-client analysis;
- weighted Credit Quality V2 portfolio rating;
- portfolio rating dynamics strip;
- aging structure;
- historical analytics;
- counterparties table;
- active invoices table;
- recent paid invoices table;
- navigation to clients and branches.

### Branch Card

Status: **READY — Credit Quality V2 integrated**

Implemented:

- branch-level monitoring;
- branch KPI overview;
- 90+ non-overdue KPI;
- 120+ non-overdue KPI;
- weighted Credit Quality V2 portfolio rating;
- branch aging structure;
- historical debt analytics;
- historical debt structure analysis;
- behavioral indicators;
- client quality exposure block;
- counterparties table;
- active invoices table;
- recent paid invoices table;
- navigation to clients and parent organizations.

### Executive Overview Dashboard

Status: **READY LOCALLY — Credit Quality V2 integrated**

Implemented:

- executive KPI overview;
- Credit Quality V2 weighted portfolio rating;
- portfolio status / verdict;
- total debt and overdue dynamics;
- debt structure by day;
- reliable debt vs control-required debt;
- green debt maturity structure;
- weighted average payment-term trend;
- long green exposure trend;
- Credit Quality exposure chart;
- rating migration analytics;
- risk bubble chart;
- hidden-risk bubble chart;
- TOP-20 concentration bubble chart;
- management signal cards;
- drill-down navigation.

Implemented drill-down pages:

- `/executive/long-green`
- `/executive/overdue`
- `/executive/branches`
- `/executive/hidden-risk`
- `/executive/term-shifts`
- `/executive/rating-migration`

### Executive Branch Health Page

Status: **READY — Credit Quality V2 integrated**

Implemented:

- branch table with total debt;
- overdue debt and overdue share;
- long green exposure buckets;
- weighted Credit Quality branch rating;
- base weighted rating;
- severity portfolio penalty;
- branch drill-down navigation.

---

## Recently completed major phase

## Credit Quality Rating V2

Status: **COMPLETED LOCALLY**

Purpose:

Move from an overdue-only rating concept toward broader credit-quality scoring.

Implemented:

- updated YAML rating configuration;
- Credit Quality base and severity SQL layer;
- long green debt signals;
- weighted average payment-term signal;
- maximum payment-term signal;
- term-shift severity;
- repeated term-shift severity;
- exposure-based severity multiplier;
- `credit_quality_stars` calculation;
- `credit_quality_display_label`;
- `severity_level`;
- `severity_penalty`;
- `severity_reasons`;
- Credit Quality strip in Client Card;
- Credit Quality exposure chart in Executive Overview;
- Credit Quality exposure chart in Branch Card;
- Credit Quality weighted portfolio rating for parent organizations;
- Credit Quality weighted portfolio rating for branches;
- Credit Quality weighted portfolio rating in Executive Overview;
- Credit Quality-based executive bubble charts;
- Credit Quality-based Executive Branch Health page.

Key files added / updated:

- `configs/client_rating_rules.yaml`
- `configs/client_rating_rules_prev.yaml`
- `sql/ddl/023_credit_quality_rating_v2.sql`
- `sql/ddl/024_rating_v2_term_shift_severity.sql`
- `sql/ddl/025_update_parent_org_credit_quality_dynamics.sql`
- `sql/ddl/026_update_branch_credit_quality_dynamics.sql`
- `sql/ddl/027_update_executive_credit_quality_views.sql`
- `src/app/components/credit_quality_strip.py`
- `src/app/components/charts.py`
- `src/app/pages/client_card.py`
- `src/app/pages/parent_org_card.py`
- `src/app/pages/branch_card.py`
- `src/app/pages/executive.py`
- `src/app/pages/executive_branches.py`

Validated examples:

- large disciplined client remains high-quality;
- clients with repeated extensions are downgraded;
- formally non-overdue but extremely long debt is surfaced as hidden risk;
- parent-organization rating reflects exposure concentration rather than simple client count.

---

## Other completed phases

### Real-data work environment

Status: **READY LOCALLY**

Implemented:

- separate local work database: `debt_management_work`;
- `.env`-driven ingestion configuration;
- isolated raw work directory;
- incremental ingestion workflow;
- archive / failed-file workflow;
- latest-snapshot operational views.

### Base client payment discipline rating

Status: **READY / superseded by Credit Quality V2 in major analytical layers**

Implemented:

- YAML-configurable rating rules;
- PostgreSQL rating configuration tables;
- rolling-window rating base view;
- final client rating view;
- LOW / MEDIUM / FULL confidence levels;
- colored star rendering;
- reusable rating UI component;
- daily rating snapshots.

The base rating remains useful as an input into Credit Quality V2.

### Frontend filtering refactor

Status: **READY**

Implemented:

- reusable branch filter component;
- multi-select branch filtering;
- synchronized dashboard KPI recalculation;
- synchronized aging visualization;
- unified filtering logic across operational pages.

### Phase 2 — Historical Behavioral Analytics Layer

Status: **READY**

Implemented:

- client historical analytics;
- parent-organization historical analytics;
- branch historical analytics;
- reusable Plotly chart components;
- operational debt structure visualization;
- reactive period filtering;
- behavioral interpretation indicators;
- historical KPI summaries.

### Phase 3.1 — Rating Dynamics Layer

Status: **READY**

Implemented:

- client rating history table;
- automatic rating snapshot creation during ingestion;
- client rating dynamics views;
- latest client rating dynamics view;
- rating change events view;
- client card rating dynamics strip;
- parent-organization weighted portfolio rating;
- branch weighted portfolio rating;
- reusable rating dynamics frontend component.

### Phase 3.2 — Executive Risk Signals & Invoice Lifecycle

Status: **READY LOCALLY**

Implemented:

- executive management signals;
- long-green exposure monitoring;
- overdue exposure monitoring;
- hidden-risk detection;
- branch health monitoring;
- term-shift monitoring;
- invoice lifecycle view;
- payment event detection;
- full payment detection;
- partial payment detection;
- actual payment-term estimation;
- recent paid invoice blocks.

### Phase 3.3 — Payment behavior analytics

Implemented:

- payment behavior strip on Client Card
- usual payment window estimation
- early / normal / late payment classification
- payment expectation signals for active invoices
- invoice-age monitoring
- actual payment behavior profiling

---

## Current architecture

```text
TXT / Excel
    ↓
Python ingestion
    ↓
PostgreSQL
    ↓
SQL analytical views
    ↓
NiceGUI operational frontend
```

---

## Current limitations

Not yet implemented:

- production authentication;
- role model;
- scheduled ETL;
- production deployment of real environment;
- automated backups;
- user action history;
- comments/workflow tracking;
- notification system;
- real payment history integration;
- credit limits;
- credit policy action workflow.

---

## Data status

Current work environment uses real operational datasets loaded into a local work database.

Current limitations:

- historical depth is still limited;
- rating confidence and migration analytics will become stronger as daily snapshots accumulate;
- real payment history is inferred from snapshot changes rather than imported from actual payment transactions.

---

## Demo readiness

Current build is suitable for:

- controlled business demo;
- operational workflow validation;
- UX testing;
- stakeholder presentations;
- portfolio showcase;
- discussion of production deployment.

---

## Recommended immediate next steps

1. Commit documentation update after Credit Quality V2 implementation.
2. Continue daily snapshot accumulation.
3. Validate Credit Quality V2 on real examples for 1–2 weeks.
4. Tune YAML thresholds based on observed false positives / false negatives.
5. Start production deployment preparation for password-protected real-data environment.
6. Decide whether to push current local commits to remote, depending on repository privacy and deployment workflow.


---

## June 2026 release update

Completed:

- Branch Table refactor.
- Unified operational page layouts.
- Payment Attention page.
- Term Shifts page.
- Executive Branch Health improvements.
- Executive portfolio bucket correction.
- Contract payment-term outlier handling.
- Recent paid invoice behavior analytics.
- Correct date and numeric sorting across reusable tables.

Current deployment target:

- password-protected production deployment on maximvenevtsev.com
