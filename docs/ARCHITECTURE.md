# Architecture

## Overview

Debt Management BI is a snapshot-based operational analytics platform for accounts receivable control.

```text
ERP TXT / Excel exports
    ↓
Python ingestion pipeline
    ↓
PostgreSQL analytical warehouse
    ↓
SQL analytical views
    ↓
NiceGUI frontend
```

## Layers

### 1. Source layer

Input files are generated from ERP / Axapta-style receivables reports.

The source layer includes:

- current open receivables snapshots;
- client identifiers;
- parent organization identifiers;
- branch / client group;
- invoice identifiers;
- invoice dates;
- due dates;
- invoice amounts;
- analytics type.

### 2. Ingestion layer

Python ingestion handles:

- file discovery;
- duplicate load prevention;
- parsing;
- normalization;
- data validation;
- PostgreSQL insert;
- archive / failed file routing.

### 3. Storage layer

PostgreSQL stores invoice-level daily snapshots.

The key design decision is to preserve historical snapshots rather than overwrite current state.

### 4. Analytical SQL layer

SQL views transform raw snapshots into:

- operational KPIs;
- daily histories;
- invoice lifecycle events;
- term-shift events;
- rating calculations;
- Credit Quality V2;
- executive portfolio analytics.

### 5. Frontend layer

NiceGUI pages provide:

- operational dashboards;
- drill-down navigation;
- charts;
- sortable tables;
- KPI cards;
- rating strips;
- executive risk views.

## Navigation model

```text
Dashboard
    ↓
Branch Card
    ↓
Parent Organization Card
    ↓
Client Card

Executive Overview
    ↓
Executive drill-down pages
    ↓
Client / Branch / Parent Cards
```

## Key architectural principles

- SQL-first analytical transformations;
- Python for ingestion and UI orchestration;
- reusable UI components;
- snapshot-based history;
- environment separation for demo and work data;
- no real raw data committed to Git;
- configurable business rules via YAML.
