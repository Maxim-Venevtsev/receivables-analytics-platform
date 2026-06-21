-- ============================================================
-- Fix latest-snapshot operational views
-- ============================================================
-- Operational screens must show the current receivables snapshot only.
-- Historical snapshots stay in core.receivables_snapshot_fact for history,
-- deltas, lifecycle and rating history calculations.
--
-- This migration intentionally avoids SELECT * so CREATE OR REPLACE VIEW
-- keeps stable column names/order even when the fact table grows new columns.
-- ============================================================

CREATE OR REPLACE VIEW core.v_receivables_current_snapshot AS
SELECT
    id,
    load_id,
    source_file_name,
    report_generated_date,
    report_generated_time,
    debt_asof_date_param,
    parent_org_id,
    client_id,
    client_name,
    invoice_date,
    order_number,
    print_invoice_number,
    system_invoice_number,
    analytics_type,
    invoice_amount,
    currency_code,
    due_date,
    days_overdue_report_param,
    overdue_amount_rub,
    overdue_amount_eur,
    client_group,
    payment_term_days,
    days_overdue_real,
    days_until_due_real,
    is_overdue_real,
    is_due_today,
    is_due_in_3_days,
    is_due_in_7_days,
    is_negative_document,
    loaded_at
FROM core.receivables_snapshot_fact
WHERE report_generated_date = (
    SELECT MAX(report_generated_date)
    FROM core.receivables_snapshot_fact
);


CREATE OR REPLACE VIEW core.v_client_priority AS
SELECT
    client_id,
    client_name,
    client_group,

    COUNT(*) AS invoice_count,

    SUM(invoice_amount) AS total_debt,

    SUM(CASE WHEN is_overdue_real THEN invoice_amount ELSE 0 END) AS overdue_debt,

    SUM(CASE WHEN is_due_today THEN invoice_amount ELSE 0 END) AS due_today,

    SUM(CASE WHEN is_due_in_3_days THEN invoice_amount ELSE 0 END) AS due_in_3_days,

    SUM(CASE WHEN is_due_in_7_days THEN invoice_amount ELSE 0 END) AS due_in_7_days,

    MAX(days_overdue_real) AS max_days_overdue,

    MIN(due_date) AS nearest_due_date,

    SUM(CASE WHEN is_negative_document THEN invoice_amount ELSE 0 END) AS negative_amount,

    (
        SUM(CASE WHEN is_overdue_real THEN invoice_amount ELSE 0 END) * 1.5 +
        SUM(CASE WHEN is_due_today THEN invoice_amount ELSE 0 END) * 1.3 +
        SUM(CASE WHEN is_due_in_3_days THEN invoice_amount ELSE 0 END) * 1.1 +
        SUM(CASE WHEN is_due_in_7_days THEN invoice_amount ELSE 0 END) * 0.8 +
        MAX(days_overdue_real) * 100
    ) AS risk_score,

    CASE
        WHEN SUM(CASE WHEN is_overdue_real THEN invoice_amount ELSE 0 END) > 0
            THEN 'HIGH'
        WHEN SUM(CASE WHEN is_due_today THEN invoice_amount ELSE 0 END) > 0
            THEN 'HIGH'
        WHEN SUM(CASE WHEN is_due_in_3_days THEN invoice_amount ELSE 0 END) > 0
            THEN 'MEDIUM'
        WHEN SUM(CASE WHEN is_due_in_7_days THEN invoice_amount ELSE 0 END) > 0
            THEN 'MEDIUM'
        ELSE 'LOW'
    END AS risk_category,

    CASE
        WHEN SUM(CASE WHEN is_overdue_real THEN invoice_amount ELSE 0 END) > 0
            THEN 'CALL NOW'
        WHEN SUM(CASE WHEN is_due_today THEN invoice_amount ELSE 0 END) > 0
            THEN 'CONTROL TODAY'
        WHEN SUM(CASE WHEN is_due_in_3_days THEN invoice_amount ELSE 0 END) > 0
            THEN 'REMIND'
        WHEN SUM(CASE WHEN is_due_in_7_days THEN invoice_amount ELSE 0 END) > 0
            THEN 'MONITOR'
        ELSE 'OK'
    END AS recommended_action

FROM core.v_receivables_current_snapshot
GROUP BY client_id, client_name, client_group;


CREATE OR REPLACE VIEW core.v_invoice_detail AS
SELECT
    id,
    load_id,
    source_file_name,

    report_generated_date,
    debt_asof_date_param,

    parent_org_id,
    client_id,
    client_name,
    client_group,

    invoice_date,
    due_date,
    payment_term_days,

    analytics_type,
    currency_code,

    invoice_amount,
    overdue_amount_rub,
    overdue_amount_eur,

    days_overdue_real,
    days_until_due_real,

    is_overdue_real,
    is_due_today,
    is_due_in_3_days,
    is_due_in_7_days,
    is_negative_document,

    order_number,
    print_invoice_number,
    system_invoice_number,

    CASE
        WHEN is_overdue_real THEN 'OVERDUE'
        WHEN is_due_today THEN 'DUE TODAY'
        WHEN is_due_in_3_days THEN 'DUE IN 3 DAYS'
        WHEN is_due_in_7_days THEN 'DUE IN 7 DAYS'
        ELSE 'NOT DUE'
    END AS invoice_status

FROM core.v_receivables_current_snapshot;


CREATE OR REPLACE VIEW core.v_branch_summary AS
SELECT
    client_group,

    COUNT(*) AS invoice_count,
    COUNT(DISTINCT client_id) AS client_count,

    SUM(invoice_amount) AS total_debt,

    SUM(CASE WHEN is_overdue_real THEN invoice_amount ELSE 0 END) AS overdue_debt,

    SUM(CASE WHEN is_due_today THEN invoice_amount ELSE 0 END) AS due_today,

    SUM(CASE WHEN is_due_in_3_days THEN invoice_amount ELSE 0 END) AS due_in_3_days,

    SUM(CASE WHEN is_due_in_7_days THEN invoice_amount ELSE 0 END) AS due_in_7_days,

    ROUND(
        SUM(CASE WHEN is_overdue_real THEN invoice_amount ELSE 0 END)
        / NULLIF(SUM(invoice_amount), 0) * 100,
        2
    ) AS overdue_share_pct,

    COUNT(DISTINCT CASE WHEN is_overdue_real THEN client_id END) AS overdue_client_count,

    COUNT(DISTINCT CASE WHEN is_due_in_7_days THEN client_id END) AS due_soon_client_count

FROM core.v_receivables_current_snapshot
GROUP BY client_group;


CREATE OR REPLACE VIEW core.v_dashboard_kpi AS
SELECT
    COUNT(*) AS invoice_count,
    COUNT(DISTINCT client_id) AS client_count,
    COUNT(DISTINCT client_group) AS branch_count,

    SUM(invoice_amount) AS total_debt,

    SUM(CASE WHEN is_overdue_real THEN invoice_amount ELSE 0 END) AS overdue_debt,

    SUM(CASE WHEN is_due_today THEN invoice_amount ELSE 0 END) AS due_today,

    SUM(CASE WHEN is_due_in_3_days THEN invoice_amount ELSE 0 END) AS due_in_3_days,

    SUM(CASE WHEN is_due_in_7_days THEN invoice_amount ELSE 0 END) AS due_in_7_days,

    ROUND(
        SUM(CASE WHEN is_overdue_real THEN invoice_amount ELSE 0 END)
        / NULLIF(SUM(invoice_amount), 0) * 100,
        2
    ) AS overdue_share_pct,

    COUNT(DISTINCT CASE WHEN is_overdue_real THEN client_id END) AS overdue_client_count,

    COUNT(DISTINCT CASE WHEN is_due_in_7_days THEN client_id END) AS due_soon_client_count,

    MAX(report_generated_date) AS latest_snapshot_date

FROM core.v_receivables_current_snapshot;

