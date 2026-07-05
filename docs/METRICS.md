# Metrics

This document describes the main business metrics used in Debt Management BI.

It also lists operational automation metrics used to monitor the Mail Gateway and Orchestrator. Automation metrics do not change business KPI definitions; they describe pipeline execution quality.

## Core receivables metrics

### Total debt

Total open receivables amount in the current snapshot.

After the June 2026 data-integrity fix this is based on current outstanding invoice balance, not original invoice amount. In source reports the current balance is taken from `Просрочено, руб`; `Сумма накладной` is treated as the original invoice amount and is not used for current debt analytics.

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

### Weighted average debt age

```text
SUM(current_outstanding_balance * max(report_generated_date - invoice_date, 0))
/ SUM(current_outstanding_balance)
```

Business meaning: average age of currently open debt, weighted by current outstanding balance. It complements weighted payment term by showing how old receivables are before or regardless of overdue status.

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

### Improved clients

Clients whose Credit Quality rating improved between the beginning and end of the selected period.

### Worsened clients

Clients whose Credit Quality rating worsened between the beginning and end of the selected period.

Legacy status labels `UPGRADED` and `DOWNGRADED` may still appear in older base-rating views, but the current Executive Rating Migration page uses Credit Quality history and classifies changes as improved / worsened.

### Net migration

```text
improved_clients - worsened_clients
```


## Payment Attention metrics

### Normal payment window

Debt currently located inside the client's usual payment behavior window.

### Out-of-window debt

Debt exceeding the client's usual payment behavior window.

### Repeat-shift exposure

Exposure related to invoices with repeated due-date extensions.

### Contract payment term

Inferred standard payment term based on stable historical behavior.

### Maximum payment term

Maximum observed payment term, including extreme outliers.

## Automation metrics

Automation metrics are emitted by the Mail Gateway and Orchestrator logs and summaries.

### Mail files written this run

Number of validated attachments written by Mail Gateway into `MAIL_INBOX_DIR` during the current run.

### Inbox files detected for handoff

Number of eligible files found in `MAIL_INBOX_DIR` after Mail Gateway finishes.

Eligible extensions:

- `.txt`
- `.xls`
- `.xlsx`

Manifest, JSONL, log, temp and lock files are ignored.

### Files handed off

Number of files safely copied from `MAIL_INBOX_DIR` to `AUTOMATION_RAW_DIR` with matching SHA256 verification and source removal after successful copy.

### RAW files detected

Number of eligible files present in `AUTOMATION_RAW_DIR` / `RAW_DIR` after handoff.

This is the source-of-truth metric for deciding whether ingestion should run. It supports restart safety: if the orchestrator stops after handoff but before ingestion, the next run detects raw files and continues.

### Ingestion executed

Boolean operational flag showing whether the existing ingestion entrypoint was executed.

### Ingestion skipped

Boolean operational flag showing whether ingestion was skipped.

Expected skip reasons:

- `empty raw`
- `--skip-ingestion`
- `dry_run`

### Duplicate attachments

Number of Mail Gateway attachments skipped because their SHA256 hash already exists in the manifest.

Duplicate detection is content-based, not filename-based.
