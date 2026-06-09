-- 021_rating_migration_analytics.sql
-- Rating Migration Analytics:
-- start-of-period rating vs end-of-period rating

DROP VIEW IF EXISTS core.v_executive_rating_migration_matrix;
DROP VIEW IF EXISTS core.v_executive_rating_migration_summary;
DROP VIEW IF EXISTS core.v_executive_rating_migration_clients;
DROP VIEW IF EXISTS core.v_executive_rating_migration_periods;


CREATE OR REPLACE VIEW core.v_executive_rating_migration_periods AS
WITH dates AS (
    SELECT
        MIN(snapshot_date) AS min_snapshot_date,
        MAX(snapshot_date) AS max_snapshot_date
    FROM core.client_rating_history
),
periods AS (
    SELECT '28 дней' AS period_label, 28 AS period_days, 1 AS sort_order
    UNION ALL
    SELECT '90 дней', 90, 2
    UNION ALL
    SELECT '180 дней', 180, 3
    UNION ALL
    SELECT 'Все', NULL, 4
)
SELECT
    p.period_label,
    p.period_days,
    p.sort_order,

    CASE
        WHEN p.period_days IS NULL THEN d.min_snapshot_date
        ELSE COALESCE(
            (
                SELECT MAX(h.snapshot_date)
                FROM core.client_rating_history h
                WHERE h.snapshot_date <= d.max_snapshot_date - (p.period_days || ' days')::interval
            ),
            d.min_snapshot_date
        )
    END AS start_snapshot_date,

    d.max_snapshot_date AS end_snapshot_date

FROM periods p
CROSS JOIN dates d;


CREATE OR REPLACE VIEW core.v_executive_rating_migration_clients AS
WITH start_ratings AS (
    SELECT
        p.period_label,
        p.period_days,
        p.sort_order,
        p.start_snapshot_date,
        p.end_snapshot_date,

        h.client_id,
        h.client_name,
        h.parent_org_id,
        h.client_group,
        h.stars AS start_stars,
        h.rating_display_label AS start_rating_label,
        h.confidence_level AS start_confidence_level

    FROM core.v_executive_rating_migration_periods p
    JOIN core.client_rating_history h
        ON h.snapshot_date = p.start_snapshot_date
),

end_ratings AS (
    SELECT
        p.period_label,
        p.period_days,
        p.sort_order,
        p.start_snapshot_date,
        p.end_snapshot_date,

        h.client_id,
        h.client_name,
        h.parent_org_id,
        h.client_group,
        h.stars AS end_stars,
        h.rating_display_label AS end_rating_label,
        h.confidence_level AS end_confidence_level

    FROM core.v_executive_rating_migration_periods p
    JOIN core.client_rating_history h
        ON h.snapshot_date = p.end_snapshot_date
)

SELECT
    COALESCE(e.period_label, s.period_label) AS period_label,
    COALESCE(e.period_days, s.period_days) AS period_days,
    COALESCE(e.sort_order, s.sort_order) AS sort_order,

    COALESCE(e.start_snapshot_date, s.start_snapshot_date) AS start_snapshot_date,
    COALESCE(e.end_snapshot_date, s.end_snapshot_date) AS end_snapshot_date,

    COALESCE(e.client_id, s.client_id) AS client_id,
    COALESCE(e.client_name, s.client_name) AS client_name,
    COALESCE(e.parent_org_id, s.parent_org_id) AS parent_org_id,
    COALESCE(e.client_group, s.client_group) AS client_group,

    s.start_stars,
    e.end_stars,

    s.start_rating_label,
    e.end_rating_label,

    s.start_confidence_level,
    e.end_confidence_level,

    CASE
        WHEN s.start_stars IS NOT NULL AND e.end_stars IS NOT NULL
        THEN e.end_stars - s.start_stars
        ELSE NULL
    END AS rating_delta,

    CASE
        WHEN s.client_id IS NULL THEN 'NEW'
        WHEN e.client_id IS NULL THEN 'LOST'
        WHEN e.end_stars > s.start_stars THEN 'UPGRADED'
        WHEN e.end_stars < s.start_stars THEN 'DOWNGRADED'
        ELSE 'UNCHANGED'
    END AS migration_status,

    CASE
        WHEN s.client_id IS NULL THEN 'Новый'
        WHEN e.client_id IS NULL THEN 'Исчез'
        WHEN e.end_stars > s.start_stars THEN 'Повысился'
        WHEN e.end_stars < s.start_stars THEN 'Понизился'
        ELSE 'Без изменений'
    END AS migration_label,

    CASE
        WHEN s.client_id IS NULL THEN 'Новый клиент в рейтинге'
        WHEN e.client_id IS NULL THEN 'Клиент исчез из рейтинга'
        WHEN e.end_stars > s.start_stars THEN 'Рейтинг улучшился'
        WHEN e.end_stars < s.start_stars THEN 'Рейтинг ухудшился'
        ELSE 'Рейтинг не изменился'
    END AS rating_change_label

FROM start_ratings s
FULL OUTER JOIN end_ratings e
    ON s.period_label = e.period_label
   AND s.client_id = e.client_id;


CREATE OR REPLACE VIEW core.v_executive_rating_migration_summary AS
SELECT
    period_label,
    period_days,
    sort_order,
    start_snapshot_date,
    end_snapshot_date,

    COUNT(*) AS clients_total,

    COUNT(*) FILTER (WHERE start_stars IS NOT NULL AND end_stars IS NOT NULL) AS clients_with_both_ratings,

    COUNT(*) FILTER (WHERE migration_status = 'UPGRADED') AS upgraded_clients,
    COUNT(*) FILTER (WHERE migration_status = 'DOWNGRADED') AS downgraded_clients,
    COUNT(*) FILTER (WHERE migration_status = 'UNCHANGED') AS unchanged_clients,
    COUNT(*) FILTER (WHERE migration_status = 'NEW') AS new_clients,
    COUNT(*) FILTER (WHERE migration_status = 'LOST') AS lost_clients,

    COALESCE(SUM(rating_delta), 0) AS net_rating_delta,

    COUNT(*) FILTER (WHERE migration_status = 'UPGRADED')
    - COUNT(*) FILTER (WHERE migration_status = 'DOWNGRADED') AS net_migration_clients,

    ROUND(AVG(start_stars::numeric) FILTER (WHERE start_stars IS NOT NULL), 2) AS avg_start_rating,
    ROUND(AVG(end_stars::numeric) FILTER (WHERE end_stars IS NOT NULL), 2) AS avg_end_rating,

    ROUND(
        AVG(end_stars::numeric) FILTER (WHERE end_stars IS NOT NULL)
        - AVG(start_stars::numeric) FILTER (WHERE start_stars IS NOT NULL),
        2
    ) AS avg_rating_change

FROM core.v_executive_rating_migration_clients
GROUP BY
    period_label,
    period_days,
    sort_order,
    start_snapshot_date,
    end_snapshot_date;


CREATE OR REPLACE VIEW core.v_executive_rating_migration_matrix AS
SELECT
    period_label,
    period_days,
    sort_order,
    start_snapshot_date,
    end_snapshot_date,

    start_stars,
    end_stars,

    CONCAT(start_stars::text, '★ → ', end_stars::text, '★') AS migration_path,

    COUNT(*) AS client_count,

    COUNT(*) FILTER (WHERE migration_status = 'UPGRADED') AS upgraded_clients,
    COUNT(*) FILTER (WHERE migration_status = 'DOWNGRADED') AS downgraded_clients,
    COUNT(*) FILTER (WHERE migration_status = 'UNCHANGED') AS unchanged_clients,

    COALESCE(SUM(rating_delta), 0) AS total_rating_delta

FROM core.v_executive_rating_migration_clients
WHERE start_stars IS NOT NULL
  AND end_stars IS NOT NULL
GROUP BY
    period_label,
    period_days,
    sort_order,
    start_snapshot_date,
    end_snapshot_date,
    start_stars,
    end_stars;