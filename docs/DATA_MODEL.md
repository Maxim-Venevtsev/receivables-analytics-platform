# Data Model

This document describes the core analytical data model of the Debt Management BI platform.

---

## Architecture overview

The platform follows a snapshot-based analytical model:

ERP TXT / Excel export
    ↓
Python ingestion
    ↓
PostgreSQL fact tables
    ↓
SQL analytical views
    ↓
NiceGUI operational frontend

The model is designed to support both:

- daily operational control
- historical receivables analysis
- client-level drill-down
- parent organization aggregation
- payment discipline rating
- branch-level historical analytics
- behavioral interpretation indicators

---

## Core schema

Main analytical objects are stored in the `core` schema.

---

## Main fact table

### `core.receivables_snapshot_fact`

Central fact table containing invoice-level receivables snapshots.

Each daily ERP export is loaded as a new snapshot.  
The same invoice may appear across multiple dates until it is paid or disappears from the open receivables report.

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

- `invoice_amount`
- `overdue_amount_rub`
- `overdue_amount_eur`
- `days_overdue_real`
- `days_until_due_real`

Operational flags:

- `is_overdue_real`
- `is_due_today`
- `is_due_in_3_days`
- `is_due_in_7_days`
- `is_negative_document`

---

## Ingestion control

### Incremental ingestion

The ingestion workflow is designed to avoid reloading already processed files.

Current workflow:

- read raw TXT exports from configured raw directory
- parse and normalize ERP export structure
- load new files into PostgreSQL
- skip already loaded files
- move successfully processed files to archive directory
- move failed files to failed directory

The raw, archive and failed directories are environment-driven via `.env`.

---

## Rating configuration tables

### `core.client_rating_config`

Stores global configuration for the client rating engine.

Key fields:

- `rating_window_days`
- `min_full_confidence_snapshot_days`
- `updated_at`

The default target rating window is 180 calendar days.

---

### `core.client_rating_rules`

Stores configurable thresholds for star ratings.

Key fields:

- `stars`
- `label`
- `max_overdue_occurrence_ratio`
- `max_avg_overdue_share_pct`
- `max_max_days_overdue`
- `updated_at`

Rating rules are maintained in:

```text
configs/client_rating_rules.yaml
```

and loaded into PostgreSQL using:

```bash
python -m src.ingestion.load_rating_rules
```

## Analytical views
### `core.v_dashboard_overview`

Top-level dashboard KPI view.

Used for:

- `total debt`
- `overdue debt`
- `due today`
- `due soon`
- `client counts`
- `branch counts`
- `high-risk client counts`

---

### `core.v_branch_summary`

Aggregates receivables by branch / client group.

Used for:

- `branch-level debt control`
- `overdue share by branch`
- `branch filtering in UI`

---

### `core.v_client_priority`

Operational client queue.

Used for:

- `client prioritization`
- `risk category`
- `recommended action`
- `due today / due soon / overdue monitoring`

---

### `core.v_invoice_detail`

Invoice-level operational detail view.

Used by:

- `client card`
- `parent organization card`
- `invoice-level drill-down`

---

### `core.v_client_deltas`

Historical client-level debt movement view.

Used by the Dynamics page.

Tracks:

- `previous snapshot date`
- `previous total debt`
- `current total debt`
- `total debt delta`
- `overdue debt delta`
- `debt change status`

---


---

### `core.v_client_daily_history`

Historical client-level daily aggregation.

Used by the client card historical analytics layer.

Key metrics:

- `total_debt`
- `normal_debt`
- `due_soon_only`
- `due_today`
- `overdue_debt`
- `overdue_share_pct`
- `max_days_overdue`

---

### `core.v_parent_org_daily_history`

Historical parent-organization daily aggregation.

Used by the parent organization card to analyze consolidated debt behavior across linked clients.

---

### `core.v_branch_daily_history`

Historical branch-level daily aggregation.

Used by the branch card for branch-level debt trends, debt structure dynamics and behavioral indicators.

---

### `core.v_parent_org_summary`

Aggregates receivables by parent organization.

Used by parent organization card.


---

### `core.v_parent_org_clients`

Aggregates receivables by client inside a parent organization.

Used for cross-client visibility.


---

### `core.v_parent_org_invoices`

Invoice-level view scoped for parent organization analysis.

---

### `core.v_client_rating_base`

Base analytical layer for client rating.

Calculated from historical snapshots within the configured rolling window.

Key metrics:

- `snapshot_days`
- `overdue_snapshot_days`
- `overdue_occurrence_ratio`
- `avg_overdue_share_pct`
- `max_days_overdue`
- `avg_total_debt`
- `total_debt_volatility`
- `confidence_level`

Confidence levels:

- `LOW: insufficient history`
- `MEDIUM: partial history`
- `FULL: enough history for full rating confidence`

---

### `core.v_client_rating`

Final client rating view.

Maps calculated client behavior metrics to configurable rating rules.

Key fields:

- `client_id`
- `client_name`
- `parent_org_id`
- `client_group`
- `stars`
- `rating_label`
- `rating_display_label`
- `confidence_level`

The rating is displayed in the UI as colored stars.

---

## UI integration

Client rating is displayed across major operational views:

- `Client card`
- `Dashboard client queue`
- `Dynamics client changes`
- `Overdue clients`
- `Due today clients`
- `Due soon clients`
- `Parent organization counterparties`

Star rendering is centralized in:

```text
src/app/components/rating_stars.py
```

This avoids duplicating rating rendering logic across pages.

---


## Behavioral analytics layer

The current behavioral analytics layer is calculated from historical daily aggregation views.

Current indicators:

- debt trend
- overdue behavior
- debt volatility

The indicators are rendered in:

- Client card
- Parent organization card
- Branch card

The UI uses reusable components:

```text
src/app/components/charts.py
src/app/components/kpi_cards.py
src/app/components/behavioral_indicators.py
```

Supported historical windows:

- 28 days
- 90 days
- 180 days
- all available history

---

## Environment separation

The platform supports separate environments:

- `demo environment with synthetic / anonymized data`
- `work environment with real operational datasets`

Real datasets must not be committed to GitHub.

---

## Sensitive paths should remain ignored:

- `raw real exports`
- `archived real files`
- `failed real files`
- `.env`
- `database credentials`

---

## Current limitations

The current model does not yet include:

- `real payment history table`
- `credit limits`
- `user comments`
- `promised payment dates`
- `collection action history`
- `branch-level access control`
- `rating history table`
- `rating downgrade alerts`

These features are planned for later production hardening.