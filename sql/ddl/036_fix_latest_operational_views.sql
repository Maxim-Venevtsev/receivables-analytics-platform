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

-- ============================================================
-- 035_fix_contract_payment_term_outliers.sql
-- Purpose:
--   Make contract_payment_term_days robust against outlier active invoices.
--   Example: one active invoice with 785 days must not redefine the client's
--   contractual payment term if historical paid invoices show a stable 14 days.
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
    WITH client_base AS (
        SELECT DISTINCT
            client_id
        FROM invoice_base
    ),

    active_terms AS (
        SELECT
            client_id,
            payment_term_days
        FROM invoice_base
        WHERE payment_term_days IS NOT NULL
          AND payment_term_days BETWEEN 0 AND 180
    ),

    paid_terms AS (
        SELECT
            client_id,
            payment_term_days
        FROM core.v_recent_paid_invoices_behavior
        WHERE payment_term_days IS NOT NULL
          AND payment_term_days BETWEEN 0 AND 180
    ),

    combined_terms AS (
        SELECT
            client_id,
            payment_term_days,
            2 AS source_weight
        FROM paid_terms

        UNION ALL

        SELECT
            client_id,
            payment_term_days,
            1 AS source_weight
        FROM active_terms
    ),

    term_frequency AS (
        SELECT
            client_id,
            payment_term_days,
            SUM(source_weight) AS weighted_frequency
        FROM combined_terms
        GROUP BY client_id, payment_term_days
    ),

    selected_term AS (
        SELECT DISTINCT ON (client_id)
            client_id,
            payment_term_days AS contract_payment_term_days
        FROM term_frequency
        ORDER BY
            client_id,
            weighted_frequency DESC,
            payment_term_days ASC
    ),

    active_stats AS (
        SELECT
            client_id,

            MAX(
                COALESCE(
                    current_payment_term_days,
                    payment_term_days
                )
            ) AS max_payment_term_days,

            ROUND(
                AVG(
                    COALESCE(
                        current_payment_term_days,
                        payment_term_days
                    )
                )::numeric,
                1
            ) AS avg_payment_term_days

        FROM invoice_base
        WHERE COALESCE(current_payment_term_days, payment_term_days) IS NOT NULL
        GROUP BY client_id
    )

    SELECT
        cb.client_id,
        s.contract_payment_term_days,
        a.max_payment_term_days,
        a.avg_payment_term_days

    FROM client_base cb

    LEFT JOIN selected_term s
        ON cb.client_id = s.client_id

    LEFT JOIN active_stats a
        ON cb.client_id = a.client_id
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
-- Dashboard operational views must stay downstream of latest-only
-- invoice/client operational layers.
-- ============================================================

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
SELECT
    client_id,
    client_name,
    client_group,
    stars,
    rating_display_label,
    total_debt,
    overdue_debt,
    shifted_amount,
    due_today,
    due_soon_only,
    payment_attention_amount,
    overdue_share_pct,
    shifted_share_pct,
    overdue_invoice_count,
    shifted_invoice_count,
    due_today_invoice_count,
    due_soon_invoice_count,
    payment_attention_invoice_count,
    operational_status,
    operational_sort_order
FROM enriched
WHERE
    overdue_debt > 0
    OR shifted_amount > 0
    OR due_today > 0
    OR due_soon_only > 0
    OR payment_attention_amount > 0;


CREATE OR REPLACE VIEW core.v_dashboard_operational_kpi AS
WITH portfolio AS (
    SELECT
        SUM(invoice_amount) AS total_debt
    FROM core.v_invoice_detail
),
clients AS (
    SELECT
        client_id,
        client_name,
        client_group,
        stars,
        rating_display_label,
        total_debt,
        overdue_debt,
        shifted_amount,
        due_today,
        due_soon_only,
        payment_attention_amount,
        overdue_share_pct,
        shifted_share_pct,
        overdue_invoice_count,
        shifted_invoice_count,
        due_today_invoice_count,
        due_soon_invoice_count,
        payment_attention_invoice_count,
        operational_status,
        operational_sort_order
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


DO $$
DECLARE
    bad_views text;
BEGIN
    SELECT string_agg(n.nspname || '.' || c.relname, ', ' ORDER BY c.relname)
    INTO bad_views
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'core'
      AND c.relname IN (
          'v_invoice_detail',
          'v_client_priority',
          'v_branch_summary',
          'v_dashboard_kpi',
          'v_client_operational_summary',
          'v_dashboard_operational_clients',
          'v_dashboard_operational_branches',
          'v_dashboard_operational_kpi'
      )
      AND c.relkind = 'v'
      AND pg_get_viewdef(c.oid, true) ILIKE '%FROM core.receivables_snapshot_fact%';

    IF bad_views IS NOT NULL THEN
        RAISE EXCEPTION
            'Operational views must not read historical core.receivables_snapshot_fact directly: %',
            bad_views;
    END IF;
END $$;

