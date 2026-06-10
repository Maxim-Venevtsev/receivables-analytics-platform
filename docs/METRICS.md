# Metrics

This document describes the main business metrics used in Debt Management BI.

## Core receivables metrics

### Total debt

Total open receivables amount in the current snapshot.

### Overdue debt

Amount where the invoice is currently overdue according to real due date logic.

### Overdue share

```text
overdue_debt / total_debt * 100
```

### Due today

Open debt due on the current control date.

### Due soon

Open debt due in the next 3 days, excluding due-today amount.

## Green debt metrics

Green debt means non-overdue debt.

### 90+ non-overdue debt

Non-overdue debt with payment term equal to or above 90 days.

### 120+ non-overdue debt

Non-overdue debt with payment term equal to or above 120 days.

### Green 90+ share

```text
green_90_plus_debt / total_debt * 100
```

Purpose: detect hidden credit risk inside formally non-overdue receivables.

## Payment-term metrics

### Payment term days

```text
due_date - invoice_date
```

### Weighted average payment term

Weighted by invoice amount or client total debt.

### Maximum payment term

Maximum observed payment term for a client / branch / parent organization.

## Term-shift metrics

### Term-shift count

Number of detected due-date extension events.

### Current term delta days

Difference between original and current payment term.

### Repeated shift invoice count

Number of invoices with repeated due-date extensions.

## Rating metrics

### Base stars

Original payment-discipline rating based mostly on overdue behavior.

### Credit Quality Stars

Credit Quality Rating V2, combining base rating with hidden-risk and severity signals.

### Severity level

Categorical severity signal:

- `NONE`
- `LOW`
- `MEDIUM`
- `HIGH`
- `CRITICAL`

### Severity penalty

Penalty subtracted from base rating to produce Credit Quality Rating.

### Weighted portfolio rating

```text
SUM(credit_quality_stars * total_debt) / SUM(total_debt)
```

Used for:

- total portfolio;
- parent organization;
- branch.

## Executive metrics

### Reliable debt

Typically:

```text
4–5 star clients + non-overdue + acceptable payment term
```

### Debt requiring control

Receivables outside the reliable-debt definition.

### TOP-20 concentration

Share of total debt concentrated in the 20 largest debtors.

## Migration metrics

### Upgraded clients

Clients whose rating improved between the beginning and end of the selected period.

### Downgraded clients

Clients whose rating worsened between the beginning and end of the selected period.

### Net migration

```text
upgraded_clients - downgraded_clients
```
