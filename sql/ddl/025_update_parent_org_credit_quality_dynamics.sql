-- 025_update_parent_org_credit_quality_dynamics.sql
-- Parent organization portfolio rating switched to Credit Quality Rating V2.

DROP VIEW IF EXISTS core.v_parent_org_rating_dynamics;

CREATE OR REPLACE VIEW core.v_parent_org_rating_dynamics AS
WITH current_cq AS (
    SELECT
        parent_org_id,
        client_id,
        client_name,
        client_group,
        base_stars,
        credit_quality_stars,
        severity_level,
        severity_penalty,
        total_debt,
        overdue_debt,
        CASE
            WHEN total_debt > 0 THEN total_debt
            ELSE 1
        END AS rating_weight
    FROM core.v_client_credit_quality_rating
    WHERE parent_org_id IS NOT NULL
),

parent_agg AS (
    SELECT
        parent_org_id,
        COUNT(DISTINCT client_id) AS clients_total,
        COUNT(DISTINCT client_id) AS clients_with_rating,
        SUM(total_debt) AS total_debt,
        SUM(overdue_debt) AS overdue_debt,

        ROUND(
            SUM(credit_quality_stars::numeric * rating_weight)
            / NULLIF(SUM(rating_weight), 0),
            2
        ) AS weighted_rating,

        ROUND(
            SUM(base_stars::numeric * rating_weight)
            / NULLIF(SUM(rating_weight), 0),
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

    FROM current_cq
    GROUP BY parent_org_id
)

SELECT
    parent_org_id,

    CURRENT_DATE AS snapshot_date,
    NULL::date AS previous_snapshot_date,

    clients_total,
    clients_with_rating,
    total_debt,

    weighted_rating,

    0::bigint AS clients_improved,
    0::bigint AS clients_worsened,
    clients_with_rating AS clients_stable,
    0::bigint AS clients_new,

    0::numeric AS improved_debt,
    0::numeric AS worsened_debt,

    'STABLE'::text AS portfolio_change_status,
    'Рейтинг рассчитан по Credit Quality V2'::text AS portfolio_change_label,

    base_weighted_rating,
    ROUND(base_weighted_rating - weighted_rating, 2) AS severity_portfolio_penalty,

    downgraded_by_severity_clients,
    critical_severity_clients,
    high_severity_clients,
    medium_severity_clients,
    low_severity_clients,
    no_severity_clients,

    'credit_quality_v2'::text AS rating_method

FROM parent_agg;