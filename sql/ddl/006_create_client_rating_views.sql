CREATE OR REPLACE VIEW core.v_client_rating_base AS

WITH snapshot_stats AS (
    SELECT
        client_id,
        client_name,
        parent_org_id,
        client_group,

        COUNT(DISTINCT report_generated_date) AS snapshot_days,

        COUNT(DISTINCT CASE
            WHEN is_overdue_real
            THEN report_generated_date
        END) AS overdue_snapshot_days,

        AVG(
            CASE
                WHEN invoice_amount > 0
                THEN
                    CASE
                        WHEN is_overdue_real
                        THEN 100
                        ELSE 0
                    END
                ELSE 0
            END
        ) AS avg_overdue_share_pct,

        MAX(days_overdue_real) AS max_days_overdue,

        AVG(invoice_amount) AS avg_invoice_amount,
        STDDEV(invoice_amount) AS invoice_amount_volatility

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

FROM snapshot_stats;