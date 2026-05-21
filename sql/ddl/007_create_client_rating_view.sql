CREATE OR REPLACE VIEW core.v_client_rating AS
WITH matched_rules AS (
    SELECT
        b.*,
        r.stars,
        r.label AS rating_label,

        ROW_NUMBER() OVER (
            PARTITION BY b.client_id
            ORDER BY r.stars DESC
        ) AS rn

    FROM core.v_client_rating_base b
    JOIN core.client_rating_rules r
      ON (
            r.max_overdue_occurrence_ratio IS NULL
            OR b.overdue_occurrence_ratio <= r.max_overdue_occurrence_ratio
         )
     AND (
            r.max_avg_overdue_share_pct IS NULL
            OR b.avg_overdue_share_pct <= r.max_avg_overdue_share_pct
         )
     AND (
            r.max_max_days_overdue IS NULL
            OR b.max_days_overdue <= r.max_max_days_overdue
         )
)

SELECT
    client_id,
    client_name,
    parent_org_id,
    client_group,

    snapshot_days,
    overdue_snapshot_days,
    overdue_occurrence_ratio,
    avg_overdue_share_pct,
    max_days_overdue,

    confidence_level,

    stars,
    rating_label,

    CASE
        WHEN confidence_level = 'FULL' THEN rating_label
        WHEN confidence_level = 'MEDIUM' THEN rating_label || ' · предварительно'
        ELSE rating_label || ' · мало истории'
    END AS rating_display_label

FROM matched_rules
WHERE rn = 1;