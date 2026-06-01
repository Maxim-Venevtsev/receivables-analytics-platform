CREATE TABLE IF NOT EXISTS core.client_rating_history (
    snapshot_date date NOT NULL,
    client_id text NOT NULL,

    client_name text,
    parent_org_id text,
    client_group text,

    stars integer,
    rating_label text,
    rating_display_label text,
    confidence_level text,

    snapshot_days integer,
    overdue_snapshot_days integer,
    overdue_occurrence_ratio numeric,
    avg_overdue_share_pct numeric,
    max_days_overdue integer,

    created_at timestamp DEFAULT now(),

    PRIMARY KEY (snapshot_date, client_id)
);


CREATE OR REPLACE VIEW core.v_client_rating_history AS
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

    LAG(stars) OVER (
        PARTITION BY client_id
        ORDER BY snapshot_date
    ) AS previous_stars,

    stars - LAG(stars) OVER (
        PARTITION BY client_id
        ORDER BY snapshot_date
    ) AS stars_delta,

    CASE
        WHEN LAG(stars) OVER (
            PARTITION BY client_id
            ORDER BY snapshot_date
        ) IS NULL THEN 'NEW'

        WHEN stars > LAG(stars) OVER (
            PARTITION BY client_id
            ORDER BY snapshot_date
        ) THEN 'IMPROVED'

        WHEN stars < LAG(stars) OVER (
            PARTITION BY client_id
            ORDER BY snapshot_date
        ) THEN 'WORSENED'

        ELSE 'STABLE'
    END AS rating_change_status

FROM core.client_rating_history;


CREATE OR REPLACE VIEW core.v_client_rating_latest_change AS
WITH ranked AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY client_id
            ORDER BY snapshot_date DESC
        ) AS rn
    FROM core.v_client_rating_history
)
SELECT *
FROM ranked
WHERE rn = 1;