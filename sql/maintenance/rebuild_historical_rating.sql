-- Insert canonical base-rating history for one explicit snapshot date.
-- Required bind parameter: :snapshot_date
-- Creates no persistent objects.

WITH client_snapshot AS (
    SELECT
        report_generated_date,
        client_id,
        client_name,
        parent_org_id,
        client_group,
        SUM(invoice_amount) AS total_debt,
        SUM(CASE WHEN is_overdue_real THEN invoice_amount ELSE 0 END) AS overdue_debt,
        MAX(
            CASE
                WHEN is_overdue_real AND invoice_amount > 0
                THEN days_overdue_real
                ELSE 0
            END
        ) AS max_days_overdue
    FROM core.receivables_snapshot_fact
    WHERE report_generated_date >= (
        :snapshot_date
        - (SELECT rating_window_days FROM core.client_rating_config LIMIT 1)
    )
      AND report_generated_date <= :snapshot_date
    GROUP BY
        report_generated_date,
        client_id,
        client_name,
        parent_org_id,
        client_group
),
client_snapshot_metrics AS (
    SELECT
        *,
        CASE
            WHEN total_debt <= 0 THEN 0
            ELSE LEAST(GREATEST(overdue_debt / total_debt * 100, 0), 100)
        END AS overdue_share_pct,
        CASE WHEN overdue_debt > 0 THEN 1 ELSE 0 END AS has_overdue
    FROM client_snapshot
),
rating_base AS (
    SELECT
        client_id,
        client_name,
        parent_org_id,
        client_group,
        COUNT(*) AS snapshot_days,
        SUM(has_overdue) AS overdue_snapshot_days,
        AVG(overdue_share_pct) AS avg_overdue_share_pct,
        MAX(max_days_overdue) AS max_days_overdue,
        CASE
            WHEN COUNT(*) >= (
                SELECT min_full_confidence_snapshot_days
                FROM core.client_rating_config
                LIMIT 1
            ) THEN 'FULL'
            WHEN COUNT(*) >= 30 THEN 'MEDIUM'
            ELSE 'LOW'
        END AS confidence_level
    FROM client_snapshot_metrics
    GROUP BY client_id, client_name, parent_org_id, client_group
),
rating_metrics AS (
    SELECT
        *,
        CASE
            WHEN snapshot_days = 0 THEN 0
            ELSE overdue_snapshot_days::numeric / snapshot_days
        END AS overdue_occurrence_ratio
    FROM rating_base
),
matched_rules AS (
    SELECT
        b.*,
        r.stars,
        r.label AS rating_label,
        ROW_NUMBER() OVER (
            PARTITION BY b.client_id
            ORDER BY r.stars DESC
        ) AS rn
    FROM rating_metrics b
    JOIN core.client_rating_rules r
      ON (r.max_overdue_occurrence_ratio IS NULL
          OR b.overdue_occurrence_ratio <= r.max_overdue_occurrence_ratio)
     AND (r.max_avg_overdue_share_pct IS NULL
          OR b.avg_overdue_share_pct <= r.max_avg_overdue_share_pct)
     AND (r.max_max_days_overdue IS NULL
          OR b.max_days_overdue <= r.max_max_days_overdue)
)
INSERT INTO backfill_rating_stage (
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
    max_days_overdue
)
SELECT
    :snapshot_date,
    client_id,
    client_name,
    parent_org_id,
    client_group,
    stars,
    rating_label,
    CASE
        WHEN confidence_level = 'FULL' THEN rating_label
        WHEN confidence_level = 'MEDIUM' THEN rating_label || ' · предварительно'
        ELSE rating_label || ' · мало истории'
    END,
    confidence_level,
    snapshot_days,
    overdue_snapshot_days,
    overdue_occurrence_ratio,
    avg_overdue_share_pct,
    max_days_overdue
FROM matched_rules
WHERE rn = 1;
