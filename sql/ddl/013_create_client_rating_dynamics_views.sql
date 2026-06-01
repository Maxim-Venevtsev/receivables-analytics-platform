CREATE OR REPLACE VIEW core.v_client_rating_dynamics AS
WITH rating_with_lags AS (
    SELECT
        snapshot_date,
        client_id,
        client_name,
        parent_org_id,
        client_group,

        stars,
        rating_label,
        rating_display_label,
        confidence_level,

        snapshot_days,
        overdue_snapshot_days,
        overdue_occurrence_ratio,
        avg_overdue_share_pct,
        max_days_overdue,

        LAG(snapshot_date) OVER (
            PARTITION BY client_id
            ORDER BY snapshot_date
        ) AS previous_snapshot_date,

        LAG(stars) OVER (
            PARTITION BY client_id
            ORDER BY snapshot_date
        ) AS previous_stars,

        LAG(rating_label) OVER (
            PARTITION BY client_id
            ORDER BY snapshot_date
        ) AS previous_rating_label

    FROM core.client_rating_history
),

rating_dynamics AS (
    SELECT
        *,

        stars - previous_stars AS rating_delta,

        CASE
            WHEN previous_stars IS NULL THEN 'NEW'
            WHEN stars > previous_stars THEN 'IMPROVED'
            WHEN stars < previous_stars THEN 'WORSENED'
            ELSE 'STABLE'
        END AS rating_change_status,

        CASE
            WHEN previous_stars IS NULL THEN 'Новый в истории'
            WHEN stars > previous_stars THEN 'Рейтинг улучшился'
            WHEN stars < previous_stars THEN 'Рейтинг ухудшился'
            ELSE 'Без изменений'
        END AS rating_change_label

    FROM rating_with_lags
)

SELECT *
FROM rating_dynamics;


CREATE OR REPLACE VIEW core.v_client_rating_latest_dynamics AS
WITH ranked AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY client_id
            ORDER BY snapshot_date DESC
        ) AS rn
    FROM core.v_client_rating_dynamics
)
SELECT *
FROM ranked
WHERE rn = 1;


CREATE OR REPLACE VIEW core.v_client_rating_change_events AS
SELECT
    snapshot_date,
    previous_snapshot_date,

    client_id,
    client_name,
    parent_org_id,
    client_group,

    previous_stars,
    stars,
    rating_delta,

    previous_rating_label,
    rating_label,
    rating_display_label,
    confidence_level,

    rating_change_status,
    rating_change_label

FROM core.v_client_rating_dynamics
WHERE rating_change_status IN ('IMPROVED', 'WORSENED');