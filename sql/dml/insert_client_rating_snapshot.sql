INSERT INTO core.client_rating_history (
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
    (
        SELECT MAX(report_generated_date)
        FROM core.receivables_snapshot_fact
    ) AS snapshot_date,

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

FROM core.v_client_rating

ON CONFLICT (snapshot_date, client_id)
DO UPDATE SET
    client_name = EXCLUDED.client_name,
    parent_org_id = EXCLUDED.parent_org_id,
    client_group = EXCLUDED.client_group,

    stars = EXCLUDED.stars,
    rating_label = EXCLUDED.rating_label,
    rating_display_label = EXCLUDED.rating_display_label,
    confidence_level = EXCLUDED.confidence_level,

    snapshot_days = EXCLUDED.snapshot_days,
    overdue_snapshot_days = EXCLUDED.overdue_snapshot_days,
    overdue_occurrence_ratio = EXCLUDED.overdue_occurrence_ratio,
    avg_overdue_share_pct = EXCLUDED.avg_overdue_share_pct,
    max_days_overdue = EXCLUDED.max_days_overdue;