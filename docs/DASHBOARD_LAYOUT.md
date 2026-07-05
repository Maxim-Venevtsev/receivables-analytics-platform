# Dashboard Layout

## Main navigation

Current primary pages:

- Dashboard
- Dynamics
- Overdue
- Due Today
- Due Soon
- Payment Attention
- Term Shifts
- Executive Overview
- Executive drill-down pages
- Client Card
- Parent Organization Card
- Branch Card

## Dashboard

Contains:

- KPI cards;
- latest data snapshot line under the subtitle;
- branch filter;
- aging / receivables structure;
- branch summary table sorted by total debt descending by default;
- operational client queue sorted by total debt descending by default.

Data freshness:

- the dashboard displays the latest available database snapshot date;
- the UI does not read mail or filesystem runtime directories directly;
- automated Mail Gateway and Orchestrator runs update the raw ingestion flow before PostgreSQL views refresh.

Automation context:

```text
Yahoo Mail
    ↓
Mail Gateway
    ↓
mail_inbox
    ↓
Orchestrator
    ↓
raw_work / RAW_DIR
    ↓
Existing ingestion
    ↓
PostgreSQL views
    ↓
Dashboard
```

## Client Card

Recommended structure:

1. Header and navigation.
2. KPI cards.
3. Credit Quality strip.
4. Rating migration strip.
5. Aging / debt structure.
6. Historical analytics.
7. Active invoices.
8. Recent paid invoices.

## Parent Organization Card

Recommended structure:

1. Header and navigation.
2. KPI cards.
3. Weighted portfolio rating strip.
4. Aging structure.
5. Historical analytics.
6. Counterparties.
7. Active invoices.
8. Recent paid invoices.

## Branch Card

Recommended structure:

1. Header and navigation.
2. KPI cards, including 90+ and 120+ non-overdue exposure.
3. Weighted portfolio rating strip.
4. Aging structure.
5. Historical analytics.
6. Client quality exposure block.
7. Counterparties.
8. Active invoices.
9. Recent paid invoices.

## Executive Overview

Recommended structure:

1. Executive KPI cards.
2. Portfolio verdict.
3. Portfolio structure charts.
4. Green debt maturity chart.
5. Weighted debt age chart.
6. Payment-term quality charts.
7. Client quality chart.
8. Rating migration analytics.
9. Risk bubble charts.
10. Management signals.

## Executive Branch Health

Contains:

- branch KPI summary;
- branch risk table;
- long green debt columns;
- Credit Quality weighted rating;
- navigation to Branch Card.


---

## New operational pages (June 2026)

### Payment Attention

Purpose:

Detect clients that are still non-overdue but already require operational attention.

Main blocks:

1. KPI cards.
2. Branch table sorted by window excess descending.
3. Client table sorted by window excess descending.

Key metrics:

- Normal payment window.
- Out-of-window exposure.
- Repeated term shifts.
- Clients requiring control.

### Term Shifts

Purpose:

Monitor invoices whose due dates were changed after issuance.

Main blocks:

1. KPI cards.
2. Branch table sorted by repeated shifts descending, then shifted amount descending.
3. Client table sorted by repeated shifts descending, then shifted amount descending.

Highlights:

- shift amount;
- shift count;
- repeated shifts;
- invoice-level drill-down.


---

## Default sorting standards

Default sorting is part of the operational UX contract:

- Dashboard branches: `total_debt` descending.
- Dashboard clients: `total_debt` descending.
- Due Today clients: `due_today` descending.
- Due Soon clients: `due_soon_only` descending.
- Payment Attention clients: `payment_attention_amount` descending.
- Term Shifts clients: repeated shifts descending, then total shifted amount descending.

Manual table sorting remains available after page load.
