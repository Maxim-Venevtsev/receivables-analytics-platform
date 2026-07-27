-- 038_consolidate_credit_quality_term_shift.sql
-- Consolidate repeated-shift metrics into the existing Credit Quality base aggregation.

BEGIN;

CREATE OR REPLACE VIEW core.v_client_credit_quality_base AS
WITH term_shift AS (
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
    FROM core.v_term_shift_invoice_summary
    GROUP BY client_id
)

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

    b.overdue_share_pct,
    b.green_90_plus_share_of_total_pct AS green_90_plus_share_pct,
    b.green_120_plus_share_of_total_pct AS green_120_plus_share_pct,

    b.weighted_avg_payment_term_days,
    b.max_payment_term_days,
    b.max_days_overdue,
    b.invoice_count,

    COALESCE(ts.term_shift_count, 0) AS term_shift_count,
    COALESCE(ts.max_invoice_term_shift_count, 0) AS max_invoice_term_shift_count,
    COALESCE(ts.total_term_shift_delta_days, 0) AS total_term_shift_delta_days,
    COALESCE(ts.max_term_shift_delta_days, 0) AS max_term_shift_delta_days,

    CASE
        WHEN
            b.total_debt <= (
                SELECT max_total_debt
                FROM core.credit_quality_exposure_segments
                WHERE segment_name = 'small'
            )
            AND b.weighted_avg_payment_term_days <= (
                SELECT max_weighted_payment_term_days
                FROM core.credit_quality_exposure_segments
                WHERE segment_name = 'small'
            )
        THEN 'small'

        WHEN
            b.total_debt <= (
                SELECT max_total_debt
                FROM core.credit_quality_exposure_segments
                WHERE segment_name = 'medium'
            )
            OR b.weighted_avg_payment_term_days <= (
                SELECT max_weighted_payment_term_days
                FROM core.credit_quality_exposure_segments
                WHERE segment_name = 'medium'
            )
        THEN 'medium'

        ELSE 'large'
    END AS exposure_segment,

    CASE
        WHEN
            b.total_debt <= (
                SELECT max_total_debt
                FROM core.credit_quality_exposure_segments
                WHERE segment_name = 'small'
            )
            AND b.weighted_avg_payment_term_days <= (
                SELECT max_weighted_payment_term_days
                FROM core.credit_quality_exposure_segments
                WHERE segment_name = 'small'
            )
        THEN (
            SELECT multiplier
            FROM core.credit_quality_exposure_segments
            WHERE segment_name = 'small'
        )

        WHEN
            b.total_debt <= (
                SELECT max_total_debt
                FROM core.credit_quality_exposure_segments
                WHERE segment_name = 'medium'
            )
            OR b.weighted_avg_payment_term_days <= (
                SELECT max_weighted_payment_term_days
                FROM core.credit_quality_exposure_segments
                WHERE segment_name = 'medium'
            )
        THEN (
            SELECT multiplier
            FROM core.credit_quality_exposure_segments
            WHERE segment_name = 'medium'
        )

        ELSE (
            SELECT multiplier
            FROM core.credit_quality_exposure_segments
            WHERE segment_name = 'large'
        )
    END AS exposure_multiplier,

    COALESCE(ts.repeated_shift_invoice_count, 0) AS repeated_shift_invoice_count,
    COALESCE(ts.heavy_repeated_shift_invoice_count, 0) AS heavy_repeated_shift_invoice_count

FROM core.v_executive_client_risk_bubble_base b

LEFT JOIN core.v_client_rating r
    ON b.client_id = r.client_id

LEFT JOIN term_shift ts
    ON b.client_id = ts.client_id;


CREATE OR REPLACE VIEW core.v_client_credit_quality_severity AS
WITH scored AS (
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

    FROM core.v_client_credit_quality_base b
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
)

SELECT
    *,

    ARRAY_REMOVE(ARRAY[
        CASE
            WHEN weighted_avg_payment_term_points > 0
            THEN 'длинная средневзвешенная отсрочка'
        END,
        CASE
            WHEN max_payment_term_points > 0
            THEN 'аномально длинная максимальная отсрочка'
        END,
        CASE
            WHEN green_90_plus_share_points > 0
            THEN 'высокая доля 90+ непросроченного долга'
        END,
        CASE
            WHEN green_120_plus_debt_points > 0
            THEN 'есть 120+ непросроченный долг'
        END,
        CASE
            WHEN term_shift_count_points > 0
            THEN 'переносы сроков оплаты'
        END,
        CASE
            WHEN max_invoice_term_shift_points > 0
            THEN 'повторные переносы по одной накладной'
        END,
        CASE
            WHEN repeated_shift_invoice_points > 0
            THEN 'повторные переносы по нескольким накладным'
        END
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

FROM aggregated;

COMMIT;
