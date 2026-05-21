CREATE OR REPLACE VIEW core.v_client_rating_base AS

WITH client_snapshot AS (
    SELECT
        report_generated_date,
        client_id,
        client_name,
        parent_org_id,
        client_group,

        COUNT(*) AS invoice_count,
        SUM(invoice_amount) AS total_debt,

        SUM(
            CASE
                WHEN is_overdue_real
                THEN invoice_amount
                ELSE 0
            END
        ) AS overdue_debt,

        MAX(
            CASE
                WHEN is_overdue_real AND invoice_amount > 0
                THEN days_overdue_real
                ELSE 0
            END
        ) AS max_days_overdue

    FROM core.receivables_snapshot_fact

    WHERE report_generated_date >= (
        SELECT MAX(report_generated_date)
               - (
                    SELECT rating_window_days
                    FROM core.client_rating_config
                    LIMIT 1
                 )
        FROM core.receivables_snapshot_fact
    )

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
            ELSE LEAST(
                GREATEST(overdue_debt / total_debt * 100, 0),
                100
            )
        END AS overdue_share_pct,

        CASE
            WHEN overdue_debt > 0 THEN 1
            ELSE 0
        END AS has_overdue

    FROM client_snapshot
),

client_rating_base AS (
    SELECT
        client_id,
        client_name,
        parent_org_id,
        client_group,

        COUNT(*) AS snapshot_days,
        SUM(has_overdue) AS overdue_snapshot_days,

        AVG(overdue_share_pct) AS avg_overdue_share_pct,
        MAX(max_days_overdue) AS max_days_overdue,

        AVG(total_debt) AS avg_total_debt,
        STDDEV(total_debt) AS total_debt_volatility

    FROM client_snapshot_metrics

    GROUP BY
        client_id,
        client_name,
        parent_org_id,
        client_group
)

SELECT
    *,

    CASE
        WHEN snapshot_days = 0 THEN 0
        ELSE overdue_snapshot_days::numeric / snapshot_days
    END AS overdue_occurrence_ratio,

    CASE
        WHEN snapshot_days >= (
            SELECT min_full_confidence_snapshot_days
            FROM core.client_rating_config
            LIMIT 1
        )
        THEN 'FULL'

        WHEN snapshot_days >= 30
        THEN 'MEDIUM'

        ELSE 'LOW'
    END AS confidence_level

FROM client_rating_base;