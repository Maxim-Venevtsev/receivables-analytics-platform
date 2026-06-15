-- ============================================================
-- Payment Attention views
-- ============================================================
-- Purpose:
--   Pre-overdue payment attention layer:
--   - active invoices inside the client's usual payment window
--   - active invoices beyond the client's usual payment window
--   - non-overdue invoices with due-date shifts
--   - client-level and branch-level action summaries
-- ============================================================

DROP VIEW IF EXISTS core.v_payment_attention_branches;
DROP VIEW IF EXISTS core.v_payment_attention_clients;
DROP VIEW IF EXISTS core.v_payment_attention_invoices;
DROP VIEW IF EXISTS core.v_client_payment_profile;


CREATE OR REPLACE VIEW core.v_client_payment_profile AS
WITH paid_base AS (
    SELECT
        client_id,
        client_name,
        client_group,
        parent_org_id,
        actual_payment_term_days
    FROM core.v_recent_paid_invoices
    WHERE actual_payment_term_days IS NOT NULL
      AND actual_payment_term_days >= 0
),
profile AS (
    SELECT
        client_id,
        MAX(client_name) AS client_name,
        MAX(client_group) AS client_group,
        MAX(parent_org_id) AS parent_org_id,

        COUNT(*) AS payment_profile_invoice_count,

        percentile_cont(0.25)
            WITHIN GROUP (ORDER BY actual_payment_term_days)
            AS usual_from_days,

        percentile_cont(0.75)
            WITHIN GROUP (ORDER BY actual_payment_term_days)
            AS usual_to_days,

        AVG(actual_payment_term_days)::numeric(12, 2)
            AS avg_actual_payment_term_days,

        MAX(actual_payment_term_days)
            AS max_actual_payment_term_days
    FROM paid_base
    GROUP BY client_id
)
SELECT
    client_id,
    client_name,
    client_group,
    parent_org_id,

    payment_profile_invoice_count,

    ROUND(usual_from_days::numeric, 1) AS usual_from_days,
    ROUND(usual_to_days::numeric, 1) AS usual_to_days,
    avg_actual_payment_term_days,
    max_actual_payment_term_days,

    CASE
        WHEN payment_profile_invoice_count >= 5 THEN TRUE
        ELSE FALSE
    END AS has_full_profile,

    CASE
        WHEN payment_profile_invoice_count >= 1 THEN TRUE
        ELSE FALSE
    END AS has_any_profile
FROM profile;


CREATE OR REPLACE VIEW core.v_payment_attention_invoices AS
WITH latest_snapshot AS (
    SELECT MAX(report_generated_date) AS snapshot_date
    FROM core.v_invoice_detail
),
active_invoices AS (
    SELECT
        i.parent_org_id,
        i.client_id,
        i.client_name,
        i.client_group,

        i.invoice_date,
        i.order_number,
        i.print_invoice_number,
        i.analytics_type,
        i.due_date,
        i.payment_term_days,
        i.invoice_amount,

        i.days_overdue_real,
        i.days_until_due_real,
        i.is_overdue_real,
        i.is_due_today,
        i.is_due_in_3_days,

        ls.snapshot_date,

        GREATEST(
            0,
            (ls.snapshot_date::date - i.invoice_date::date)
        )::int AS invoice_age_days
    FROM core.v_invoice_detail i
    CROSS JOIN latest_snapshot ls
    WHERE i.invoice_amount > 0
),
enriched AS (
    SELECT
        a.*,

        p.payment_profile_invoice_count,
        p.usual_from_days,
        p.usual_to_days,
        p.avg_actual_payment_term_days,
        p.max_actual_payment_term_days,
        p.has_full_profile,
        p.has_any_profile,

        r.stars AS base_stars,
        r.rating_display_label AS base_rating_display_label,
        r.confidence_level AS base_rating_confidence_level,

        cq.credit_quality_stars,
        cq.credit_quality_display_label,
        cq.severity_level,
        cq.severity_penalty,
        cq.severity_reasons,

        COALESCE(ts.term_shift_count, 0) AS term_shift_count,
        COALESCE(ts.current_term_delta_days, 0) AS term_shift_delta_days,
        ts.original_payment_term_days,
        ts.current_payment_term_days AS shifted_current_payment_term_days
    FROM active_invoices a
    LEFT JOIN core.v_client_payment_profile p
        ON a.client_id = p.client_id
    LEFT JOIN core.v_client_rating r
        ON a.client_id = r.client_id
    LEFT JOIN core.v_client_credit_quality_rating cq
        ON a.client_id = cq.client_id
    LEFT JOIN core.v_term_shift_invoice_summary ts
        ON a.client_id = ts.client_id
       AND a.print_invoice_number = ts.print_invoice_number
       AND a.order_number = ts.order_number
       AND a.invoice_date = ts.invoice_date
),
classified AS (
    SELECT
        *,

        CASE
            WHEN is_overdue_real THEN 'OVERDUE'

            WHEN NOT has_any_profile OR usual_from_days IS NULL OR usual_to_days IS NULL
                THEN 'NO_PROFILE'

            WHEN invoice_age_days > usual_to_days
                THEN 'OUT_OF_USUAL_WINDOW'

            WHEN invoice_age_days >= usual_from_days
             AND invoice_age_days <= usual_to_days
                THEN 'IN_USUAL_WINDOW'

            ELSE 'NOT_YET_IN_WINDOW'
        END AS attention_status,

        CASE
            WHEN is_overdue_real THEN 'Просрочено'

            WHEN NOT has_any_profile OR usual_from_days IS NULL OR usual_to_days IS NULL
                THEN 'Нет профиля'

            WHEN invoice_age_days > usual_to_days
                THEN 'Вышла из обычного окна'

            WHEN invoice_age_days >= usual_from_days
             AND invoice_age_days <= usual_to_days
                THEN 'В обычном окне'

            ELSE 'Рано контролировать'
        END AS attention_status_label,

        CASE
            WHEN is_overdue_real THEN 'red'
            WHEN has_any_profile AND invoice_age_days > usual_to_days THEN 'orange'
            WHEN has_any_profile
             AND invoice_age_days >= usual_from_days
             AND invoice_age_days <= usual_to_days THEN 'blue'
            WHEN NOT has_any_profile OR usual_from_days IS NULL OR usual_to_days IS NULL THEN 'gray'
            ELSE 'green'
        END AS attention_color,

        CASE
            WHEN is_overdue_real THEN 1
            WHEN has_any_profile AND invoice_age_days > usual_to_days THEN 2
            WHEN term_shift_count >= 2 THEN 3
            WHEN term_shift_count = 1 THEN 4
            WHEN has_any_profile
             AND invoice_age_days >= usual_from_days
             AND invoice_age_days <= usual_to_days THEN 5
            WHEN NOT has_any_profile OR usual_from_days IS NULL OR usual_to_days IS NULL THEN 6
            ELSE 7
        END AS attention_sort_order,

        CASE
            WHEN has_any_profile AND usual_to_days IS NOT NULL
                THEN invoice_age_days - usual_to_days
            ELSE NULL
        END AS days_after_usual_window,

        CASE
            WHEN term_shift_count = 1 THEN TRUE
            ELSE FALSE
        END AS has_shift_once,

        CASE
            WHEN term_shift_count >= 2 THEN TRUE
            ELSE FALSE
        END AS has_shift_repeated
    FROM enriched
)
SELECT *
FROM classified
WHERE
    is_overdue_real
    OR (
        has_any_profile
        AND usual_from_days IS NOT NULL
        AND invoice_age_days >= usual_from_days
    )
    OR term_shift_count > 0
    OR NOT has_any_profile;


CREATE OR REPLACE VIEW core.v_payment_attention_clients AS
WITH base AS (
    SELECT *
    FROM core.v_payment_attention_invoices
    WHERE NOT is_overdue_real
      AND (
            attention_status IN ('IN_USUAL_WINDOW', 'OUT_OF_USUAL_WINDOW')
            OR term_shift_count > 0
          )
),
raw_aggregated AS (
    SELECT
        parent_org_id,
        client_id,
        MAX(client_name) AS client_name,
        MAX(client_group) AS client_group,

        COALESCE(MAX(credit_quality_stars), MAX(base_stars)) AS stars,
        COALESCE(MAX(credit_quality_display_label), MAX(base_rating_display_label)) AS rating_display_label,

        SUM(CASE WHEN attention_status = 'IN_USUAL_WINDOW' THEN invoice_amount ELSE 0 END) AS raw_amount_in_window,
        SUM(CASE WHEN attention_status = 'OUT_OF_USUAL_WINDOW' THEN invoice_amount ELSE 0 END) AS raw_amount_out_of_window,
        SUM(CASE WHEN term_shift_count = 1 THEN invoice_amount ELSE 0 END) AS raw_amount_shift_once,
        SUM(CASE WHEN term_shift_count >= 2 THEN invoice_amount ELSE 0 END) AS raw_amount_shift_repeated,

        COUNT(*) FILTER (WHERE attention_status = 'IN_USUAL_WINDOW') AS raw_invoice_count_in_window,
        COUNT(*) FILTER (WHERE attention_status = 'OUT_OF_USUAL_WINDOW') AS raw_invoice_count_out_of_window,
        COUNT(*) FILTER (WHERE term_shift_count = 1) AS raw_invoice_count_shift_once,
        COUNT(*) FILTER (WHERE term_shift_count >= 2) AS raw_invoice_count_shift_repeated,

        MAX(invoice_age_days) FILTER (WHERE attention_status = 'IN_USUAL_WINDOW') AS max_age_in_window,
        MAX(invoice_age_days) FILTER (WHERE attention_status = 'OUT_OF_USUAL_WINDOW') AS max_age_out_of_window,
        MAX(invoice_age_days) FILTER (WHERE term_shift_count = 1) AS max_age_shift_once,

        BOOL_OR(is_due_today) AS has_due_today,

        BOOL_OR(
            is_due_in_3_days
            AND NOT is_due_today
        ) AS has_due_soon,

        MAX(days_after_usual_window) AS max_days_after_usual_window,
        MAX(invoice_amount) AS max_invoice_amount,
        MIN(attention_sort_order) AS min_attention_sort_order
    FROM base
    GROUP BY parent_org_id, client_id
),
qualified AS (
    SELECT
        *,

        (
            raw_amount_in_window >= 50000
            AND COALESCE(max_age_in_window, 0) >= 8
        ) AS show_in_window,

        (
            raw_amount_out_of_window >= 10000
            AND COALESCE(max_age_out_of_window, 0) >= 4
        ) AS show_out_of_window,

        (
            raw_amount_shift_once >= 30000
            AND COALESCE(max_age_shift_once, 0) >= 8
        ) AS show_shift_once,

        (
            raw_amount_shift_repeated >= 10000
        ) AS show_shift_repeated
    FROM raw_aggregated
)
SELECT
    parent_org_id,
    client_id,
    client_name,
    client_group,
    stars,
    rating_display_label,

    CASE WHEN show_in_window THEN raw_amount_in_window ELSE 0 END AS amount_in_window,
    CASE WHEN show_out_of_window THEN raw_amount_out_of_window ELSE 0 END AS amount_out_of_window,
    CASE WHEN show_shift_once THEN raw_amount_shift_once ELSE 0 END AS amount_shift_once,
    CASE WHEN show_shift_repeated THEN raw_amount_shift_repeated ELSE 0 END AS amount_shift_repeated,

    (
        CASE WHEN show_in_window THEN raw_invoice_count_in_window ELSE 0 END
        + CASE WHEN show_out_of_window THEN raw_invoice_count_out_of_window ELSE 0 END
        + CASE WHEN show_shift_once THEN raw_invoice_count_shift_once ELSE 0 END
        + CASE WHEN show_shift_repeated THEN raw_invoice_count_shift_repeated ELSE 0 END
    ) AS invoice_count_total,

    CASE WHEN show_in_window THEN raw_invoice_count_in_window ELSE 0 END AS invoice_count_in_window,
    CASE WHEN show_out_of_window THEN raw_invoice_count_out_of_window ELSE 0 END AS invoice_count_out_of_window,
    CASE WHEN show_shift_once THEN raw_invoice_count_shift_once ELSE 0 END AS invoice_count_shift_once,
    CASE WHEN show_shift_repeated THEN raw_invoice_count_shift_repeated ELSE 0 END AS invoice_count_shift_repeated,

    (
        CASE WHEN show_in_window THEN raw_invoice_count_in_window ELSE 0 END
        + CASE WHEN show_out_of_window THEN raw_invoice_count_out_of_window ELSE 0 END
        + CASE WHEN show_shift_once THEN raw_invoice_count_shift_once ELSE 0 END
        + CASE WHEN show_shift_repeated THEN raw_invoice_count_shift_repeated ELSE 0 END
    ) AS invoices_to_control,

    max_age_in_window,
    max_age_out_of_window,
    max_days_after_usual_window,
    max_invoice_amount,
    min_attention_sort_order,
    has_due_today,
    has_due_soon,

    TRUE AS needs_attention,
    1 AS clients_to_control,

    show_in_window,
    show_out_of_window,
    show_shift_once,
    show_shift_repeated
FROM qualified
WHERE
    show_in_window
    OR show_out_of_window
    OR show_shift_once
    OR show_shift_repeated;


CREATE OR REPLACE VIEW core.v_payment_attention_branches AS
WITH base AS (
    SELECT *
    FROM core.v_payment_attention_clients
),
aggregated AS (
    SELECT
        client_group,

        SUM(amount_in_window) AS amount_in_window,
        SUM(amount_out_of_window) AS amount_out_of_window,
        SUM(amount_shift_once) AS amount_shift_once,
        SUM(amount_shift_repeated) AS amount_shift_repeated,

        COUNT(*) AS clients_to_control,
        COUNT(*) AS clients_total,

        SUM(invoice_count_total) AS invoice_count_total,
        SUM(invoices_to_control) AS invoices_to_control,

        CASE
            WHEN SUM(amount_in_window + amount_out_of_window + amount_shift_once + amount_shift_repeated) > 0
            THEN
                SUM(
                    COALESCE(stars, 0)
                    * (amount_in_window + amount_out_of_window + amount_shift_once + amount_shift_repeated)
                )
                / SUM(amount_in_window + amount_out_of_window + amount_shift_once + amount_shift_repeated)
            ELSE NULL
        END AS weighted_rating
    FROM base
    GROUP BY client_group
)
SELECT
    client_group,
    ROUND(weighted_rating::numeric, 1) AS weighted_rating,

    amount_in_window,
    amount_out_of_window,
    amount_shift_once,
    amount_shift_repeated,

    clients_to_control,
    clients_total,

    invoice_count_total,
    invoices_to_control
FROM aggregated
WHERE
    amount_in_window > 0
    OR amount_out_of_window > 0
    OR amount_shift_once > 0
    OR amount_shift_repeated > 0;