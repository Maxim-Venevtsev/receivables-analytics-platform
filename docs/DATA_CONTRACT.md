# Data Contract

This document defines the expected data contract for Debt Management BI source exports and analytical outputs.

## Input file expectations

Source exports should contain enough fields to reconstruct invoice-level receivables.

Required logical fields:

- report generated date;
- debt as-of date;
- client ID;
- client name;
- parent organization ID;
- client group / branch;
- invoice date;
- due date;
- order number;
- printable invoice number;
- analytics type;
- invoice amount;
- currency;
- overdue days or enough fields to calculate overdue days.

## Parsing expectations

The ingestion pipeline should:

- normalize dates;
- normalize numeric amounts;
- preserve invoice identifiers;
- preserve source filename;
- reject or quarantine malformed files;
- avoid duplicate loads.

## Snapshot assumptions

Each loaded file represents one receivables snapshot.

The same invoice can appear in multiple snapshots.

Invoices can disappear because of:

- full payment;
- write-off;
- correction;
- source-system change.

Balance decrease between snapshots is interpreted as a possible partial payment.

## Required output guarantees

Analytical views should provide stable fields for UI pages:

- client identifiers;
- branch identifiers;
- parent organization identifiers;
- current debt;
- overdue debt;
- due today;
- due soon;
- payment term;
- rating;
- Credit Quality Rating;
- severity signals;
- term-shift indicators.

## Data quality checks to add later

Planned checks:

- duplicate invoice key detection;
- missing due date;
- missing invoice date;
- missing client ID;
- abnormal payment term;
- negative amount validation;
- inconsistent parent organization mapping;
- unknown analytics type;
- unexpected currency.

## Sensitive data rule

Real raw files, credentials and work data must not be committed to Git.
