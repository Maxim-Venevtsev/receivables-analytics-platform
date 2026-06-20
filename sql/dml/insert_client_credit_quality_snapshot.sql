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
    (
        SELECT MAX(report_generated_date)
        FROM core.receivables_snapshot_fact
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

ON CONFLICT (snapshot_date, client_id)
DO UPDATE SET
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
