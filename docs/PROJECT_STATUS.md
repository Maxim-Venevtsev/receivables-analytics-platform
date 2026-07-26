# PROJECT STATUS

## Current stage

Status: **Production Foundation v1 completed and validated end to end**.

The system now supports:

- operational receivables control;
- overdue management;
- upcoming payment monitoring;
- hierarchical drill-down;
- parent organization aggregation;
- invoice-level analytics;
- configurable base client rating;
- Credit Quality Rating V2;
- complete historical Credit Quality tracking across the rebuilt snapshot history;
- rating history and Credit Quality migration analytics;
- parent-organization weighted Credit Quality portfolio rating;
- branch weighted Credit Quality portfolio rating;
- historical behavioral analytics;
- branch-level operational analytics;
- executive overview dashboard;
- executive management signal drill-down pages;
- green debt quality monitoring;
- hidden-risk client detection;
- weighted debt age analytics;
- branch executive risk profile;
- term-shift detection;
- invoice lifecycle and recent paid invoice analytics.
- Automation Layer: Mail Gateway and Orchestrator;
- restart-safe processing from mailbox to raw ingestion directory;
- backlog processing for both mail inbox and raw directory;
- scheduled hourly production ingestion and online dashboard refresh;
- production source-report archive;
- restart-safe Local Sync into the local development environment;
- dedicated read-only, chrooted SFTP-only access with no shell or write permission;
- SHA256 content identity, atomic transfer/handoff and manifest recovery;
- double-click manual Local Sync and dry-run launchers;
- isolated Historical Backfill Framework for atomic reconstruction of approved
  historical fact, rating and Credit Quality snapshots;
- validated matching latest snapshot dates and principal metrics between production and local dashboards.

Project timeline note:

- project scaffold appeared around **20 April 2026**;
- active product development accelerated around **20 May 2026**;
- by June 2026 the product reached an advanced local MVP stage with Credit Quality V2 implemented across core analytical views and main UI layers;
- after the June 2026 data-integrity rebuild, local and online work environments were synchronized on the validated historical database.
- by July 2026 the production automation, read-only Local Sync path and production/local validation formed Production Foundation v1.

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

Status: **READY — Credit Quality V2 integrated and synchronized online**

Implemented:

- executive KPI overview;
- Credit Quality V2 weighted portfolio rating;
- portfolio status / verdict;
- total debt and overdue dynamics;
- debt structure by day;
- reliable debt vs control-required debt;
- green debt maturity structure;
- weighted average debt-age trend;
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

## Recently completed major phases

## Historical Backfill Framework

Status: **COMPLETED, HARDENED AND POSTGRESQL-VALIDATED**

The project now includes an isolated maintenance framework for reconstructing
approved historical snapshot batches without changing scheduled ingestion or
production analytical views.

Implemented:

- complete-batch preflight and deterministic chronological processing;
- audited source-file SHA256 checks before database work;
- metadata-qualified matching for snapshots already present in the database;
- dry-run assessment with no write transaction;
- one atomic PostgreSQL transaction for fact loading and history reconstruction;
- isolated maintenance SQL for explicit snapshot dates;
- verified replacement of the affected history suffix only after complete staging;
- base client rating history reconstruction;
- Credit Quality history reconstruction, including historical term-shift isolation;
- idempotent no-op handling when available metadata and structural history match;
- explicit rejection of mixed, conflicting, incomplete and future-history states;
- rollback on fact, rating, Credit Quality or verification failure;
- preservation of normal current-snapshot production views;
- no persistent snapshot-context function, schema migration or maintenance object.

Validation:

- focused regression coverage for batch validation, transaction boundaries,
  structural completeness and failure handling;
- exact PostgreSQL parity between maintenance output and the canonical latest
  base-rating and Credit Quality production views;
- future-snapshot and future term-shift leakage tests;
- rollback verification through a new independent PostgreSQL connection;
- full automated test-suite validation.

Evidence boundary:

- approved source files are cryptographically checked before maintenance starts;
- existing database facts can be matched only by report date, source filename,
  loaded status, metadata row count and fact row count;
- `raw.snapshot_loads` does not store SHA256, so cryptographic identity of
  already-loaded database rows cannot be claimed.

Architecture boundary:

- normal scheduled ingestion remains unchanged;
- production analytical views remain unchanged;
- the framework is an explicitly invoked maintenance path, not an alternative
  scheduler or ingestion pipeline.

---

## Production Foundation v1

Status: **COMPLETED AND VALIDATED WITH PRODUCTION REPORTS**

Completed:

- production Mail Gateway and restart-safe Orchestrator;
- hourly scheduled production ingestion;
- PostgreSQL and online dashboard refresh through the existing ingestion pipeline;
- durable production source-report archive;
- archive publication with explicit file mode `0644`;
- persistent read-only archive view for synchronization;
- dedicated chrooted SFTP-only identity with no shell and no write access;
- native Windows OpenSSH Local Sync;
- SHA256 content identity and duplicate/alias handling;
- atomic `.part` download and atomic RAW handoff;
- versioned manifest, corruption recovery and reconciliation with local inbox/raw/archive/failed directories;
- manual PowerShell and CMD launchers for normal and dry-run synchronization;
- real production-to-local end-to-end validation;
- matching production/local latest snapshot dates and principal dashboard metrics.

Operational boundary:

- production refresh is automatic and scheduled;
- local development synchronization is deliberately manual;
- local development never reads Yahoo Mail;
- production remains the source of truth for incoming source reports.

## Production MVP Deployment v1

Status: **COMPLETED**

The private work deployment is now live:

- URL: `https://work.maximvenevtsev.com`;
- release tag: `work-deploy-v1`;
- private GitHub remote: `work`;
- server: Ubuntu 24.04 VPS, `83.220.168.3`;
- work app directory: `/home/deploy/receivables-work`;
- systemd service: `receivables-work`;
- database: `receivables_work`;
- app port: `8081`;
- access protection: Nginx Basic Auth;
- HTTPS: Let's Encrypt certificate for `work.maximvenevtsev.com`;
- dashboard shows latest snapshot date from the database;
- browser title is `Кофточки+`;
- favicon is enabled;
- June 2026 validated local database was promoted to the online work stand after content-level debt-balance checks.

The existing public demo remains available at `https://demo.maximvenevtsev.com` with anonymized/generated data.

Remaining stabilization tasks:

- daily PostgreSQL backups;
- restore test;
- password rotation;
- monitoring and failure notifications beyond current logs.

---

## Automation Layer — Mail Gateway and Orchestrator

Status: **DEPLOYED, SCHEDULED HOURLY AND VALIDATED END TO END**

Purpose:

Create a safe automation layer before the existing ingestion pipeline without changing ingestion business logic.

Implemented architecture:

```text
Yahoo Mail
    ↓
ARS Reports
    ↓
Mail Gateway
    ↓
mail_inbox
    ↓
Orchestrator
    ↓
raw_work
    ↓
Existing ingestion pipeline
    ↓
archive_work / failed_work
    ↓
PostgreSQL
    ↓
Dashboard
```

Completed:

- Mail Gateway standalone pre-ingestion layer;
- Yahoo IMAP authentication through App Password;
- configurable source / processed / failed mailbox folders;
- sender whitelist;
- attachment extension whitelist;
- SHA256 duplicate detection;
- manifest-based idempotency;
- structured JSONL logging;
- dry-run mode;
- processed / failed routing;
- backlog-safe processing of existing inbox files;
- restart-safe Orchestrator;
- safe handoff from `MAIL_INBOX_DIR` to raw ingestion directory;
- RAW directory treated as the source of truth for ingestion execution;
- existing ingestion triggered only when eligible raw files exist;
- support for `--dry-run`, `--skip-mail`, `--skip-ingestion` and `--limit`;
- end-to-end production pipeline successfully validated;
- hourly scheduled execution and online dashboard refresh;
- production archive publication for every successfully processed source report.

Important boundary:

The Automation Layer does not modify parsing, mapping, rating, SQL views or existing ingestion business logic.

---

## Credit Quality Rating V2

Status: **COMPLETED AND HISTORICALLY REBUILT**

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
- complete `client_credit_quality_history` snapshots for all rebuilt report dates;
- Credit Quality migration analytics based on historical Credit Quality values;
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

Status: **DEPLOYED AS PRIVATE PRODUCTION MVP V1 — DATA REBUILT AND SYNCHRONIZED**

Implemented:

- separate local work database: `debt_management_work`;
- server work database: `receivables_work`;
- `.env`-driven ingestion configuration;
- isolated raw work directory;
- incremental ingestion workflow;
- archive / failed-file workflow;
- latest-snapshot operational views;
- validated rebuild from archived reports;
- corrected current-balance mapping from source column `Просрочено, руб`;
- local and online work databases synchronized after validation.

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
Yahoo Mail
    ↓
Mail Gateway
    ↓
mail_inbox
    ↓
Orchestrator
    ↓
raw_work
    ↓
Python ingestion
    ↓
PostgreSQL
    ↓
SQL analytical views
    ↓
Online NiceGUI dashboard
    ↓
Production archive
    ↓
Read-only SFTP
    ↓
Local Sync (manual)
    ↓
local raw_work → existing ingestion → local PostgreSQL
    ↓
Local development dashboard
```

---

## Current limitations

Not yet implemented:

- role model;
- automated backups;
- documented restore testing;
- user action history;
- comments/workflow tracking;
- notification system;
- real payment history integration;
- credit limits;
- credit policy action workflow.
- automation health checks, proactive notifications and operational status page;
- performance engineering and load characterization.

---

## Data status

Current work environment uses real operational datasets loaded into both the local work database and the private online work database.

The June 2026 data-integrity rebuild corrected a critical ingestion mapping issue: `invoice_amount` now represents the current outstanding balance from source column `Просрочено, руб`, not the original invoice amount from `Сумма накладной`. This means partial payments are reflected correctly and portfolio totals may differ materially from earlier releases even when row counts and snapshot dates are unchanged.

Validated rebuilt history:

- 26 historical report snapshot dates;
- complete `core.client_rating_history` across all rebuilt dates;
- complete `core.client_credit_quality_history` across all rebuilt dates;
- corrected rating and Credit Quality migration history;
- synchronized local and online work environments.

Current limitations:

- historical depth is still limited to the available archived reports;
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

## Recommended next steps

1. Begin Performance Engineering as the next active technical phase.
2. Add scheduled daily PostgreSQL backups and retention.
3. Perform and document a restore test.
4. Add automation health checks, failure notifications and an operational status view.
5. Define application-level roles beyond current perimeter authentication.
6. Continue snapshot accumulation and Credit Quality V2 observation.


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
- Data-integrity rebuild using current outstanding balance from `Просрочено, руб`.
- Complete base rating and Credit Quality history for all 26 rebuilt snapshots.
- Credit Quality-based rating migration restored across the full rebuilt history.
- Weighted debt age chart in Executive Overview.
- Default sorting standardized on dashboard and operational client tables.
- Online work stand synchronized with the validated local database.

Current deployment target:

- private production MVP at `https://work.maximvenevtsev.com`
