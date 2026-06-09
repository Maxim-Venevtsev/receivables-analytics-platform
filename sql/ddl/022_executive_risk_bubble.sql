-- 022_executive_risk_bubble.sql
-- Executive Risk Bubble / Matrix analytics

DROP VIEW IF EXISTS core.v_executive_hidden_risk_bubble;
DROP VIEW IF EXISTS core.v_executive_client_risk_bubble;
DROP VIEW IF EXISTS core.v_executive_client_risk_bubble_base;


CREATE OR REPLACE VIEW core.v_executive_client_risk_bubble_base AS
WITH base AS (
    SELECT
        i.client_id,
        MAX(i.client_name) AS client_name,
        MAX(i.client_group) AS client_group,
        MAX(i.parent_org_id) AS parent_org_id,

        SUM(i.invoice_amount) AS total_debt,

        SUM(
            CASE WHEN i.is_overdue_real
            THEN i.invoice_amount ELSE 0 END
        ) AS overdue_debt,

        SUM(
            CASE WHEN NOT i.is_overdue_real
            THEN i.invoice_amount ELSE 0 END
        ) AS green_debt,

        SUM(
            CASE
                WHEN NOT i.is_overdue_real
                 AND COALESCE(i.payment_term_days, 0) >= 45
                THEN i.invoice_amount ELSE 0
            END
        ) AS green_45_plus_debt,

        SUM(
            CASE
                WHEN NOT i.is_overdue_real
                 AND COALESCE(i.payment_term_days, 0) >= 60
                THEN i.invoice_amount ELSE 0
            END
        ) AS green_60_plus_debt,

        SUM(
            CASE
                WHEN NOT i.is_overdue_real
                 AND COALESCE(i.payment_term_days, 0) >= 90
                THEN i.invoice_amount ELSE 0
            END
        ) AS green_90_plus_debt,

        SUM(
            CASE
                WHEN NOT i.is_overdue_real
                 AND COALESCE(i.payment_term_days, 0) >= 120
                THEN i.invoice_amount ELSE 0
            END
        ) AS green_120_plus_debt,

        ROUND(
            (
                SUM(COALESCE(i.payment_term_days, 0) * i.invoice_amount)
                / NULLIF(SUM(i.invoice_amount), 0)
            )::numeric,
            2
        ) AS weighted_avg_payment_term_days,

        MAX(i.payment_term_days) AS max_payment_term_days,
        MAX(i.days_overdue_real) AS max_days_overdue,

        COUNT(*) AS invoice_count

    FROM core.v_invoice_detail i
    GROUP BY i.client_id
)

SELECT
    b.client_id,
    b.client_name,
    b.client_group,
    b.parent_org_id,

    r.stars,
    r.rating_display_label,
    r.confidence_level,

    b.total_debt,
    b.overdue_debt,
    b.green_debt,
    b.green_45_plus_debt,
    b.green_60_plus_debt,
    b.green_90_plus_debt,
    b.green_120_plus_debt,

    ROUND(
        (b.overdue_debt / NULLIF(b.total_debt, 0) * 100)::numeric,
        2
    ) AS overdue_share_pct,

    ROUND(
        (b.green_90_plus_debt / NULLIF(b.total_debt, 0) * 100)::numeric,
        2
    ) AS green_90_plus_share_of_total_pct,

    ROUND(
        (b.green_90_plus_debt / NULLIF(b.green_debt, 0) * 100)::numeric,
        2
    ) AS green_90_plus_share_of_green_pct,

    ROUND(
        (b.green_120_plus_debt / NULLIF(b.total_debt, 0) * 100)::numeric,
        2
    ) AS green_120_plus_share_of_total_pct,

    b.weighted_avg_payment_term_days,
    b.max_payment_term_days,
    b.max_days_overdue,
    b.invoice_count,

    CASE
        WHEN b.overdue_debt / NULLIF(b.total_debt, 0) >= 0.20 THEN 'RED'
        WHEN b.overdue_debt > 0 THEN 'ORANGE'
        ELSE 'GREEN'
    END AS overdue_risk_level,

    CASE
        WHEN b.green_120_plus_debt > 0 THEN 'CRITICAL'
        WHEN b.green_90_plus_debt / NULLIF(b.total_debt, 0) >= 0.20 THEN 'HIGH'
        WHEN b.green_90_plus_debt > 0 THEN 'MEDIUM'
        ELSE 'LOW'
    END AS hidden_risk_level

FROM base b
LEFT JOIN core.v_client_rating r
    ON b.client_id = r.client_id;


CREATE OR REPLACE VIEW core.v_executive_client_risk_bubble AS
SELECT
    client_id,
    client_name,
    client_group,
    parent_org_id,

    stars,
    rating_display_label,
    confidence_level,

    weighted_avg_payment_term_days AS x_payment_term_days,
    stars AS y_rating,
    total_debt AS bubble_size,

    total_debt,
    overdue_debt,
    overdue_share_pct,

    max_payment_term_days,
    max_days_overdue,
    invoice_count,

    overdue_risk_level AS color_group,

    CASE
        WHEN overdue_risk_level = 'RED'
            THEN 'Высокая просрочка'
        WHEN overdue_risk_level = 'ORANGE'
            THEN 'Есть просрочка'
        ELSE 'Без просрочки'
    END AS risk_label

FROM core.v_executive_client_risk_bubble_base
WHERE total_debt > 0;


CREATE OR REPLACE VIEW core.v_executive_hidden_risk_bubble AS
SELECT
    client_id,
    client_name,
    client_group,
    parent_org_id,

    stars,
    rating_display_label,
    confidence_level,

    green_90_plus_share_of_total_pct AS x_green_90_share_pct,
    stars AS y_rating,
    total_debt AS bubble_size,

    total_debt,
    green_debt,
    green_90_plus_debt,
    green_120_plus_debt,

    green_90_plus_share_of_total_pct,
    green_90_plus_share_of_green_pct,
    green_120_plus_share_of_total_pct,

    weighted_avg_payment_term_days,
    max_payment_term_days,
    invoice_count,

    hidden_risk_level AS color_group,

    CASE
        WHEN hidden_risk_level = 'CRITICAL'
            THEN '120+ непросрочено'
        WHEN hidden_risk_level = 'HIGH'
            THEN 'Высокая доля 90+'
        WHEN hidden_risk_level = 'MEDIUM'
            THEN 'Есть 90+ непросрочено'
        ELSE 'Низкий скрытый риск'
    END AS risk_label

FROM core.v_executive_client_risk_bubble_base
WHERE total_debt > 0;