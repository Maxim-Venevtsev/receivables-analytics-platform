# Data Model

This document describes the analytical data model of the Debt Management BI platform.

---

## Architecture overview

The platform follows a snapshot-based analytical model:

```text
ERP TXT / Excel export
    ↓
Python ingestion
    ↓
PostgreSQL fact tables
    ↓
SQL analytical views
    ↓
NiceGUI operational frontend
```

The model supports:

- daily operational control;
- historical receivables analysis;
- client-level drill-down;
- parent organization aggregation;
- branch-level analytics;
- base payment-discipline rating;
- Credit Quality Rating V2;
- complete historical Credit Quality snapshots;
- rating migration analytics;
- invoice lifecycle analytics;
- term-shift detection;
- executive-level portfolio risk monitoring;
- green debt quality analytics;
- hidden-risk detection.

---

## Historical snapshot strategy

The platform stores daily receivables snapshots instead of only current-state balances.

This supports:

- debt evolution analysis;
- historical KPI reconstruction;
- payment behavior inference;
- rating calculation;
- rating dynamics tracking;
- parent organization and branch portfolio quality monitoring;
- payment-term drift detection;
- invoice lifecycle reconstruction;
- hidden-risk analysis;
- future forecasting.

---

## Core schema

Main analytical objects are stored in the `core` schema.

---

## Main fact table

### `core.receivables_snapshot_fact`

Central invoice-level snapshot fact table.

Each ERP export is loaded as a new snapshot. The same invoice can appear across multiple snapshot dates until it is paid, partially paid, written off, or disappears from the open receivables report.

Important balance definition after the June 2026 data-integrity fix:

- `invoice_amount` stores the current outstanding invoice balance used by operational and executive analytics;
- this value is mapped from source column `Просрочено, руб` because the CRM export is generated with an artificial future as-of date and current remaining balances appear there;
- source column `Сумма накладной` represents the original invoice amount and must not be used as the current debt balance.

This correction is why rebuilt portfolio totals can differ from earlier releases even when the same snapshot dates and row counts are present.

Typical dimensions:

- `report_generated_date`
- `debt_asof_date_param`
- `source_file_name`
- `parent_org_id`
- `client_id`
- `client_name`
- `client_group`
- `invoice_date`
- `due_date`
- `currency_code`
- `analytics_type`

Typical measures:

- `invoice_amount` — current outstanding balance, sourced from `Просрочено, руб`;
- `overdue_amount_rub` — normalized source outstanding-balance field retained for validation and audit;
- `overdue_amount_eur`
- `days_overdue_real`
- `days_until_due_real`

Operational flags:

- `is_overdue_real`
- `is_due_today`
- `is_due_in_3_days`
- `is_due_in_7_days`
- `is_negative_document`

Derived analytical fields:

- `payment_term_days`
- maturity buckets;
- term-shift changes;
- long green debt flags.

---

## Ingestion control

The ingestion workflow is designed to avoid duplicate loads.

Current flow:

1. Read raw TXT / Excel exports from configured raw directory.
2. Parse and normalize ERP export structure.
3. Load new files into PostgreSQL.
4. Skip already loaded files.
5. Write base rating history and Credit Quality history for the successfully loaded snapshot.
6. Move successfully processed files to archive directory.
7. Move failed files to failed directory.

Raw, archive and failed directories are environment-driven via `.env`.

The June 2026 rebuild loaded archived reports one by one in chronological report-date order so natural history was preserved. The validated result contains 26 report snapshot dates and matching base-rating and Credit Quality history dates.

---

## Environment separation

Supported environments:

- demo environment with synthetic / anonymized data;
- work environment with real operational data.

Sensitive paths must remain ignored:

- raw real exports;
- archived real files;
- failed real files;
- `.env`;
- database credentials.

---

## Rating configuration tables

### `core.client_rating_config`

Stores global configuration for the base client rating engine.

Key fields:

- `rating_window_days`
- `min_full_confidence_snapshot_days`
- `updated_at`

Default target rating window: 180 calendar days.

### `core.client_rating_rules`

Stores configurable thresholds for base star ratings.

Maintained in:

```text
configs/client_rating_rules.yaml
```

Loaded using:

```bash
python -m src.ingestion.load_rating_rules
```

### `core.client_rating_history`

Stores daily snapshots of base client ratings.

Purpose:

- rating audit trail;
- rating dynamics;
- upgrade / downgrade detection;
- base rating migration analytics;
- portfolio-quality aggregation.

### `core.client_credit_quality_history`

Stores daily snapshots of Credit Quality Rating V2 after each successful ingestion run.

Purpose:

- Credit Quality audit trail;
- Credit Quality migration analytics;
- branch / parent / client migration strips based on the same Credit Quality metric used by current cards;
- historical executive portfolio quality analysis.

After the June 2026 rebuild this table is complete for all available snapshot dates, matching `core.receivables_snapshot_fact.report_generated_date`.

---

## Credit Quality Rating V2

Credit Quality V2 extends the base payment-discipline rating with hidden-risk and severity signals.

### Core concept

```text
Base rating
    + payment-term quality
    + long green debt exposure
    + term-shift behavior
    + repeated due-date extensions
    + exposure severity
    = Credit Quality Rating V2
```

### Main view

### `core.v_client_credit_quality_rating`

Final client-level Credit Quality V2 view.

Key fields:

- `client_id`
- `client_name`
- `client_group`
- `parent_org_id`
- `base_stars`
- `base_rating_label`
- `base_rating_display_label`
- `confidence_level`
- `total_debt`
- `overdue_debt`
- `overdue_share_pct`
- `green_debt`
- `green_90_plus_debt`
- `green_120_plus_debt`
- `green_90_plus_share_pct`
- `green_120_plus_share_pct`
- `weighted_avg_payment_term_days`
- `max_payment_term_days`
- `term_shift_count`
- `max_invoice_term_shift_count`
- `repeated_shift_invoice_count`
- `heavy_repeated_shift_invoice_count`
- `total_term_shift_delta_days`
- `max_term_shift_delta_days`
- `exposure_segment`
- `exposure_multiplier`
- `raw_severity_points`
- `weighted_severity_points`
- `severity_level`
- `severity_penalty`
- `severity_reasons`
- `credit_quality_stars`
- `credit_quality_label`
- `credit_quality_display_label`
- `rating_downgraded_by_severity`

### Severity dimensions

Current severity dimensions:

- long weighted average payment term;
- anomalously long maximum payment term;
- high share of 90+ non-overdue debt;
- 120+ non-overdue debt;
- due-date extensions;
- repeated extensions on the same invoice;
- repeated extensions across multiple invoices;
- exposure size multiplier.

### Supporting views / SQL files

- `023_credit_quality_rating_v2.sql`
- `024_rating_v2_term_shift_severity.sql`

---

## Term-shift analytics

### `core.v_term_shift_events`

Detects due-date extension events across invoice snapshots.

### `core.v_term_shift_invoice_summary`

Aggregates term shifts to invoice level.

Key fields:

- `client_id`
- `print_invoice_number`
- `order_number`
- `invoice_date`
- `term_shift_count`
- `current_term_delta_days`
- `original_payment_term_days`
- `current_payment_term_days`

Used by:

- active invoice tables;
- paid invoice tables;
- Credit Quality V2;
- Executive term-shift drill-down.

---

## Invoice lifecycle analytics

### `core.v_invoice_snapshot_lifecycle`

Reconstructs invoice lifecycle across snapshots.

### `core.v_recent_paid_invoices`

Detects recent payment events based on:

- invoice disappearance from open receivables;
- open balance decrease;
- full payment;
- partial payment.

Used by:

- Client Card;
- Parent Organization Card;
- Branch Card.

Derived metrics:

- estimated payment date;
- actual payment-term days;
- delay vs due date;
- payment event type;
- term-shift markers.

---

## Operational analytical views

### `core.v_dashboard_overview`

Top-level operational dashboard KPI view.

### `core.v_branch_summary`

Branch / client-group aggregation.

### `core.v_client_priority`

Operational client queue.

### `core.v_invoice_detail`

Invoice-level operational detail view.

Current-state operational views read from the latest receivables snapshot only. Historical fact rows remain available for trend analytics, but operational pages must not aggregate across all historical snapshots.

Used by:

- Client Card;
- Parent Organization Card;
- Branch Card;
- invoice-level tables.

### `core.v_client_deltas`

Client-level debt movement view for Dynamics page.

---

## Historical daily views

### `core.v_client_daily_history`

Client-level historical aggregation.

### `core.v_parent_org_daily_history`

Parent organization-level historical aggregation.

### `core.v_branch_daily_history`

Branch-level historical aggregation.

Common metrics:

- `total_debt`
- `normal_debt`
- `due_soon_only`
- `due_today`
- `overdue_debt`
- `overdue_share_pct`
- `max_days_overdue`

---

## Base rating and rating dynamics views

### `core.v_client_rating_base`

Base analytical layer for payment-discipline rating.

### `core.v_client_rating`

Final base client rating view.

### `core.v_client_rating_dynamics`

Historical rating dynamics view.

### `core.v_client_rating_latest_dynamics`

Latest rating dynamics state for each client.

### `core.v_client_rating_change_events`

Only clients whose rating changed.

These views remain important because Credit Quality V2 uses the base rating as an input and rating migration analytics still depend on historical rating snapshots.

---

## Portfolio rating views

### `core.v_parent_org_rating_dynamics`

Parent-organization weighted portfolio rating.

Current status: **switched to Credit Quality V2**.

Current calculation:

```sql
SUM(credit_quality_stars * total_debt) / SUM(total_debt)
```

Key fields:

- `weighted_rating`
- `base_weighted_rating`
- `severity_portfolio_penalty`
- `rating_method = 'credit_quality_v2'`

### `core.v_branch_rating_dynamics`

Branch weighted portfolio rating.

Current status: **switched to Credit Quality V2**.

Current calculation:

```sql
SUM(credit_quality_stars * total_debt) / SUM(total_debt)
```

---

## Executive analytics layer

### `core.v_executive_overview_kpi`

Top-level Executive Overview KPI view.

Current status: **weighted portfolio rating switched to Credit Quality V2**.

Used for:

- total receivables;
- overdue debt;
- due-today debt;
- 90+ non-overdue debt;
- 120+ non-overdue debt;
- weighted portfolio rating.

### `core.v_executive_portfolio_daily_history`

Historical portfolio-level daily aggregation.

### `core.v_executive_green_debt_maturity_history`

Historical distribution of non-overdue debt by payment-term buckets:

- `0–30`
- `31–45`
- `46–60`
- `61–90`
- `91–120`
- `120+`

### `core.v_executive_weighted_debt_age_history`

Weighted average debt-age trend by snapshot date.

Calculation:

```sql
SUM(invoice_amount * GREATEST(report_generated_date - invoice_date, 0))
/ NULLIF(SUM(invoice_amount), 0)
```

Uses only positive open debt rows. This measures how old the currently open debt is from invoice date, weighted by current outstanding balance.

### `core.v_executive_payment_term_history`

Weighted average payment-term trend.

### `core.v_executive_long_green_exposure`

Historical long green exposure:

- 90+ non-overdue debt;
- 120+ non-overdue debt.

### `core.v_executive_rating_exposure`

Legacy base rating exposure view.

### Credit Quality exposure query

Executive Overview now uses `core.v_client_credit_quality_rating` directly for Credit Quality exposure distribution.

### `core.v_executive_branch_health`

Branch-level executive risk profile.

Current status: **weighted branch rating switched to Credit Quality V2**.

Key fields:

- `total_debt`
- `overdue_debt`
- `overdue_share_pct`
- `green_90_plus_debt`
- `green_90_plus_share_pct`
- `green_120_plus_debt`
- `green_120_plus_share_pct`
- `weighted_rating`
- `base_weighted_rating`
- `severity_portfolio_penalty`
- `rating_method`

### `core.v_executive_client_risk_bubble`

Executive bubble chart view.

Current status: **Y-axis rating switched to `credit_quality_stars`**.

Fields used by chart:

- `x_payment_term_days`
- `y_rating`
- `bubble_size`
- `color_group`

### `core.v_executive_hidden_risk_bubble`

Hidden-risk bubble chart view.

Current status: **Y-axis rating switched to `credit_quality_stars`**.

Fields used by chart:

- `x_green_90_share_pct`
- `y_rating`
- `bubble_size`
- `color_group`

### `core.v_executive_long_green_clients`

Client-level long green aggregation.

### `core.v_executive_long_green_invoices`

Invoice-level long green detail.

### `core.v_executive_overdue_clients`

Client-level overdue drill-down.

### `core.v_executive_hidden_risk_clients`

Client-level hidden-risk drill-down.

### `core.v_executive_term_shift_clients`

Term-shift drill-down.

---

## UI integration

Star rendering:

```text
src/app/components/rating_stars.py
```

Rating dynamics and weighted portfolio strip:

```text
src/app/components/rating_dynamics.py
```

Credit Quality strip:

```text
src/app/components/credit_quality_strip.py
```

Charts:

```text
src/app/components/charts.py
```

Credit Quality V2 is currently integrated into:

- Client Card;
- Parent Organization Card;
- Branch Card;
- Executive Overview;
- Executive Rating Migration;
- Executive Branch Health;
- Executive bubble charts.

---

## Current limitations

The current model does not yet include:

- real payment history table;
- credit limits;
- user comments;
- promised payment dates;
- collection action history;
- branch-level access control;
- automated downgrade alert workflow;
- scheduled production ETL.


---

## Payment behavior layer

Additional business concepts introduced in June 2026:

### Contract Payment Term

Client's stable expected payment term inferred from historical behavior and protected from anomalous invoices.

### Usual Payment Window

Observed payment behavior range used by Payment Attention monitoring.

### Recent Paid Invoice Behavior

Behavioral layer derived from recently paid invoices:

- early payment;
- normal payment;
- later than usual;
- overdue payment.

Used by Client, Parent Organization and Branch cards.
