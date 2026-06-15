-- ============================================================
-- Dashboard operational views
-- ============================================================
-- Purpose:
--   Operational home page layer for daily receivables work:
--   overdue, term shifts, due today, due soon, payment attention.
-- ============================================================

DROP VIEW IF EXISTS core.v_dashboard_operational_branches;
DROP VIEW IF EXISTS core.v_dashboard_operational_clients;
DROP VIEW IF EXISTS core.v_dashboard_operational_kpi;


CREATE OR REPLACE VIEW core.v_dashboard_operational_clients AS
WITH invoice_base AS (
    SELECT
        i.client_id,
        MAX(i.client_name) AS client_name,
        MAX(i.client_group) AS client_group,

        SUM(i.invoice_amount) AS total_debt,

        SUM(CASE WHEN i.is_overdue_real THEN i.invoice_amount ELSE 0 END) AS overdue_debt,

        SUM(CASE WHEN i.is_due_today THEN i.invoice_amount ELSE 0 END) AS due_today,

        SUM(
            CASE
                WHEN i.is_due_in_3_days AND NOT i.is_due_today
                THEN i.invoice_amount
                ELSE 0
            END
        ) AS due_soon_only,

        SUM(
            CASE
                WHEN COALESCE(ts.term_shift_count, 0) > 0
                THEN i.invoice_amount
                ELSE 0
            END
        ) AS shifted_amount,

        COUNT(*) FILTER (WHERE i.is_overdue_real) AS overdue_invoice_count,
        COUNT(*) FILTER (WHERE i.is_due_today) AS due_today_invoice_count,
        COUNT(*) FILTER (WHERE i.is_due_in_3_days AND NOT i.is_due_today) AS due_soon_invoice_count,
        COUNT(*) FILTER (WHERE COALESCE(ts.term_shift_count, 0) > 0) AS shifted_invoice_count

    FROM core.v_invoice_detail i
    LEFT JOIN core.v_term_shift_invoice_summary ts
        ON i.client_id = ts.client_id
       AND i.print_invoice_number = ts.print_invoice_number
       AND i.order_number = ts.order_number
       AND i.invoice_date = ts.invoice_date
    WHERE i.invoice_amount > 0
    GROUP BY i.client_id
),
attention AS (
    SELECT
        client_id,
        SUM(
            amount_in_window
            + amount_out_of_window
            + amount_shift_once
            + amount_shift_repeated
        ) AS payment_attention_amount,
        MAX(clients_to_control) AS payment_attention_flag,
        SUM(invoices_to_control) AS payment_attention_invoice_count
    FROM core.v_payment_attention_clients
    GROUP BY client_id
),
enriched AS (
    SELECT
        b.client_id,
        b.client_name,
        b.client_group,

        COALESCE(cq.credit_quality_stars, r.stars) AS stars,
        COALESCE(cq.credit_quality_display_label, r.rating_display_label) AS rating_display_label,

        b.total_debt,
        b.overdue_debt,
        b.shifted_amount,
        b.due_today,
        b.due_soon_only,

        COALESCE(a.payment_attention_amount, 0) AS payment_attention_amount,

        ROUND(b.overdue_debt / NULLIF(b.total_debt, 0) * 100, 2) AS overdue_share_pct,
        ROUND(b.shifted_amount / NULLIF(b.total_debt, 0) * 100, 2) AS shifted_share_pct,

        b.overdue_invoice_count,
        b.shifted_invoice_count,
        b.due_today_invoice_count,
        b.due_soon_invoice_count,
        COALESCE(a.payment_attention_invoice_count, 0) AS payment_attention_invoice_count,

        CASE
            WHEN b.overdue_debt > 0 THEN 'OVERDUE'
            WHEN b.due_today > 0 THEN 'DUE_TODAY'
            WHEN b.due_soon_only > 0 THEN 'DUE_SOON'
            WHEN COALESCE(a.payment_attention_amount, 0) > 0 THEN 'PAYMENT_ATTENTION'
            WHEN b.shifted_amount > 0 THEN 'TERM_SHIFT'
            ELSE 'NORMAL'
        END AS operational_status,

        CASE
            WHEN b.overdue_debt > 0 THEN 1
            WHEN b.due_today > 0 THEN 2
            WHEN b.due_soon_only > 0 THEN 3
            WHEN COALESCE(a.payment_attention_amount, 0) > 0 THEN 4
            WHEN b.shifted_amount > 0 THEN 5
            ELSE 6
        END AS operational_sort_order
    FROM invoice_base b
    LEFT JOIN attention a
        ON b.client_id = a.client_id
    LEFT JOIN core.v_client_rating r
        ON b.client_id = r.client_id
    LEFT JOIN core.v_client_credit_quality_rating cq
        ON b.client_id = cq.client_id
)
SELECT *
FROM enriched
WHERE
    overdue_debt > 0
    OR shifted_amount > 0
    OR due_today > 0
    OR due_soon_only > 0
    OR payment_attention_amount > 0;


CREATE OR REPLACE VIEW core.v_dashboard_operational_branches AS
WITH base AS (
    SELECT *
    FROM core.v_dashboard_operational_clients
),
aggregated AS (
    SELECT
        client_group,

        SUM(total_debt) AS total_debt,
        SUM(overdue_debt) AS overdue_debt,
        SUM(shifted_amount) AS shifted_amount,
        SUM(due_today) AS due_today,
        SUM(due_soon_only) AS due_soon_only,
        SUM(payment_attention_amount) AS payment_attention_amount,

        ROUND(SUM(overdue_debt) / NULLIF(SUM(total_debt), 0) * 100, 2) AS overdue_share_pct,
        ROUND(SUM(shifted_amount) / NULLIF(SUM(total_debt), 0) * 100, 2) AS shifted_share_pct,

        COUNT(*) FILTER (WHERE overdue_debt > 0) AS overdue_clients,
        COUNT(*) FILTER (WHERE shifted_amount > 0) AS shifted_clients,
        COUNT(*) FILTER (WHERE due_today > 0) AS due_today_clients,
        COUNT(*) FILTER (WHERE due_soon_only > 0) AS due_soon_clients,
        COUNT(*) FILTER (WHERE payment_attention_amount > 0) AS payment_attention_clients,

        COUNT(*) AS clients_to_control,

        CASE
            WHEN SUM(total_debt) > 0
            THEN SUM(COALESCE(stars, 0) * total_debt) / SUM(total_debt)
            ELSE NULL
        END AS weighted_rating
    FROM base
    GROUP BY client_group
)
SELECT
    client_group,
    ROUND(weighted_rating::numeric, 1) AS weighted_rating,

    total_debt,
    overdue_debt,
    shifted_amount,
    due_today,
    due_soon_only,
    payment_attention_amount,

    overdue_share_pct,
    shifted_share_pct,

    overdue_clients,
    shifted_clients,
    due_today_clients,
    due_soon_clients,
    payment_attention_clients,
    clients_to_control
FROM aggregated;


CREATE OR REPLACE VIEW core.v_dashboard_operational_kpi AS
WITH portfolio AS (
    SELECT
        SUM(invoice_amount) AS total_debt
    FROM core.v_invoice_detail
    WHERE invoice_amount > 0
),
clients AS (
    SELECT *
    FROM core.v_dashboard_operational_clients
)
SELECT
    p.total_debt,

    COALESCE(SUM(c.overdue_debt), 0) AS overdue_debt,
    COUNT(*) FILTER (WHERE c.overdue_debt > 0) AS overdue_clients,

    COALESCE(SUM(c.shifted_amount), 0) AS shifted_amount,
    COUNT(*) FILTER (WHERE c.shifted_amount > 0) AS shifted_clients,

    COALESCE(SUM(c.due_today), 0) AS due_today,
    COUNT(*) FILTER (WHERE c.due_today > 0) AS due_today_clients,

    COALESCE(SUM(c.due_soon_only), 0) AS due_soon_only,
    COUNT(*) FILTER (WHERE c.due_soon_only > 0) AS due_soon_clients,

    COALESCE(SUM(c.payment_attention_amount), 0) AS payment_attention_amount,
    COUNT(*) FILTER (WHERE c.payment_attention_amount > 0) AS payment_attention_clients
FROM portfolio p
LEFT JOIN clients c ON TRUE
GROUP BY p.total_debt;