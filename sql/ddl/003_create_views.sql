DROP VIEW IF EXISTS core.v_client_priority;

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

FROM core.receivables_snapshot_fact
GROUP BY client_id, client_name, client_group;



DROP VIEW IF EXISTS core.v_invoice_detail;

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

FROM core.receivables_snapshot_fact;



DROP VIEW IF EXISTS core.v_branch_summary;

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

FROM core.receivables_snapshot_fact
GROUP BY client_group;



DROP VIEW IF EXISTS core.v_dashboard_kpi;

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

FROM core.receivables_snapshot_fact;



DROP VIEW IF EXISTS core.v_client_deltas;

CREATE VIEW core.v_client_deltas AS
WITH client_daily AS (
    SELECT
        report_generated_date,
        client_id,
        client_name,
        client_group,

        COUNT(*) AS invoice_count,
        SUM(invoice_amount) AS total_debt,
        SUM(CASE WHEN is_overdue_real THEN invoice_amount ELSE 0 END) AS overdue_debt,
        SUM(CASE WHEN is_due_in_7_days THEN invoice_amount ELSE 0 END) AS due_in_7_days,
        MAX(days_overdue_real) AS max_days_overdue
    FROM core.receivables_snapshot_fact
    GROUP BY
        report_generated_date,
        client_id,
        client_name,
        client_group
),

with_lags AS (
    SELECT
        *,
        LAG(report_generated_date) OVER (
            PARTITION BY client_id
            ORDER BY report_generated_date
        ) AS previous_snapshot_date,

        LAG(total_debt) OVER (
            PARTITION BY client_id
            ORDER BY report_generated_date
        ) AS previous_total_debt,

        LAG(overdue_debt) OVER (
            PARTITION BY client_id
            ORDER BY report_generated_date
        ) AS previous_overdue_debt
    FROM client_daily
)

SELECT
    report_generated_date,
    previous_snapshot_date,

    client_id,
    client_name,
    client_group,

    invoice_count,
    total_debt,
    overdue_debt,
    due_in_7_days,
    max_days_overdue,

    previous_total_debt,
    previous_overdue_debt,

    total_debt - COALESCE(previous_total_debt, 0) AS total_debt_delta,
    overdue_debt - COALESCE(previous_overdue_debt, 0) AS overdue_debt_delta,

    CASE
        WHEN previous_total_debt IS NULL THEN 'NEW IN SNAPSHOT'
        WHEN total_debt < previous_total_debt THEN 'DEBT DECREASED'
        WHEN total_debt > previous_total_debt THEN 'DEBT INCREASED'
        ELSE 'NO CHANGE'
    END AS debt_change_status,

    CASE
        WHEN previous_overdue_debt IS NULL THEN 'NEW IN SNAPSHOT'
        WHEN overdue_debt < previous_overdue_debt THEN 'OVERDUE DECREASED'
        WHEN overdue_debt > previous_overdue_debt THEN 'OVERDUE INCREASED'
        ELSE 'NO CHANGE'
    END AS overdue_change_status

FROM with_lags;



DROP VIEW IF EXISTS core.v_dashboard_overview;

CREATE VIEW core.v_dashboard_overview AS
SELECT
    k.latest_snapshot_date,

    k.invoice_count,
    k.client_count,
    k.branch_count,

    k.total_debt,
    k.overdue_debt,
    k.due_today,
    k.due_in_3_days,
    k.due_in_7_days,
    k.overdue_share_pct,

    k.overdue_client_count,
    k.due_soon_client_count,

    (
        SELECT COUNT(*)
        FROM core.v_client_priority
        WHERE risk_category = 'HIGH'
    ) AS high_risk_client_count,

    (
        SELECT COUNT(*)
        FROM core.v_client_priority
        WHERE recommended_action IN ('CALL NOW', 'CONTROL TODAY')
    ) AS urgent_action_count,

    (
        SELECT COUNT(*)
        FROM core.v_client_deltas
        WHERE report_generated_date = k.latest_snapshot_date
          AND total_debt_delta < 0
    ) AS clients_with_debt_decrease,

    (
        SELECT COUNT(*)
        FROM core.v_client_deltas
        WHERE report_generated_date = k.latest_snapshot_date
          AND total_debt_delta > 0
    ) AS clients_with_debt_increase

FROM core.v_dashboard_kpi k;