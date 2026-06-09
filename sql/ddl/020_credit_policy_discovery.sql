-- 020_credit_policy_discovery.sql
-- Phase 3.3 — Credit Policy Discovery

DROP VIEW IF EXISTS core.v_no_clients;
DROP VIEW IF EXISTS core.v_client_analytics_mix;
DROP VIEW IF EXISTS core.v_analytics_type_profile;

CREATE OR REPLACE VIEW core.v_analytics_type_profile AS
SELECT
    COALESCE(NULLIF(TRIM(analytics_type), ''), 'UNKNOWN') AS analytics_type,

    COUNT(DISTINCT client_id) AS client_count,
    COUNT(*) AS invoice_count,

    SUM(invoice_amount) AS total_debt,
    SUM(CASE WHEN is_overdue_real THEN invoice_amount ELSE 0 END) AS overdue_debt,

    ROUND(
        SUM(CASE WHEN is_overdue_real THEN invoice_amount ELSE 0 END)
        / NULLIF(SUM(invoice_amount), 0) * 100,
        2
    ) AS overdue_share_pct,

    ROUND(AVG(payment_term_days), 1) AS avg_payment_term_days,
    MAX(payment_term_days) AS max_payment_term_days,

    ROUND(AVG(days_overdue_real), 1) AS avg_days_overdue,
    MAX(days_overdue_real) AS max_days_overdue,

    MIN(invoice_date) AS oldest_invoice_date,
    MAX(invoice_date) AS newest_invoice_date,
    MIN(due_date) AS oldest_due_date,
    MAX(due_date) AS newest_due_date

FROM core.v_invoice_detail
GROUP BY COALESCE(NULLIF(TRIM(analytics_type), ''), 'UNKNOWN');


CREATE OR REPLACE VIEW core.v_client_analytics_mix AS
WITH base AS (
    SELECT
        client_id,
        client_name,
        client_group,
        parent_org_id,
        COALESCE(NULLIF(TRIM(analytics_type), ''), 'UNKNOWN') AS analytics_type,
        invoice_amount,
        payment_term_days,
        days_overdue_real,
        is_overdue_real,
        invoice_date,
        due_date
    FROM core.v_invoice_detail
),

agg AS (
    SELECT
        client_id,
        MAX(client_name) AS client_name,
        MAX(client_group) AS client_group,
        MAX(parent_org_id) AS parent_org_id,

        SUM(invoice_amount) AS total_debt,

        SUM(CASE WHEN analytics_type = 'ARS_New' THEN invoice_amount ELSE 0 END) AS ars_new_debt,
        SUM(CASE WHEN analytics_type = 'НО' THEN invoice_amount ELSE 0 END) AS no_debt,

        SUM(CASE WHEN analytics_type = 'ARS_New' AND is_overdue_real THEN invoice_amount ELSE 0 END) AS ars_new_overdue,
        SUM(CASE WHEN analytics_type = 'НО' AND is_overdue_real THEN invoice_amount ELSE 0 END) AS no_overdue,

        COUNT(*) FILTER (WHERE analytics_type = 'ARS_New') AS ars_new_invoice_count,
        COUNT(*) FILTER (WHERE analytics_type = 'НО') AS no_invoice_count,

        MAX(payment_term_days) FILTER (WHERE analytics_type = 'ARS_New') AS max_ars_new_payment_term_days,
        MAX(payment_term_days) FILTER (WHERE analytics_type = 'НО') AS max_no_payment_term_days,

        MAX(days_overdue_real) FILTER (WHERE analytics_type = 'ARS_New') AS max_ars_new_days_overdue,
        MAX(days_overdue_real) FILTER (WHERE analytics_type = 'НО') AS max_no_days_overdue,

        MIN(invoice_date) FILTER (WHERE analytics_type = 'НО') AS oldest_no_invoice_date,
        MAX(invoice_date) FILTER (WHERE analytics_type = 'НО') AS newest_no_invoice_date

    FROM base
    GROUP BY client_id
)

SELECT
    *,

    CASE
        WHEN ars_new_debt > 0 AND no_debt > 0
        THEN TRUE ELSE FALSE
    END AS uses_both_flag,

    ROUND(ars_new_debt / NULLIF(total_debt, 0) * 100, 2) AS ars_new_share_pct,
    ROUND(no_debt / NULLIF(total_debt, 0) * 100, 2) AS no_share_pct,

    CASE
        WHEN no_overdue > 0 THEN 'BURGUNDY'
        WHEN ars_new_overdue > 0 AND no_debt > 0 THEN 'ORANGE'
        WHEN ars_new_debt > 0 AND no_debt > 0 THEN 'YELLOW'
        ELSE 'GREEN'
    END AS credit_policy_risk_level,

    CASE
        WHEN no_overdue > 0 THEN 'НО overdue'
        WHEN ars_new_overdue > 0 AND no_debt > 0 THEN 'ARS_New overdue + НО activity'
        WHEN ars_new_debt > 0 AND no_debt > 0 THEN 'Mixed ARS_New / НО exposure'
        ELSE 'No mixed-risk signal'
    END AS credit_policy_signal

FROM agg;


CREATE OR REPLACE VIEW core.v_no_clients AS
SELECT
    client_id,
    client_name,
    client_group,
    parent_org_id,

    total_debt,

    no_debt,
    no_overdue,
    no_invoice_count,
    oldest_no_invoice_date,
    newest_no_invoice_date,
    max_no_payment_term_days,
    max_no_days_overdue,

    ars_new_debt,
    ars_new_overdue,
    ars_new_invoice_count,
    max_ars_new_payment_term_days,
    max_ars_new_days_overdue,

    uses_both_flag,
    no_share_pct,
    credit_policy_risk_level,
    credit_policy_signal

FROM core.v_client_analytics_mix
WHERE no_debt > 0
ORDER BY
    CASE credit_policy_risk_level
        WHEN 'BURGUNDY' THEN 4
        WHEN 'ORANGE' THEN 3
        WHEN 'YELLOW' THEN 2
        ELSE 1
    END DESC,
    no_overdue DESC,
    ars_new_overdue DESC,
    no_debt DESC;