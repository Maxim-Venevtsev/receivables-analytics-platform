# Future Roadmap

This roadmap is structured by implementation status and product layer. It is intended to guide the next development cycles after the implementation of Credit Quality Rating V2.

Project timeline note:

- project initiated around **20 April 2026**;
- active development started around **20 May 2026**;
- Credit Quality Rating V2 was implemented in June 2026.

---

# 1. Completed / ready locally

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

## 1.4 Rating Dynamics Layer

Status: **READY**

Implemented:

- client rating history;
- automatic rating snapshots after ingestion;
- latest rating dynamics;
- rating change event view;
- rating migration drill-down page;
- rating migration chart;
- client rating migration strip;
- weighted parent and branch rating strips.

Purpose:

Track rating upgrades, downgrades, stable clients, and newly rated clients.

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

Status: **COMPLETED LOCALLY / IN VALIDATION**

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
- Credit Quality-based Executive Branch Health.

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

# 2. In validation / tune next

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

## 2.3 Rating migration based on Credit Quality V2

Status: **DESIGN NEEDED**

Current migration analytics uses historical base rating snapshots.

Potential next step:

- store daily `credit_quality_stars` snapshots;
- create Credit Quality migration matrix;
- distinguish base rating migration from severity-driven migration;
- detect early deterioration even before overdue debt appears.

Important design question:

Should Credit Quality migration replace base rating migration, or should both be shown separately?

Recommended approach:

- keep base rating migration as payment-discipline migration;
- add Credit Quality migration as risk-quality migration.

---

# 3. Next product milestones

## 3.1 Production deployment of real work environment

Status: **PLANNED / HIGH PRIORITY**

Goal:

Deploy password-protected real-data version alongside the demo environment.

Scope:

- protected access;
- server deployment;
- environment separation;
- scheduled ingestion;
- logging;
- backup strategy;
- service restart policy;
- data refresh workflow.

Important decision:

Decide whether the client receives:

- trial package: data stays on client server, source code protected as much as practical;
- full package: all scripts, documentation and pipeline logic transferred.

---

## 3.2 Scheduled ETL

Status: **PLANNED**

Goal:

Automate daily ingestion.

Planned capabilities:

- scheduled file pickup;
- ingestion run logging;
- failure notifications;
- archive / failed folder management;
- automatic rating snapshot update;
- automatic Credit Quality refresh;
- dashboard refresh after ingestion.

---

## 3.3 Authentication and user management

Status: **PLANNED**

Minimum production scope:

- password protection;
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

Status: **PLANNED**

Planned capabilities:

- PostgreSQL backup schedule;
- backup rotation;
- restore test procedure;
- retention policy for raw exports;
- retention policy for database snapshots.

---

# 4. Credit policy and exposure analytics

## 4.1 Credit Policy Monitoring: ARS_New / НО

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

## 4.2 Credit exposure and credit-limit monitoring

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

# 5. Workflow and collection management

## 5.1 Comments and action tracking

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

## 5.2 Notification system

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

## 5.3 Collection efficiency analytics

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

# 6. Advanced behavioral analytics

## 6.1 Payment behavior profiling

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

---

## 6.2 Predictive collection risk

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

## 6.3 Behavioral anomaly detection

Status: **FUTURE / RESEARCH**

Potential anomalies:

- unusual debt growth;
- unusual payment-term extension;
- sudden change in analytics type;
- unusual shift from normal credit to cash-sale pattern;
- invoice amount outside normal range;
- branch-specific anomalies.

---

# 7. Parent organization and branch analytics

## 7.1 Parent organization advanced analytics

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

## 7.2 Branch advanced analytics

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

## 7.3 User-defined branch groups

Status: **PLANNED**

Potential capabilities:

- saved branch selections;
- personal branch groups;
- shared branch groups;
- regional management views;
- quick filter presets.

---

# 8. Data quality and governance

## 8.1 Data quality controls

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

## 8.2 Data contract hardening

Status: **PLANNED**

Potential tasks:

- formally document required ERP export fields;
- define accepted formats;
- define encoding assumptions;
- define validation rules;
- define failure-handling logic;
- add automated data contract tests.

---

# 9. Frontend and UX evolution

## 9.1 Reusable dashboard widgets

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

## 9.2 Persistent filters and layout personalization

Status: **PLANNED**

Potential capabilities:

- remember selected branches;
- remember period window;
- saved user views;
- configurable dashboard layout.

---

## 9.3 Mobile and responsive polish

Status: **PLANNED**

Potential improvements:

- mobile-friendly card stacking;
- compact tables;
- responsive chart heights;
- simplified operational queue for mobile users.

---

# 10. Multi-currency support

Status: **PLANNED / LOW PRIORITY UNTIL NEEDED**

Potential capabilities:

- RUR and EUR separated KPI cards;
- currency-specific overdue amounts;
- currency-specific branch summaries;
- optional FX conversion;
- hiding unused currency blocks.

---

# 11. Documentation roadmap

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

# 12. Recommended next development sequence

## Immediate

1. Commit current documentation update.
2. Continue daily snapshot accumulation.
3. Monitor Credit Quality V2 outputs on real clients.
4. Tune YAML thresholds after 1–2 weeks of observation.
5. Prepare production deployment checklist.

## Next product cycle

1. Production deployment with password protection.
2. Scheduled ETL.
3. Backup strategy.
4. Credit Quality V2 historical snapshots.
5. Credit Quality migration analytics.
6. Branch-level green debt maturity visualization.

## Later

1. Comments and collection workflow.
2. Credit limits.
3. Notifications.
4. Real payment history integration.
5. Predictive risk analytics.
