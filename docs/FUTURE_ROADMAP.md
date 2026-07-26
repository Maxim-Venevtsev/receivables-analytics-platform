# Future Roadmap

This roadmap is structured by implementation status and product layer. Production Foundation v1 is complete; Performance Engineering is the next active technical phase.

Project timeline note:

- project initiated around **20 April 2026**;
- active development started around **20 May 2026**;
- Credit Quality Rating V2 was implemented in June 2026;
- the June 2026 data-integrity rebuild corrected current-balance mapping, restored full rating histories and synchronized the online work stand with the validated local database.
- the Automation Layer, production schedule, source archive and Local Sync workflow have been deployed and validated with real production reports.

---

# 1. Completed / ready locally

## 1.0 Production MVP Deployment v1

Status: **COMPLETED**

Implemented:

- private work deployment at `https://work.maximvenevtsev.com`;
- release tag: `work-deploy-v1`;
- isolated work application directory: `/home/deploy/receivables-work`;
- isolated work database: `receivables_work`;
- systemd service: `receivables-work`;
- Nginx reverse proxy on port `8081`;
- Nginx Basic Auth protection;
- HTTPS with Let's Encrypt;
- real operational snapshots loaded into the work database;
- dashboard latest snapshot date;
- work browser title and favicon.

The existing public demo remains available at `https://demo.maximvenevtsev.com` on the separate demo environment.

---

## 1.1 Operational MVP

Status: **READY**

Implemented:

- dashboard KPI layer;
- overdue monitoring;
- due-today monitoring;
- due-soon monitoring;
- Dynamics page;
- client-level drill-down;
- branch-level drill-down;
- parent-organization drill-down;
- invoice-level tables;
- reusable navigation;
- branch filtering;
- multi-select branch filtering.

Purpose:

Provide daily operational visibility over receivables and collection priorities.

---

## 1.2 Historical Behavioral Analytics Layer

Status: **READY**

Implemented:

- client historical charts;
- parent-organization historical charts;
- branch historical charts;
- debt structure by day;
- 28 / 90 / 180 / All period selector;
- behavioral indicators;
- reusable chart components.

Purpose:

Move the system from static current-state reporting to historical behavioral analysis.

---

## 1.3 Base Client Rating

Status: **READY / retained as foundation**

Implemented:

- YAML-driven rating rules;
- PostgreSQL rating configuration;
- base rating views;
- confidence levels;
- rating stars UI;
- rating history snapshots;
- rating dynamics views.

Current role:

The base rating remains the foundation for Credit Quality V2 and rating migration analytics.

---

## 1.4 Rating Dynamics and Migration Layer

Status: **READY — BASE AND CREDIT QUALITY HISTORY RESTORED**

Implemented:

- client rating history;
- automatic rating snapshots after ingestion;
- latest rating dynamics;
- rating change event view;
- rating migration drill-down page;
- Credit Quality-based rating migration chart and table;
- complete Credit Quality history across the rebuilt snapshot period;
- client rating migration strip;
- weighted parent and branch rating strips.

Purpose:

Track base rating movement and Credit Quality movement for improved, worsened, stable and newly rated clients.

Important note:

Daily snapshot-to-snapshot movement is noisy. Current rating migration methodology compares rating at the beginning and end of selected periods.

Supported periods:

- 28 days;
- 90 days;
- 180 days;
- all available history.

---

## 1.5 Invoice Lifecycle Analytics

Status: **READY LOCALLY**

Implemented:

- invoice lifecycle view;
- estimated payment event detection;
- full payment detection;
- partial payment detection;
- active invoices excluded from false full-payment detection;
- actual payment-term estimation;
- delay vs due date;
- recent paid invoices block on Client Card;
- recent paid invoices block on Parent Organization Card;
- recent paid invoices block on Branch Card.

Purpose:

Analyze how invoices actually move through the collection process, not just how open debt looks today.

---

## 1.6 Term-shift Detection

Status: **READY LOCALLY**

Implemented:

- due-date extension detection;
- invoice-level term-shift summary;
- term-shift markers in active invoice tables;
- term-shift markers in recent paid invoice tables;
- executive term-shift drill-down page;
- repeated shift detection used in Credit Quality V2.

Purpose:

Detect cases where risk is kept outside overdue buckets by moving due dates.

---

## 1.7 Executive Overview Dashboard

Status: **READY LOCALLY**

Implemented:

- portfolio KPI cards;
- portfolio status / verdict;
- total debt and overdue history;
- debt structure history;
- reliable vs control-required debt;
- green debt maturity chart;
- weighted debt-age trend;
- weighted payment-term trend;
- long green exposure trend;
- Credit Quality exposure chart;
- rating migration analytics;
- management signal cards;
- executive drill-down pages.

Implemented drill-down pages:

- `/executive/long-green`
- `/executive/overdue`
- `/executive/branches`
- `/executive/hidden-risk`
- `/executive/term-shifts`
- `/executive/rating-migration`

---

## 1.8 Executive Risk Concentration Analytics

Status: **READY LOCALLY**

Implemented:

### Risk bubble chart

- X-axis: weighted average payment term;
- Y-axis: Credit Quality Rating;
- bubble size: total debt;
- color: overdue severity.

### Hidden-risk bubble chart

- X-axis: share of 90+ green debt;
- Y-axis: Credit Quality Rating;
- bubble size: total debt;
- color: hidden-risk level.

### TOP-20 bubble chart

- same axes as main risk bubble chart;
- limited to 20 largest debtors;
- shows concentration of exposure and risk.

Purpose:

Help management identify large exposures, hidden risk and portfolio concentration quickly.

---

## 1.9 Credit Quality Rating V2

Status: **COMPLETED, HISTORICALLY REBUILT AND DEPLOYED TO WORK STAND**

Implemented:

- base rating input;
- severity model;
- long payment-term signals;
- 90+ and 120+ non-overdue debt signals;
- term-shift severity;
- repeated shift severity;
- exposure segment and multiplier;
- `credit_quality_stars`;
- severity reasons;
- severity penalty;
- Credit Quality UI strip;
- parent-organization weighted Credit Quality rating;
- branch weighted Credit Quality rating;
- executive weighted portfolio Credit Quality rating;
- Credit Quality-based bubble charts;
- Credit Quality-based Executive Branch Health;
- daily Credit Quality history snapshots;
- Credit Quality migration analytics across the rebuilt history.

Validation status:

- model successfully surfaces clients with hidden risk;
- model preserves high ratings for large but disciplined clients;
- model downgrades parent organizations where the largest exposure is low-quality;
- thresholds still require real-world observation and tuning.

Next validation actions:

- monitor highlighted clients for 1–2 weeks;
- compare model output with business intuition;
- tune YAML thresholds;
- record false positives and false negatives.

---

## 1.10 June 2026 Data Integrity and Analytics Release

Status: **COMPLETED AND DEPLOYED TO WORK STAND**

Implemented:

- corrected current-balance mapping: `invoice_amount` now comes from source `Просрочено, руб`;
- validated full historical rebuild from archived reports;
- 26 historical report snapshot dates restored;
- complete `client_rating_history` across all rebuilt dates;
- complete `client_credit_quality_history` across all rebuilt dates;
- Credit Quality migration analytics restored on historical Credit Quality data;
- weighted debt age chart added to Executive Overview;
- dashboard and operational client-table default sorting standardized;
- validated local database promoted to the online work stand.

Purpose:

Ensure debt totals reflect current outstanding balances after partial payments and make rating migration analytics consistent with Credit Quality Rating V2.

---

## 1.11 Automation Layer

Status: **COMPLETED, DEPLOYED AND SCHEDULED**

Implemented:

- standalone Mail Gateway;
- Yahoo IMAP App Password authentication;
- sender and attachment extension validation;
- SHA256 duplicate detection and manifest;
- structured JSONL logging;
- dry-run mode;
- processed / failed mailbox routing;
- backlog-safe inbox processing;
- restart-safe Orchestrator;
- safe handoff from `MAIL_INBOX_DIR` to ingestion raw directory;
- RAW directory used as the source of truth before ingestion;
- support for `--dry-run`, `--skip-mail`, `--skip-ingestion` and `--limit`;
- hourly production execution and online refresh;
- production archive workflow with explicit `0644` publication;
- production end-to-end validation.

## 1.12 Production-to-local synchronization

Status: **COMPLETED AND VALIDATED**

Implemented:

- dedicated chrooted SFTP-only access;
- persistent read-only production archive view;
- no shell and no production write permission;
- native Windows OpenSSH transport;
- SHA256 content identity and alias handling;
- atomic `.part` downloads and RAW handoff;
- versioned manifest and corruption recovery;
- local archive/raw/failed reconciliation;
- manual normal and dry-run PowerShell/CMD launchers;
- successful production archive → local PostgreSQL → local dashboard validation;
- matching production/local latest snapshot and principal metrics.

---

## 1.13 Historical Backfill Framework

Status: **COMPLETED, HARDENED AND POSTGRESQL-VALIDATED**

Implemented:

- isolated maintenance entry point outside scheduled ingestion;
- complete approved-batch validation and dry-run mode;
- audited source SHA256 validation and metadata-qualified database matching;
- chronological fact and history reconstruction in one transaction;
- temporary isolated maintenance staging;
- affected rating-history suffix rebuild;
- affected Credit Quality-history suffix rebuild;
- preservation of later facts and production current-snapshot views;
- explicit rejection of future-history and future term-shift leakage;
- rollback verification through an independent PostgreSQL connection;
- exact PostgreSQL parity with canonical latest-snapshot rating and Credit
  Quality views;
- regression and full-suite coverage;
- no persistent snapshot-context function or schema migration.

The Historical Backfill Framework is complete and is no longer future
implementation work.

Possible future enhancements, if broader maintenance needs emerge:

- a generalized analytical maintenance toolkit;
- additional reusable maintenance verification utilities;
- operator-oriented historical replay planning and reporting;
- support for separately approved report families without weakening validation.

These are extensions of the completed framework, not prerequisites for its
current controlled use.

---

# 2. Next active technical phase

## 2.0 Performance Engineering

Status: **NEXT ACTIVE TECHNICAL PHASE**

Scope:

- establish repeatable query and page-load baselines;
- profile slow analytical views and dashboard queries;
- inspect query plans and indexing opportunities;
- measure ingestion and refresh duration as history grows;
- define performance budgets for core operational pages;
- validate improvements without changing business definitions.

## 2.1 Credit Quality V2 threshold tuning

Status: **NEXT ACTIVE ANALYTICAL TASK**

Why:

The model is now implemented across the main UI, but thresholds should be validated on more real snapshots.

Questions to validate:

- Are long non-overdue debts penalized too aggressively?
- Are repeated shifts penalized enough?
- Should severity depend more strongly on debt size?
- Should small low-term clients be protected from excessive penalties?
- Should very large clients with long terms require separate policy review rather than rating penalty?

Planned actions:

- collect examples by rating transition: `base_stars → credit_quality_stars`;
- review top downgraded clients;
- review high-debt clients with unchanged rating;
- tune `configs/client_rating_rules.yaml`;
- document rationale for thresholds.

---

## 2.2 Credit Quality Portfolio Score

Status: **PARTIALLY IMPLEMENTED / NEEDS PRODUCTIZATION**

Already implemented:

- weighted Credit Quality rating in Executive Overview;
- weighted parent portfolio rating;
- weighted branch portfolio rating.

Potential improvements:

- historical trend of portfolio Credit Quality;
- monthly change vs previous month;
- split by branch;
- split by parent organization;
- share of debt in 1–2 star clients;
- share of debt downgraded by severity.

Potential KPI:

```text
Portfolio Credit Quality Score = weighted average Credit Quality Rating by current debt exposure
```

---

# 3. Immediate stabilization

## 3.1 Production hardening after work deployment v1

Status: **FOUNDATION COMPLETE / REMAINING OPERATIONS MATURITY**

Goal:

Stabilize the private work deployment after Production MVP Deployment v1.

Scope:

- daily PostgreSQL backups;
- restore test;
- password rotation;
- backup logs;
- proactive ingestion failure notifications;
- operational status page.

---

## 3.2 Scheduled automation

Status: **SCHEDULING COMPLETED / MONITORING REMAINS**

Goal:

Schedule and monitor the completed automation pipeline in the private work environment.

Completed:

- hourly scheduled execution;
- automatic online ingestion and dashboard refresh;
- ingestion run logging;

Remaining:

- failure notifications;
- archive / failed folder monitoring;
- dashboard freshness monitoring after ingestion.

---

## 3.3 Authentication and user management

Status: **PARTIALLY IMPLEMENTED / EXTEND LATER**

Current scope:

- Nginx Basic Auth protects the private work deployment;
- Basic Auth credentials are stored on the server only.

Minimum next scope:

- password rotation;
- admin user;
- read-only users;
- session handling;
- environment-specific credentials.

Later scope:

- role-based access;
- branch-level visibility restrictions;
- user action audit.

---

## 3.4 Backup and data retention

Status: **IMMEDIATE STABILIZATION TASK**

Planned capabilities:

- PostgreSQL backup schedule;
- backup rotation;
- restore test procedure;
- retention policy for raw exports;
- retention policy for database snapshots.

---

# 4. Next product milestones

## 4.1 Production operations maturity

Status: **NEXT**

Goal:

Move from Production MVP Deployment v1 to a durable operational production setup.

Scope:

- scheduled ingestion;
- logging;
- backup strategy;
- restore procedure;
- data refresh workflow.

Important decision:

Decide whether the client receives:

- trial package: data stays on client server, source code protected as much as practical;
- full package: all scripts, documentation and pipeline logic transferred.

---

# 5. Credit policy and exposure analytics

## 5.1 Credit Policy Monitoring: ARS_New / НО

Status: **RESEARCH COMPLETED / LOW CURRENT MATERIALITY / PARKED**

Research result:

- current observable НО exposure is small;
- clients with both ARS_New and НО are limited;
- influence on current portfolio-level risk is not significant enough to prioritize immediately.

Important caveat:

The system can only analyze facts present in the ERP data. If not all cash shipments are registered, this remains outside the current data perimeter.

Future use cases:

- ARS_New exposure monitoring;
- НО exposure monitoring;
- mixed analytics detection;
- branch-level policy compliance;
- parent-organization policy monitoring;
- early signal of credit restriction bypass.

Status recommendation:

Keep SQL discovery artifacts, but do not prioritize full productization until stronger business evidence appears.

---

## 5.2 Credit exposure and credit-limit monitoring

Status: **PLANNED**

Potential capabilities:

- effective working exposure;
- recommended credit limit;
- credit-limit utilization;
- abnormal shipment detection;
- exposure growth monitoring;
- concentration risk;
- safe next-shipment recommendation.

Potential metrics:

- average exposure during payment-term window;
- maximum historical exposure;
- exposure volatility;
- exposure growth rate;
- utilization percentage;
- debt-to-limit ratio.

Purpose:

Support practical credit-control and shipment approval decisions.

---

# 6. Workflow and collection management

## 6.1 Comments and action tracking

Status: **PLANNED**

Potential capabilities:

- client comments;
- invoice comments;
- next action;
- responsible manager;
- promised payment date;
- action history;
- communication timeline.

Purpose:

Turn the dashboard from analytics into a lightweight collection workflow tool.

---

## 6.2 Notification system

Status: **PLANNED**

Potential capabilities:

- configurable email reminders;
- payment deadline notifications;
- downgrade alerts;
- repeated term-shift alerts;
- 90+ green debt alerts;
- escalation workflow;
- operational notification queue.

---

## 6.3 Collection efficiency analytics

Status: **PLANNED**

Potential metrics:

- overdue recovery rate;
- average overdue resolution time;
- overdue backlog dynamics;
- manager workload;
- promised-payment fulfillment;
- action effectiveness.

Purpose:

Measure operational effectiveness of collection activities.

---

# 7. Advanced behavioral analytics

## 7.1 Payment behavior profiling

Status: **PLANNED**

Potential metrics:

- average contractual payment term;
- average actual payment term;
- average payment delay;
- maximum payment delay;
- percentage of invoices paid on time;
- percentage of invoices with due-date extensions;
- extension frequency;
- extension severity.

Purpose:

Improve Credit Quality V2 using actual payment behavior rather than only open receivables snapshots.

## 7.1.1 Analytics Segment Monitoring

Status: **PLANNED**

Motivation:

Portfolio behavior differs significantly between analytics types.

Current observations:

### ARS_NEW

Typical characteristics:

- large invoice amounts;
- long contractual payment terms;
- due-date extensions;
- hidden-risk scenarios;
- high management attention required.

### Розница

Typical characteristics:

- high invoice volume;
- small invoice amounts;
- short payment terms (3–7 days);
- rapid turnover;
- low individual risk;
- operational noise dominates.

### НО

Typical characteristics:

- requires separate policy monitoring;
- low current materiality;
- potential indicator of credit-policy bypass.

Potential capabilities:

- portfolio split by analytics type;
- analytics-specific KPI cards;
- analytics-specific overdue monitoring;
- analytics-specific exposure monitoring;
- analytics-specific client rankings;
- analytics-specific executive dashboards.

Potential KPI examples:

ARS_NEW:

- total exposure;
- overdue share;
- hidden-risk share;
- average payment term;
- average extension frequency.

Розница:

- turnover volume;
- collection speed;
- overdue ratio;
- average invoice size;
- top retail clients.

НО:

- exposure volume;
- client count;
- policy exceptions;
- mixed analytics monitoring.

Purpose:

Avoid mixing fundamentally different business processes into a single portfolio view and improve management focus.

---

## 7.2 Predictive collection risk

Status: **FUTURE / RESEARCH**

Possible signals:

- rising average payment term;
- repeated shifts;
- rating deterioration;
- green debt maturity drift;
- sudden exposure growth;
- abnormal invoice size;
- branch-specific risk patterns.

Potential outputs:

- probability of becoming overdue;
- expected delay;
- priority queue;
- downgrade warning.

---

## 7.3 Behavioral anomaly detection

Status: **FUTURE / RESEARCH**

Potential anomalies:

- unusual debt growth;
- unusual payment-term extension;
- sudden change in analytics type;
- unusual shift from normal credit to cash-sale pattern;
- invoice amount outside normal range;
- branch-specific anomalies.

## Event-driven receivables monitoring

Current status:
- implemented

Future improvements:

- event severity scoring
- grouping related invoice events
- branch-level event aggregation
- event acknowledgement workflow
- manager assignment
- event notification queue

---

# 8. Parent organization and branch analytics

## 8.1 Parent organization advanced analytics

Status: **PARTIALLY IMPLEMENTED / EXTEND LATER**

Already implemented:

- consolidated parent card;
- weighted Credit Quality portfolio rating;
- counterparties table;
- invoice table;
- recent paid invoice table;
- historical analytics.

Possible improvements:

- parent-level Credit Quality migration;
- parent-level risk bubble chart;
- parent-level concentration analysis;
- internal client dispersion analysis;
- parent-level credit limit.

---

## 8.2 Branch advanced analytics

Status: **PARTIALLY IMPLEMENTED / EXTEND LATER**

Already implemented:

- branch card;
- weighted Credit Quality portfolio rating;
- 90+ and 120+ non-overdue KPIs;
- client quality chart;
- tables aligned with parent organization card;
- recent paid invoice table;
- Executive Branch Health page.

Possible improvements:

- branch green debt maturity chart;
- branch-level risk bubble chart;
- branch operational scorecard;
- branch benchmarking;
- branch risk heatmap;
- branch workload monitoring.

---

## 8.3 User-defined branch groups

Status: **PLANNED**

Potential capabilities:

- saved branch selections;
- personal branch groups;
- shared branch groups;
- regional management views;
- quick filter presets.

---

# 9. Data quality and governance

## 9.1 Data quality controls

Status: **PLANNED**

Potential checks:

- missing due dates;
- duplicate invoices;
- inconsistent client IDs;
- inconsistent parent organization mapping;
- abnormal payment-term values;
- negative document handling;
- missing analytics type;
- unexpected currency values.

Potential outputs:

- ingestion quality dashboard;
- data quality score;
- blocking vs warning rules;
- anomaly report.

---

## 9.2 Data contract hardening

Status: **PLANNED**

Potential tasks:

- formally document required ERP export fields;
- define accepted formats;
- define encoding assumptions;
- define validation rules;
- define failure-handling logic;
- add automated data contract tests.

---

# 10. Frontend and UX evolution

## 10.1 Reusable dashboard widgets

Status: **ONGOING**

Already implemented:

- reusable chart functions;
- KPI cards;
- rating stars;
- rating strips;
- Credit Quality strip;
- navigation;
- branch filter.

Possible improvements:

- reusable table formatters;
- reusable invoice table component;
- reusable client link component;
- reusable parent / branch link components;
- centralized date and money formatting.

---

## 10.2 Persistent filters and layout personalization

Status: **PLANNED**

Potential capabilities:

- remember selected branches;
- remember period window;
- saved user views;
- configurable dashboard layout.

---

## 10.3 Mobile and responsive polish

Status: **PLANNED**

Potential improvements:

- mobile-friendly card stacking;
- compact tables;
- responsive chart heights;
- simplified operational queue for mobile users.

---

# 11. Multi-currency support

Status: **PLANNED / LOW PRIORITY UNTIL NEEDED**

Potential capabilities:

- RUR and EUR separated KPI cards;
- currency-specific overdue amounts;
- currency-specific branch summaries;
- optional FX conversion;
- hiding unused currency blocks.

---

# 12. Documentation roadmap

Status: **ONGOING**

Current documentation files:

- `README.md`
- `docs/PROJECT_STATUS.md`
- `docs/DATA_MODEL.md`
- `docs/FUTURE_ROADMAP.md`
- `docs/DEPLOYMENT.md`
- `docs/PRODUCTION_CONTEXT.md`
- `docs/ARCHITECTURE.md`
- `docs/METRICS.md`
- `docs/DASHBOARD_LAYOUT.md`
- `docs/DATA_CONTRACT.md`

Recommended next documentation updates:

1. Add screenshots after UI stabilizes.
2. Add SQL dependency map.
3. Add production deployment checklist.
4. Add demo script for stakeholder presentation.
5. Add Credit Quality V2 methodology note.

---

# 13. Recommended next development sequence

## Immediate

1. Begin Performance Engineering.
2. Add daily PostgreSQL backups and retention.
3. Perform and document a restore test.
4. Add health checks, failure notifications and dashboard-freshness monitoring.
5. Continue daily snapshot accumulation.
6. Monitor and tune Credit Quality V2 outputs.

## Next product cycle

1. Branch-level green debt maturity visualization.
2. Production operations dashboard.
3. Data quality monitoring for source-report mapping and operational view freshness.
4. Credit Quality threshold tuning based on post-rebuild observations.

## Later

1. Comments and collection workflow.
2. Credit limits.
3. Notifications.
4. Real payment history integration.
5. Predictive risk analytics.


---

## Next major milestone

### Production Foundation v1

Completed:

- private work deployment at `https://work.maximvenevtsev.com`;
- production hosting;
- password protection through Nginx Basic Auth;
- demo/work environment separation.
- scheduled Mail Gateway and Orchestrator;
- automatic online ingestion;
- production source archive;
- secure read-only Local Sync;
- manual double-click local synchronization;
- production/local end-to-end validation.

Remaining production stabilization:

- backup procedures;
- restore testing;
- PostgreSQL backup automation and retention;
- proactive production monitoring and failure notifications;
- application-level role-based access control.

### Demo / Work separation

Completed baseline:

- isolated public demo environment;
- isolated production environment;
- independent release workflow.
