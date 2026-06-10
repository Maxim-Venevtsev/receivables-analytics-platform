-- 027_update_executive_credit_quality_views.sql
-- Executive Overview: switch portfolio rating, bubble charts and branch health to Credit Quality V2.

DROP VIEW IF EXISTS core.v_executive_branch_health;
DROP VIEW IF EXISTS core.v_executive_hidden_risk_bubble;
DROP VIEW IF EXISTS core.v_executive_client_risk_bubble;
DROP VIEW IF EXISTS core.v_executive_overview_kpi;


CREATE OR REPLACE VIEW core.v_executive_overview_kpi AS
WITH invoice_base AS (
    SELECT
        i.*,

        CASE WHEN i.is_overdue_real THEN i.invoice_amount ELSE 0 END AS overdue_amount,
        CASE WHEN i.is_due_today THEN i.invoice_amount ELSE 0 END AS due_today_amount,
        CASE
            WHEN i.is_due_in_3_days AND NOT i.is_due_today
            THEN i.invoice_amount
            ELSE 0
        END AS due_soon_only_amount,

        CASE
            WHEN NOT i.is_overdue_real
             AND i.payment_term_days >= 90
            THEN i.invoice_amount
            ELSE 0
        END AS green_90_plus_amount,

        CASE
            WHEN NOT i.is_overdue_real
             AND i.payment_term_days >= 120
            THEN i.invoice_amount
            ELSE 0
        END AS green_120_plus_amount

    FROM core.v_invoice_detail i
),

portfolio AS (
    SELECT
        MAX(invoice_date) AS latest_snapshot_date,

        SUM(invoice_amount) AS total_debt,
        SUM(overdue_amount) AS overdue_debt,
        SUM(due_today_amount) AS due_today,
        SUM(due_soon_only_amount) AS due_soon_only,

        SUM(green_90_plus_amount) AS green_90_plus_debt,
        SUM(green_120_plus_amount) AS green_120_plus_debt
    FROM invoice_base
),

rating AS (
    SELECT
        ROUND(
            SUM(cq.credit_quality_stars::numeric * cq.total_debt)
            / NULLIF(SUM(cq.total_debt), 0),
            2
        ) AS weighted_portfolio_rating
    FROM core.v_client_credit_quality_rating cq
    WHERE cq.total_debt > 0
)

SELECT
    p.latest_snapshot_date,

    p.total_debt,
    p.overdue_debt,

    CASE
        WHEN p.total_debt > 0
        THEN ROUND(p.overdue_debt / p.total_debt * 100, 2)
        ELSE 0
    END AS overdue_share_pct,

    p.due_today,
    p.due_soon_only,

    p.green_90_plus_debt,

    CASE
        WHEN p.total_debt > 0
        THEN ROUND(p.green_90_plus_debt / p.total_debt * 100, 2)
        ELSE 0
    END AS green_90_plus_share_of_portfolio_pct,

    p.green_120_plus_debt,

    CASE
        WHEN p.total_debt > 0
        THEN ROUND(p.green_120_plus_debt / p.total_debt * 100, 2)
        ELSE 0
    END AS green_120_plus_share_of_portfolio_pct,

    r.weighted_portfolio_rating,

    'credit_quality_v2'::text AS rating_method

FROM portfolio p
CROSS JOIN rating r;


CREATE OR REPLACE VIEW core.v_executive_client_risk_bubble AS
SELECT
    cq.client_id,
    cq.client_name,
    cq.client_group,
    cq.parent_org_id,

    cq.weighted_avg_payment_term_days AS x_payment_term_days,
    cq.credit_quality_stars AS y_rating,
    cq.total_debt AS bubble_size,

    cq.total_debt,
    cq.overdue_debt,
    cq.overdue_share_pct,
    cq.max_payment_term_days,

    cq.green_90_plus_debt,
    cq.green_120_plus_debt,
    cq.green_90_plus_share_pct,
    cq.green_120_plus_share_pct,

    cq.base_stars,
    cq.credit_quality_stars,
    cq.severity_level,
    cq.severity_penalty,
    cq.severity_reasons,

    CASE
        WHEN cq.overdue_share_pct >= 20 THEN 'RED'
        WHEN cq.overdue_debt > 0 THEN 'ORANGE'
        ELSE 'GREEN'
    END AS color_group,

    'credit_quality_v2'::text AS rating_method

FROM core.v_client_credit_quality_rating cq
WHERE cq.total_debt > 0;


CREATE OR REPLACE VIEW core.v_executive_hidden_risk_bubble AS
SELECT
    cq.client_id,
    cq.client_name,
    cq.client_group,
    cq.parent_org_id,

    cq.green_90_plus_share_pct AS x_green_90_share_pct,
    cq.credit_quality_stars AS y_rating,
    cq.total_debt AS bubble_size,

    cq.total_debt,
    cq.overdue_debt,
    cq.overdue_share_pct,

    cq.green_90_plus_debt,
    cq.green_120_plus_debt,
    cq.green_90_plus_share_pct AS green_90_plus_share_of_total_pct,
    cq.green_120_plus_share_pct AS green_120_plus_share_of_total_pct,

    cq.max_payment_term_days,

    cq.base_stars,
    cq.credit_quality_stars,
    cq.severity_level,
    cq.severity_penalty,
    cq.severity_reasons,

    CASE
        WHEN cq.green_120_plus_debt > 0 THEN 'CRITICAL'
        WHEN cq.green_90_plus_share_pct >= 50 THEN 'HIGH'
        WHEN cq.green_90_plus_debt > 0 THEN 'MEDIUM'
        ELSE 'LOW'
    END AS color_group,

    'credit_quality_v2'::text AS rating_method

FROM core.v_client_credit_quality_rating cq
WHERE cq.total_debt > 0;


CREATE OR REPLACE VIEW core.v_executive_branch_health AS
WITH branch_invoice AS (
    SELECT
        i.client_group,

        SUM(i.invoice_amount) AS total_debt,

        SUM(
            CASE WHEN i.is_overdue_real THEN i.invoice_amount ELSE 0 END
        ) AS overdue_debt,

        SUM(
            CASE
                WHEN NOT i.is_overdue_real
                 AND i.payment_term_days >= 90
                THEN i.invoice_amount
                ELSE 0
            END
        ) AS green_90_plus_debt,

        SUM(
            CASE
                WHEN NOT i.is_overdue_real
                 AND i.payment_term_days >= 120
                THEN i.invoice_amount
                ELSE 0
            END
        ) AS green_120_plus_debt,

        COUNT(DISTINCT i.client_id) AS client_count,
        COUNT(*) AS invoice_count

    FROM core.v_invoice_detail i
    GROUP BY i.client_group
),

branch_rating AS (
    SELECT
        client_group,

        ROUND(
            SUM(credit_quality_stars::numeric * total_debt)
            / NULLIF(SUM(total_debt), 0),
            2
        ) AS weighted_rating,

        ROUND(
            SUM(base_stars::numeric * total_debt)
            / NULLIF(SUM(total_debt), 0),
            2
        ) AS base_weighted_rating,

        COUNT(*) FILTER (
            WHERE credit_quality_stars < base_stars
        ) AS downgraded_by_severity_clients,

        COUNT(*) FILTER (WHERE severity_level = 'CRITICAL') AS critical_severity_clients,
        COUNT(*) FILTER (WHERE severity_level = 'HIGH') AS high_severity_clients,
        COUNT(*) FILTER (WHERE severity_level = 'MEDIUM') AS medium_severity_clients,
        COUNT(*) FILTER (WHERE severity_level = 'LOW') AS low_severity_clients,
        COUNT(*) FILTER (WHERE severity_level = 'NONE') AS no_severity_clients

    FROM core.v_client_credit_quality_rating
    WHERE total_debt > 0
    GROUP BY client_group
)

SELECT
    bi.client_group,

    bi.total_debt,
    bi.overdue_debt,

    CASE
        WHEN bi.total_debt > 0
        THEN ROUND(bi.overdue_debt / bi.total_debt * 100, 2)
        ELSE 0
    END AS overdue_share_pct,

    bi.green_90_plus_debt,

    CASE
        WHEN bi.total_debt > 0
        THEN ROUND(bi.green_90_plus_debt / bi.total_debt * 100, 2)
        ELSE 0
    END AS green_90_plus_share_pct,

    bi.green_120_plus_debt,

    CASE
        WHEN bi.total_debt > 0
        THEN ROUND(bi.green_120_plus_debt / bi.total_debt * 100, 2)
        ELSE 0
    END AS green_120_plus_share_pct,

    bi.client_count,
    bi.invoice_count,

    br.weighted_rating,
    br.base_weighted_rating,
    ROUND(br.base_weighted_rating - br.weighted_rating, 2) AS severity_portfolio_penalty,

    br.downgraded_by_severity_clients,
    br.critical_severity_clients,
    br.high_severity_clients,
    br.medium_severity_clients,
    br.low_severity_clients,
    br.no_severity_clients,

    'Рейтинг рассчитан по Credit Quality V2'::text AS portfolio_change_label,
    'STABLE'::text AS portfolio_change_status,
    'credit_quality_v2'::text AS rating_method

FROM branch_invoice bi

LEFT JOIN branch_rating br
    ON bi.client_group = br.client_group;