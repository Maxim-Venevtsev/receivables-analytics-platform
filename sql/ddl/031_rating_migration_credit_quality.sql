-- ============================================================
-- 031_create_rating_migration_credit_quality.sql
-- Purpose:
--   Move rating migration views to Credit Quality V2.
-- ============================================================

DROP VIEW IF EXISTS core.v_executive_rating_migration_branches CASCADE;
DROP VIEW IF EXISTS core.v_executive_rating_migration_parent_orgs CASCADE;
DROP VIEW IF EXISTS core.v_executive_rating_migration_clients CASCADE;

CREATE TABLE IF NOT EXISTS core.client_credit_quality_history (
    snapshot_date date NOT NULL,
    client_id text NOT NULL,
    client_name text,
    parent_org_id text,
    client_group text,

    base_stars integer,
    credit_quality_stars integer,
    credit_quality_display_label text,
    confidence_level text,

    total_debt numeric,
    overdue_debt numeric,
    severity_level text,
    severity_penalty numeric,
    severity_reasons text[],

    created_at timestamp DEFAULT now(),

    CONSTRAINT pk_client_credit_quality_history
        PRIMARY KEY (snapshot_date, client_id)
);

INSERT INTO core.client_credit_quality_history (
    snapshot_date,
    client_id,
    client_name,
    parent_org_id,
    client_group,
    base_stars,
    credit_quality_stars,
    credit_quality_display_label,
    confidence_level,
    total_debt,
    overdue_debt,
    severity_level,
    severity_penalty,
    severity_reasons
)
SELECT
    COALESCE(
        (SELECT MAX(snapshot_date) FROM core.client_rating_history),
        CURRENT_DATE
    ) AS snapshot_date,
    client_id,
    client_name,
    parent_org_id,
    client_group,
    base_stars,
    credit_quality_stars,
    credit_quality_display_label,
    confidence_level,
    total_debt,
    overdue_debt,
    severity_level,
    severity_penalty,
    severity_reasons
FROM core.v_client_credit_quality_rating
ON CONFLICT (snapshot_date, client_id) DO UPDATE SET
    client_name = EXCLUDED.client_name,
    parent_org_id = EXCLUDED.parent_org_id,
    client_group = EXCLUDED.client_group,
    base_stars = EXCLUDED.base_stars,
    credit_quality_stars = EXCLUDED.credit_quality_stars,
    credit_quality_display_label = EXCLUDED.credit_quality_display_label,
    confidence_level = EXCLUDED.confidence_level,
    total_debt = EXCLUDED.total_debt,
    overdue_debt = EXCLUDED.overdue_debt,
    severity_level = EXCLUDED.severity_level,
    severity_penalty = EXCLUDED.severity_penalty,
    severity_reasons = EXCLUDED.severity_reasons,
    created_at = now();

CREATE OR REPLACE VIEW core.v_executive_rating_migration_clients AS
WITH periods AS (
    SELECT '28 дней'::text AS period_label, 28::integer AS period_days, 1::integer AS sort_order
    UNION ALL SELECT '90 дней', 90, 2
    UNION ALL SELECT '180 дней', 180, 3
    UNION ALL SELECT 'Все', NULL, 4
),
bounds AS (
    SELECT
        MIN(snapshot_date) AS min_snapshot_date,
        MAX(snapshot_date) AS max_snapshot_date
    FROM core.client_credit_quality_history
),
period_bounds AS (
    SELECT
        p.period_label,
        p.period_days,
        p.sort_order,
        CASE
            WHEN p.period_days IS NULL THEN b.min_snapshot_date
            ELSE COALESCE(
                (
                    SELECT MIN(h.snapshot_date)
                    FROM core.client_credit_quality_history h
                    WHERE h.snapshot_date >= b.max_snapshot_date - p.period_days
                ),
                b.min_snapshot_date
            )
        END AS start_snapshot_date,
        b.max_snapshot_date AS end_snapshot_date
    FROM periods p
    CROSS JOIN bounds b
),
client_universe AS (
    SELECT DISTINCT client_id
    FROM core.client_credit_quality_history
),
migration AS (
    SELECT
        p.period_label,
        p.period_days,
        p.sort_order,

        p.start_snapshot_date,
        p.end_snapshot_date,

        end_h.client_id,
        end_h.client_name,
        end_h.parent_org_id,
        end_h.client_group,

        start_h.credit_quality_stars AS start_stars,
        end_h.credit_quality_stars AS end_stars,

        start_h.credit_quality_display_label AS start_rating_label,
        end_h.credit_quality_display_label AS end_rating_label,

        start_h.confidence_level AS start_confidence_level,
        end_h.confidence_level AS end_confidence_level,

        end_h.credit_quality_stars - start_h.credit_quality_stars AS rating_delta

    FROM period_bounds p
    CROSS JOIN client_universe u

    JOIN LATERAL (
        SELECT h.*
        FROM core.client_credit_quality_history h
        WHERE h.client_id = u.client_id
          AND h.snapshot_date <= p.end_snapshot_date
        ORDER BY h.snapshot_date DESC
        LIMIT 1
    ) end_h ON TRUE

    LEFT JOIN core.client_credit_quality_history start_h
        ON start_h.client_id = u.client_id
       AND start_h.snapshot_date = p.start_snapshot_date
)
SELECT
    *,
    CASE
        WHEN rating_delta > 0 THEN 'improved'
        WHEN rating_delta < 0 THEN 'worsened'
        ELSE 'stable'
    END AS migration_status,

    CASE
        WHEN rating_delta > 0 THEN 'Рейтинг улучшился'
        WHEN rating_delta < 0 THEN 'Рейтинг ухудшился'
        ELSE 'Рейтинг стабилен'
    END AS migration_label,

    CASE
        WHEN rating_delta > 0 THEN '+' || rating_delta::text
        ELSE rating_delta::text
    END AS rating_change_label

FROM migration;

CREATE OR REPLACE VIEW core.v_executive_rating_migration_parent_orgs AS
SELECT
    period_label,
    period_days,
    sort_order,
    start_snapshot_date,
    end_snapshot_date,
    parent_org_id,

    COUNT(DISTINCT client_id) AS client_count,

    ROUND(AVG(start_stars)::numeric, 2) AS start_rating,
    ROUND(AVG(end_stars)::numeric, 2) AS end_rating,
    ROUND((AVG(end_stars) - AVG(start_stars))::numeric, 2) AS rating_delta,

    COUNT(*) FILTER (WHERE rating_delta > 0) AS improved_clients,
    COUNT(*) FILTER (WHERE rating_delta < 0) AS worsened_clients,
    COUNT(*) FILTER (WHERE rating_delta = 0) AS stable_clients

FROM core.v_executive_rating_migration_clients
WHERE parent_org_id IS NOT NULL
GROUP BY
    period_label,
    period_days,
    sort_order,
    start_snapshot_date,
    end_snapshot_date,
    parent_org_id;

CREATE OR REPLACE VIEW core.v_executive_rating_migration_branches AS
SELECT
    period_label,
    period_days,
    sort_order,
    start_snapshot_date,
    end_snapshot_date,
    client_group,

    COUNT(DISTINCT client_id) AS client_count,

    ROUND(AVG(start_stars)::numeric, 2) AS start_rating,
    ROUND(AVG(end_stars)::numeric, 2) AS end_rating,
    ROUND((AVG(end_stars) - AVG(start_stars))::numeric, 2) AS rating_delta,

    COUNT(*) FILTER (WHERE rating_delta > 0) AS improved_clients,
    COUNT(*) FILTER (WHERE rating_delta < 0) AS worsened_clients,
    COUNT(*) FILTER (WHERE rating_delta = 0) AS stable_clients

FROM core.v_executive_rating_migration_clients
WHERE client_group IS NOT NULL
GROUP BY
    period_label,
    period_days,
    sort_order,
    start_snapshot_date,
    end_snapshot_date,
    client_group;

CREATE OR REPLACE VIEW core.v_executive_rating_migration_summary AS
SELECT
    period_label,
    period_days,
    sort_order,
    start_snapshot_date,
    end_snapshot_date,

    COUNT(*) AS client_count,

    COUNT(*) FILTER (WHERE rating_delta > 0) AS improved_clients,
    COUNT(*) FILTER (WHERE rating_delta < 0) AS worsened_clients,
    COUNT(*) FILTER (WHERE rating_delta = 0) AS stable_clients,

    COUNT(*) FILTER (WHERE rating_delta > 0) AS upgraded_clients,
    COUNT(*) FILTER (WHERE rating_delta < 0) AS downgraded_clients,
    COUNT(*) FILTER (WHERE rating_delta = 0) AS unchanged_clients,

    0::bigint AS new_clients,

    COUNT(*) FILTER (WHERE rating_delta > 0)
    -
    COUNT(*) FILTER (WHERE rating_delta < 0) AS net_migration_clients,

    ROUND(AVG(start_stars)::numeric, 2) AS start_rating,
    ROUND(AVG(end_stars)::numeric, 2) AS end_rating,
    ROUND((AVG(end_stars) - AVG(start_stars))::numeric, 2) AS rating_delta

FROM core.v_executive_rating_migration_clients
GROUP BY
    period_label,
    period_days,
    sort_order,
    start_snapshot_date,
    end_snapshot_date;
