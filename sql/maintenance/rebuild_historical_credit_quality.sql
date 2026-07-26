-- Insert canonical Credit Quality V2 history for one explicit snapshot date.
-- Required bind parameter: :snapshot_date
-- Depends only on facts/config tables and backfill_rating_stage.
-- Creates no persistent objects.

WITH current_exposure AS (
    SELECT
        client_id,
        MAX(client_name) AS client_name,
        MAX(client_group) AS client_group,
        MAX(parent_org_id) AS parent_org_id,
        SUM(invoice_amount) AS total_debt,
        SUM(CASE WHEN is_overdue_real THEN invoice_amount ELSE 0 END) AS overdue_debt,
        SUM(CASE WHEN NOT is_overdue_real THEN invoice_amount ELSE 0 END) AS green_debt,
        SUM(
            CASE WHEN NOT is_overdue_real AND COALESCE(payment_term_days, 0) >= 45
            THEN invoice_amount ELSE 0 END
        ) AS green_45_plus_debt,
        SUM(
            CASE WHEN NOT is_overdue_real AND COALESCE(payment_term_days, 0) >= 60
            THEN invoice_amount ELSE 0 END
        ) AS green_60_plus_debt,
        SUM(
            CASE WHEN NOT is_overdue_real AND COALESCE(payment_term_days, 0) >= 90
            THEN invoice_amount ELSE 0 END
        ) AS green_90_plus_debt,
        SUM(
            CASE WHEN NOT is_overdue_real AND COALESCE(payment_term_days, 0) >= 120
            THEN invoice_amount ELSE 0 END
        ) AS green_120_plus_debt,
        ROUND(
            (
                SUM(COALESCE(payment_term_days, 0) * invoice_amount)
                / NULLIF(SUM(invoice_amount), 0)
            )::numeric,
            2
        ) AS weighted_avg_payment_term_days,
        MAX(payment_term_days) AS max_payment_term_days,
        MAX(days_overdue_real) AS max_days_overdue,
        COUNT(*) AS invoice_count
    FROM core.receivables_snapshot_fact
    WHERE report_generated_date = :snapshot_date
    GROUP BY client_id
),
invoice_event_source AS (
    SELECT
        client_id,
        print_invoice_number,
        order_number,
        invoice_date,
        payment_term_days,
        report_generated_date,
        LAG(payment_term_days) OVER (
            PARTITION BY client_id, print_invoice_number
            ORDER BY report_generated_date
        ) AS previous_payment_term_days
    FROM core.receivables_snapshot_fact
    WHERE report_generated_date <= :snapshot_date
),
invoice_snapshots AS (
    SELECT
        client_id,
        print_invoice_number,
        order_number,
        invoice_date,
        payment_term_days,
        report_generated_date,
        ROW_NUMBER() OVER (
            PARTITION BY client_id, print_invoice_number, order_number, invoice_date
            ORDER BY report_generated_date ASC
        ) AS rn_first,
        ROW_NUMBER() OVER (
            PARTITION BY client_id, print_invoice_number, order_number, invoice_date
            ORDER BY report_generated_date DESC
        ) AS rn_last
    FROM core.receivables_snapshot_fact
    WHERE report_generated_date <= :snapshot_date
      AND invoice_amount > 0
      AND print_invoice_number IS NOT NULL
),
invoice_history AS (
    SELECT
        client_id,
        print_invoice_number,
        order_number,
        invoice_date,
        MAX(payment_term_days) FILTER (WHERE rn_first = 1)
            AS original_payment_term_days,
        MAX(payment_term_days) FILTER (WHERE rn_last = 1)
            AS current_payment_term_days
    FROM invoice_snapshots
    GROUP BY client_id, print_invoice_number, order_number, invoice_date
),
shift_events AS (
    SELECT
        client_id,
        print_invoice_number,
        order_number,
        invoice_date,
        COUNT(*) AS term_shift_count
    FROM invoice_event_source
    WHERE previous_payment_term_days IS NOT NULL
      AND payment_term_days > previous_payment_term_days
    GROUP BY client_id, print_invoice_number, order_number, invoice_date
),
term_shift_invoices AS (
    SELECT
        h.client_id,
        h.print_invoice_number,
        h.order_number,
        h.invoice_date,
        h.current_payment_term_days - h.original_payment_term_days
            AS current_term_delta_days,
        COALESCE(e.term_shift_count, 0) AS term_shift_count
    FROM invoice_history h
    LEFT JOIN shift_events e
      ON h.client_id = e.client_id
     AND h.print_invoice_number = e.print_invoice_number
     AND h.order_number = e.order_number
     AND h.invoice_date = e.invoice_date
    WHERE COALESCE(e.term_shift_count, 0) > 0
       OR h.current_payment_term_days > h.original_payment_term_days
),
term_shift_client AS (
    SELECT
        client_id,
        SUM(COALESCE(term_shift_count, 0)) AS term_shift_count,
        MAX(COALESCE(term_shift_count, 0)) AS max_invoice_term_shift_count,
        SUM(COALESCE(current_term_delta_days, 0)) AS total_term_shift_delta_days,
        MAX(COALESCE(current_term_delta_days, 0)) AS max_term_shift_delta_days,
        COUNT(*) FILTER (
            WHERE COALESCE(term_shift_count, 0) >= 2
        ) AS repeated_shift_invoice_count,
        COUNT(*) FILTER (
            WHERE COALESCE(term_shift_count, 0) >= 3
        ) AS heavy_repeated_shift_invoice_count
    FROM term_shift_invoices
    GROUP BY client_id
),
credit_base AS (
    SELECT
        b.client_id,
        b.client_name,
        b.client_group,
        b.parent_org_id,
        r.stars AS base_stars,
        r.rating_label AS base_rating_label,
        r.rating_display_label AS base_rating_display_label,
        r.confidence_level,
        b.total_debt,
        b.overdue_debt,
        b.green_debt,
        b.green_45_plus_debt,
        b.green_60_plus_debt,
        b.green_90_plus_debt,
        b.green_120_plus_debt,
        ROUND((b.overdue_debt / NULLIF(b.total_debt, 0) * 100)::numeric, 2)
            AS overdue_share_pct,
        ROUND((b.green_90_plus_debt / NULLIF(b.total_debt, 0) * 100)::numeric, 2)
            AS green_90_plus_share_pct,
        ROUND((b.green_120_plus_debt / NULLIF(b.total_debt, 0) * 100)::numeric, 2)
            AS green_120_plus_share_pct,
        b.weighted_avg_payment_term_days,
        b.max_payment_term_days,
        b.max_days_overdue,
        b.invoice_count,
        COALESCE(ts.term_shift_count, 0) AS term_shift_count,
        COALESCE(ts.max_invoice_term_shift_count, 0) AS max_invoice_term_shift_count,
        COALESCE(ts.repeated_shift_invoice_count, 0) AS repeated_shift_invoice_count,
        COALESCE(ts.heavy_repeated_shift_invoice_count, 0)
            AS heavy_repeated_shift_invoice_count,
        COALESCE(ts.total_term_shift_delta_days, 0) AS total_term_shift_delta_days,
        COALESCE(ts.max_term_shift_delta_days, 0) AS max_term_shift_delta_days,
        CASE
            WHEN b.total_debt <= (
                SELECT max_total_debt FROM core.credit_quality_exposure_segments
                WHERE segment_name = 'small'
            )
            AND b.weighted_avg_payment_term_days <= (
                SELECT max_weighted_payment_term_days
                FROM core.credit_quality_exposure_segments
                WHERE segment_name = 'small'
            ) THEN 'small'
            WHEN b.total_debt <= (
                SELECT max_total_debt FROM core.credit_quality_exposure_segments
                WHERE segment_name = 'medium'
            )
            OR b.weighted_avg_payment_term_days <= (
                SELECT max_weighted_payment_term_days
                FROM core.credit_quality_exposure_segments
                WHERE segment_name = 'medium'
            ) THEN 'medium'
            ELSE 'large'
        END AS exposure_segment,
        CASE
            WHEN b.total_debt <= (
                SELECT max_total_debt FROM core.credit_quality_exposure_segments
                WHERE segment_name = 'small'
            )
            AND b.weighted_avg_payment_term_days <= (
                SELECT max_weighted_payment_term_days
                FROM core.credit_quality_exposure_segments
                WHERE segment_name = 'small'
            ) THEN (
                SELECT multiplier FROM core.credit_quality_exposure_segments
                WHERE segment_name = 'small'
            )
            WHEN b.total_debt <= (
                SELECT max_total_debt FROM core.credit_quality_exposure_segments
                WHERE segment_name = 'medium'
            )
            OR b.weighted_avg_payment_term_days <= (
                SELECT max_weighted_payment_term_days
                FROM core.credit_quality_exposure_segments
                WHERE segment_name = 'medium'
            ) THEN (
                SELECT multiplier FROM core.credit_quality_exposure_segments
                WHERE segment_name = 'medium'
            )
            ELSE (
                SELECT multiplier FROM core.credit_quality_exposure_segments
                WHERE segment_name = 'large'
            )
        END AS exposure_multiplier
    FROM current_exposure b
    LEFT JOIN backfill_rating_stage r
      ON r.snapshot_date = :snapshot_date
     AND r.client_id = b.client_id
    LEFT JOIN term_shift_client ts ON ts.client_id = b.client_id
),
scored AS (
    SELECT
        b.*,
        COALESCE((
            SELECT MAX(severity_points)
            FROM core.credit_quality_severity_rules r
            WHERE r.metric_name = 'weighted_avg_payment_term_days'
              AND b.weighted_avg_payment_term_days >= r.threshold
        ), 0) AS weighted_avg_payment_term_points,
        COALESCE((
            SELECT MAX(severity_points)
            FROM core.credit_quality_severity_rules r
            WHERE r.metric_name = 'max_payment_term_days'
              AND b.max_payment_term_days >= r.threshold
        ), 0) AS max_payment_term_points,
        COALESCE((
            SELECT MAX(severity_points)
            FROM core.credit_quality_severity_rules r
            WHERE r.metric_name = 'green_90_plus_share_pct'
              AND b.green_90_plus_share_pct >= r.threshold
        ), 0) AS green_90_plus_share_points,
        COALESCE((
            SELECT MAX(severity_points)
            FROM core.credit_quality_severity_rules r
            WHERE r.metric_name = 'green_120_plus_debt'
              AND b.green_120_plus_debt >= r.threshold
        ), 0) AS green_120_plus_debt_points,
        COALESCE((
            SELECT MAX(severity_points)
            FROM core.credit_quality_severity_rules r
            WHERE r.metric_name = 'term_shift_count'
              AND b.term_shift_count >= r.threshold
        ), 0) AS term_shift_count_points,
        COALESCE((
            SELECT MAX(severity_points)
            FROM core.credit_quality_repeated_shift_rules r
            WHERE r.metric_name = 'max_invoice_term_shift_count'
              AND b.max_invoice_term_shift_count >= r.threshold
        ), 0) AS max_invoice_term_shift_points,
        COALESCE((
            SELECT MAX(severity_points)
            FROM core.credit_quality_repeated_shift_rules r
            WHERE r.metric_name = 'repeated_shift_invoice_count'
              AND b.repeated_shift_invoice_count >= r.threshold
        ), 0) AS repeated_shift_invoice_points
    FROM credit_base b
),
aggregated AS (
    SELECT
        *,
        (
            weighted_avg_payment_term_points
            + max_payment_term_points
            + green_90_plus_share_points
            + green_120_plus_debt_points
            + term_shift_count_points
            + max_invoice_term_shift_points
            + repeated_shift_invoice_points
        ) AS raw_severity_points,
        ROUND(
            (
                weighted_avg_payment_term_points
                + max_payment_term_points
                + green_90_plus_share_points
                + green_120_plus_debt_points
                + term_shift_count_points
                + max_invoice_term_shift_points
                + repeated_shift_invoice_points
            ) * exposure_multiplier,
            2
        ) AS weighted_severity_points
    FROM scored
),
severity AS (
    SELECT
        *,
        ARRAY_REMOVE(ARRAY[
            CASE WHEN weighted_avg_payment_term_points > 0
                THEN 'длинная средневзвешенная отсрочка' END,
            CASE WHEN max_payment_term_points > 0
                THEN 'аномально длинная максимальная отсрочка' END,
            CASE WHEN green_90_plus_share_points > 0
                THEN 'высокая доля 90+ непросроченного долга' END,
            CASE WHEN green_120_plus_debt_points > 0
                THEN 'есть 120+ непросроченный долг' END,
            CASE WHEN term_shift_count_points > 0
                THEN 'переносы сроков оплаты' END,
            CASE WHEN max_invoice_term_shift_points > 0
                THEN 'повторные переносы по одной накладной' END,
            CASE WHEN repeated_shift_invoice_points > 0
                THEN 'повторные переносы по нескольким накладным' END
        ], NULL) AS severity_reasons,
        CASE
            WHEN weighted_severity_points >= 6 THEN 'CRITICAL'
            WHEN weighted_severity_points >= 4 THEN 'HIGH'
            WHEN weighted_severity_points >= 2 THEN 'MEDIUM'
            WHEN weighted_severity_points > 0 THEN 'LOW'
            ELSE 'NONE'
        END AS severity_level,
        COALESCE((
            SELECT penalty
            FROM core.credit_quality_penalty_mapping p
            WHERE aggregated.weighted_severity_points >= p.min_severity_points
            ORDER BY p.min_severity_points DESC
            LIMIT 1
        ), 0) AS severity_penalty
    FROM aggregated
),
final_rating AS (
    SELECT
        *,
        GREATEST(
            (
                SELECT config_value::integer
                FROM core.credit_quality_final_rating_config
                WHERE config_key = 'min_stars'
            ),
            FLOOR(base_stars::numeric - severity_penalty)::integer
        ) AS credit_quality_stars
    FROM severity
    WHERE base_stars IS NOT NULL
)
INSERT INTO backfill_credit_quality_stage (
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
    :snapshot_date,
    client_id,
    client_name,
    parent_org_id,
    client_group,
    base_stars,
    credit_quality_stars,
    CONCAT(
        credit_quality_stars,
        '★ · ',
        CASE
            WHEN severity_level = 'NONE'
            THEN 'без дополнительных severity-сигналов'
            ELSE CONCAT('severity: ', severity_level)
        END
    ),
    confidence_level,
    total_debt,
    overdue_debt,
    severity_level,
    severity_penalty,
    severity_reasons
FROM final_rating;
