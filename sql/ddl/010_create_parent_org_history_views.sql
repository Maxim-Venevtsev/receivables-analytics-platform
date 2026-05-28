CREATE OR REPLACE VIEW core.v_parent_org_daily_history AS
WITH parent_daily AS (
    SELECT
        report_generated_date,
        parent_org_id,

        COUNT(DISTINCT client_id) AS client_count,
        COUNT(*) AS invoice_count,

        SUM(invoice_amount) AS total_debt,

        SUM(CASE WHEN is_overdue_real THEN invoice_amount ELSE 0 END) AS overdue_debt,
        SUM(CASE WHEN is_due_today THEN invoice_amount ELSE 0 END) AS due_today,
        SUM(
            CASE
                WHEN is_due_in_3_days AND NOT is_due_today
                THEN invoice_amount
                ELSE 0
            END
        ) AS due_soon_only,

        MAX(days_overdue_real) AS max_days_overdue

    FROM core.receivables_snapshot_fact

    GROUP BY
        report_generated_date,
        parent_org_id
)

SELECT
    report_generated_date,
    parent_org_id,

    client_count,
    invoice_count,
    total_debt,

    GREATEST(
        total_debt - overdue_debt - due_today - due_soon_only,
        0
    ) AS normal_debt,

    due_soon_only,
    due_today,
    overdue_debt,

    ROUND(
        overdue_debt / NULLIF(total_debt, 0) * 100,
        2
    ) AS overdue_share_pct,

    max_days_overdue

FROM parent_daily;