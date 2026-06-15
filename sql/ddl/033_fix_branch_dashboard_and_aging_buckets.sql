-- ============================================================
-- 033_fix_branch_dashboard_and_aging_buckets.sql
-- Purpose:
--   1) Fix aging buckets in core.v_client_operational_summary:
--      45+/60+/90+/120+ must mean debt age, not contractual payment term.
--   2) Fix core.v_dashboard_operational_branches:
--      branch total_debt must include all active debt in the branch,
--      not only clients already included in operational control slice.
-- ============================================================


-- ============================================================
-- 1. Client operational summary
-- ============================================================

CREATE OR REPLACE VIEW core.v_client_operational_summary AS
WITH invoice_base AS (
    SELECT
        i.parent_org_id,
        i.client_id,
        i.client_name,
        i.client_group,

        i.invoice_date,
        i.due_date,
        i.invoice_amount,
        i.payment_term_days,

        (CURRENT_DATE - i.invoice_date::date) AS invoice_age_days,

        i.days_overdue_real,
        i.days_until_due_real,

        i.is_overdue_real,
        i.is_due_today,
        i.is_due_in_3_days,

        COALESCE(ts.term_shift_count, 0) AS term_shift_count,
        COALESCE(ts.current_term_delta_days, 0) AS term_shift_delta_days,
        ts.current_payment_term_days,
        ts.last_shift_date

    FROM core.v_invoice_detail i

    LEFT JOIN core.v_term_shift_invoice_summary ts
        ON i.client_id = ts.client_id
       AND i.print_invoice_number = ts.print_invoice_number
       AND i.order_number = ts.order_number
       AND i.invoice_date = ts.invoice_date
),

paid_behavior AS (
    SELECT
        client_id,
        COUNT(*) AS paid_behavior_invoice_count,
        percentile_cont(0.25) WITHIN GROUP (
            ORDER BY actual_payment_term_days
        ) AS usual_from_days,
        percentile_cont(0.75) WITHIN GROUP (
            ORDER BY actual_payment_term_days
        ) AS usual_to_days
    FROM core.v_recent_paid_invoices_behavior
    WHERE actual_payment_term_days IS NOT NULL
    GROUP BY client_id
),

contract_terms AS (
    SELECT
        client_id,
        MODE() WITHIN GROUP (ORDER BY payment_term_days) AS contract_payment_term_days,
        MAX(payment_term_days) AS max_payment_term_days,
        ROUND(AVG(payment_term_days)::numeric, 1) AS avg_payment_term_days
    FROM invoice_base
    WHERE payment_term_days IS NOT NULL
    GROUP BY client_id
),

client_agg AS (
    SELECT
        invoice_base.parent_org_id,
        invoice_base.client_id,
        invoice_base.client_name,
        invoice_base.client_group,

        COUNT(*) AS invoice_count,

        SUM(invoice_amount) AS total_debt,

        SUM(
            CASE
                WHEN is_overdue_real
                THEN invoice_amount
                ELSE 0
            END
        ) AS overdue_debt,

        SUM(
            CASE
                WHEN is_due_today
                THEN invoice_amount
                ELSE 0
            END
        ) AS due_today,

        SUM(
            CASE
                WHEN is_due_in_3_days AND NOT is_due_today
                THEN invoice_amount
                ELSE 0
            END
        ) AS due_soon_only,

        SUM(
            CASE
                WHEN NOT is_overdue_real
                 AND NOT is_due_today
                 AND NOT is_due_in_3_days
                 AND COALESCE(term_shift_count, 0) = 0
                 AND (
                        pb.usual_to_days IS NULL
                        OR invoice_age_days <= pb.usual_to_days
                     )
                THEN invoice_amount
                ELSE 0
            END
        ) AS normal_window_amount,

        SUM(
            CASE
                WHEN NOT is_overdue_real
                 AND NOT is_due_today
                 AND NOT is_due_in_3_days
                 AND COALESCE(term_shift_count, 0) = 0
                 AND pb.usual_to_days IS NOT NULL
                 AND invoice_age_days > pb.usual_to_days
                THEN invoice_amount
                ELSE 0
            END
        ) AS payment_attention_amount,

        SUM(
            CASE
                WHEN COALESCE(term_shift_count, 0) > 0
                THEN invoice_amount
                ELSE 0
            END
        ) AS shifted_amount,

        SUM(
            CASE
                WHEN COALESCE(term_shift_count, 0) >= 2
                THEN invoice_amount
                ELSE 0
            END
        ) AS repeated_shift_amount,

        COUNT(*) FILTER (
            WHERE COALESCE(term_shift_count, 0) > 0
        ) AS shifted_invoice_count,

        COUNT(*) FILTER (
            WHERE COALESCE(term_shift_count, 0) >= 2
        ) AS repeated_shift_invoice_count,

        SUM(COALESCE(term_shift_count, 0)) AS term_shift_count,

        MAX(last_shift_date) AS last_shift_date,
        MAX(COALESCE(term_shift_delta_days, 0)) AS max_current_term_delta_days,
        MAX(COALESCE(current_payment_term_days, payment_term_days)) AS max_current_payment_term_days,

        MAX(
            CASE
                WHEN is_overdue_real
                THEN days_overdue_real
                ELSE 0
            END
        ) AS max_days_overdue,

        MAX(pb.usual_from_days) AS usual_from_days,
        MAX(pb.usual_to_days) AS usual_to_days,

        -- Просроченный долг по возрасту долга, а не по договорной отсрочке.
        SUM(
            CASE
                WHEN is_overdue_real
                 AND invoice_age_days >= 45
                THEN invoice_amount
                ELSE 0
            END
        ) AS debt_45_plus,

        SUM(
            CASE
                WHEN is_overdue_real
                 AND invoice_age_days >= 60
                THEN invoice_amount
                ELSE 0
            END
        ) AS debt_60_plus,

        SUM(
            CASE
                WHEN is_overdue_real
                 AND invoice_age_days >= 90
                THEN invoice_amount
                ELSE 0
            END
        ) AS debt_90_plus,

        SUM(
            CASE
                WHEN is_overdue_real
                 AND invoice_age_days >= 120
                THEN invoice_amount
                ELSE 0
            END
        ) AS debt_120_plus,

        -- Непросроченный длинный долг по возрасту долга.
        SUM(
            CASE
                WHEN NOT is_overdue_real
                 AND invoice_age_days >= 45
                THEN invoice_amount
                ELSE 0
            END
        ) AS green_45_plus_debt,

        SUM(
            CASE
                WHEN NOT is_overdue_real
                 AND invoice_age_days >= 60
                THEN invoice_amount
                ELSE 0
            END
        ) AS green_60_plus_debt,

        SUM(
            CASE
                WHEN NOT is_overdue_real
                 AND invoice_age_days >= 90
                THEN invoice_amount
                ELSE 0
            END
        ) AS green_90_plus_debt,

        SUM(
            CASE
                WHEN NOT is_overdue_real
                 AND invoice_age_days >= 120
                THEN invoice_amount
                ELSE 0
            END
        ) AS green_120_plus_debt

    FROM invoice_base

    LEFT JOIN paid_behavior pb
        ON invoice_base.client_id = pb.client_id

    GROUP BY
        invoice_base.parent_org_id,
        invoice_base.client_id,
        invoice_base.client_name,
        invoice_base.client_group
)

SELECT
    a.parent_org_id,
    a.client_id,
    a.client_name,
    a.client_group,

    cq.credit_quality_stars AS stars,
    cq.credit_quality_display_label AS rating_display_label,
    cq.confidence_level,

    a.invoice_count,

    a.total_debt,
    a.due_today,
    a.due_soon_only,
    a.normal_window_amount,
    a.payment_attention_amount,
    a.overdue_debt,
    a.shifted_amount,
    a.repeated_shift_amount,

    ROUND((a.overdue_debt / NULLIF(a.total_debt, 0) * 100)::numeric, 1) AS overdue_share_pct,
    ROUND((a.due_today / NULLIF(a.total_debt, 0) * 100)::numeric, 1) AS due_today_share_pct,
    ROUND((a.due_soon_only / NULLIF(a.total_debt, 0) * 100)::numeric, 1) AS due_soon_share_pct,
    ROUND((a.shifted_amount / NULLIF(a.total_debt, 0) * 100)::numeric, 1) AS shifted_share_pct,

    a.shifted_invoice_count,
    a.term_shift_count,
    a.repeated_shift_invoice_count,

    a.last_shift_date,
    a.max_current_term_delta_days,
    a.max_current_payment_term_days,

    a.max_days_overdue,

    t.contract_payment_term_days,
    t.max_payment_term_days,
    t.avg_payment_term_days,

    a.usual_from_days,
    a.usual_to_days,

    a.debt_45_plus,
    a.debt_60_plus,
    a.debt_90_plus,
    a.debt_120_plus,

    a.green_45_plus_debt,
    a.green_60_plus_debt,
    a.green_90_plus_debt,
    a.green_120_plus_debt,

    CASE
        WHEN a.overdue_debt > 0 THEN 'OVERDUE'
        WHEN a.due_today > 0 THEN 'DUE_TODAY'
        WHEN a.due_soon_only > 0 THEN 'DUE_SOON'
        WHEN a.payment_attention_amount > 0 THEN 'PAYMENT_ATTENTION'
        WHEN a.shifted_amount > 0 THEN 'TERM_SHIFT'
        ELSE 'NORMAL'
    END AS operational_status,

    CASE
        WHEN a.overdue_debt > 0 THEN 1
        WHEN a.due_today > 0 THEN 2
        WHEN a.due_soon_only > 0 THEN 3
        WHEN a.payment_attention_amount > 0 THEN 4
        WHEN a.shifted_amount > 0 THEN 5
        ELSE 9
    END AS operational_sort_order,

    CASE
        WHEN cq.credit_quality_stars IN (1, 2, 3)
         AND t.contract_payment_term_days >= 15
        THEN TRUE
        ELSE FALSE
    END AS is_hidden_long_terms_risk

FROM client_agg a

LEFT JOIN contract_terms t
    ON a.client_id = t.client_id

LEFT JOIN core.v_client_credit_quality_rating cq
    ON a.client_id = cq.client_id;


-- ============================================================
-- 2. Dashboard branch aggregation
-- ============================================================

CREATE OR REPLACE VIEW core.v_dashboard_operational_branches AS
WITH aggregated AS (
    SELECT
        c.client_group,

        SUM(c.total_debt) AS total_debt,
        SUM(c.overdue_debt) AS overdue_debt,
        SUM(c.shifted_amount) AS shifted_amount,
        SUM(c.due_today) AS due_today,
        SUM(c.due_soon_only) AS due_soon_only,
        SUM(c.normal_window_amount) AS normal_window_amount,
        SUM(c.payment_attention_amount) AS payment_attention_amount,

        ROUND(
            SUM(c.overdue_debt)
            / NULLIF(SUM(c.total_debt), 0)
            * 100,
            2
        ) AS overdue_share_pct,

        ROUND(
            SUM(c.shifted_amount)
            / NULLIF(SUM(c.total_debt), 0)
            * 100,
            2
        ) AS shifted_share_pct,

        COUNT(*) FILTER (
            WHERE c.overdue_debt > 0
        ) AS overdue_clients,

        COUNT(*) FILTER (
            WHERE c.shifted_amount > 0
        ) AS shifted_clients,

        COUNT(*) FILTER (
            WHERE c.due_today > 0
        ) AS due_today_clients,

        COUNT(*) FILTER (
            WHERE c.due_soon_only > 0
        ) AS due_soon_clients,

        COUNT(*) FILTER (
            WHERE c.payment_attention_amount > 0
        ) AS payment_attention_clients,

        COUNT(*) FILTER (
            WHERE
                c.overdue_debt > 0
                OR c.shifted_amount > 0
                OR c.due_today > 0
                OR c.due_soon_only > 0
                OR c.payment_attention_amount > 0
        ) AS clients_to_control,

        CASE
            WHEN SUM(c.total_debt) > 0
            THEN
                SUM(COALESCE(c.stars, 0)::numeric * c.total_debt)
                / SUM(c.total_debt)
            ELSE NULL::numeric
        END AS weighted_rating

    FROM core.v_client_operational_summary c

    GROUP BY c.client_group
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
    clients_to_control,

    normal_window_amount

FROM aggregated

WHERE total_debt > 0;