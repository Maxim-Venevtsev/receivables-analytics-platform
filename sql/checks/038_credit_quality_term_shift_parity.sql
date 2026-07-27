-- Exact P2A parity validation. Every difference_count must be zero.
WITH old_term_shift AS (
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
),
old_scored AS (
    SELECT
        b.client_id,
        b.base_stars,
        COALESCE(o.term_shift_count, 0) AS term_shift_count,
        COALESCE(o.max_invoice_term_shift_count, 0) AS max_invoice_term_shift_count,
        COALESCE(o.total_term_shift_delta_days, 0) AS total_term_shift_delta_days,
        COALESCE(o.max_term_shift_delta_days, 0) AS max_term_shift_delta_days,
        COALESCE(o.repeated_shift_invoice_count, 0) AS repeated_shift_invoice_count,
        COALESCE(o.heavy_repeated_shift_invoice_count, 0)
            AS heavy_repeated_shift_invoice_count,
        b.exposure_multiplier,
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
              AND COALESCE(o.term_shift_count, 0) >= r.threshold
        ), 0) AS term_shift_count_points,
        COALESCE((
            SELECT MAX(severity_points)
            FROM core.credit_quality_repeated_shift_rules r
            WHERE r.metric_name = 'max_invoice_term_shift_count'
              AND COALESCE(o.max_invoice_term_shift_count, 0) >= r.threshold
        ), 0) AS max_invoice_term_shift_points,
        COALESCE((
            SELECT MAX(severity_points)
            FROM core.credit_quality_repeated_shift_rules r
            WHERE r.metric_name = 'repeated_shift_invoice_count'
              AND COALESCE(o.repeated_shift_invoice_count, 0) >= r.threshold
        ), 0) AS repeated_shift_invoice_points
    FROM core.v_client_credit_quality_base b
    LEFT JOIN old_term_shift o
        ON b.client_id = o.client_id
),
old_aggregated AS (
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
    FROM old_scored
),
old_severity AS (
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
            WHERE old_aggregated.weighted_severity_points >= p.min_severity_points
            ORDER BY p.min_severity_points DESC
            LIMIT 1
        ), 0) AS severity_penalty
    FROM old_aggregated
),
old_result AS (
    SELECT
        client_id,
        term_shift_count,
        max_invoice_term_shift_count,
        total_term_shift_delta_days,
        max_term_shift_delta_days,
        repeated_shift_invoice_count,
        heavy_repeated_shift_invoice_count,
        raw_severity_points,
        weighted_severity_points,
        severity_level,
        severity_penalty,
        severity_reasons,
        base_stars,
        GREATEST(
            (
                SELECT config_value::INT
                FROM core.credit_quality_final_rating_config
                WHERE config_key = 'min_stars'
            ),
            FLOOR(base_stars::numeric - severity_penalty)::INT
        ) AS credit_quality_stars,
        GREATEST(
            (
                SELECT config_value::INT
                FROM core.credit_quality_final_rating_config
                WHERE config_key = 'min_stars'
            ),
            FLOOR(base_stars::numeric - severity_penalty)::INT
        ) < base_stars AS rating_downgraded_by_severity
    FROM old_severity
    WHERE base_stars IS NOT NULL
),
new_result AS (
    SELECT
        client_id,
        term_shift_count,
        max_invoice_term_shift_count,
        total_term_shift_delta_days,
        max_term_shift_delta_days,
        repeated_shift_invoice_count,
        heavy_repeated_shift_invoice_count,
        raw_severity_points,
        weighted_severity_points,
        severity_level,
        severity_penalty,
        severity_reasons,
        base_stars,
        credit_quality_stars,
        rating_downgraded_by_severity
    FROM core.v_client_credit_quality_rating
),
old_except_new AS (
    SELECT * FROM old_result
    EXCEPT ALL
    SELECT * FROM new_result
),
new_except_old AS (
    SELECT * FROM new_result
    EXCEPT ALL
    SELECT * FROM old_result
),
base_old AS (
    SELECT
        b.client_id,
        COALESCE(o.term_shift_count, 0) AS term_shift_count,
        COALESCE(o.max_invoice_term_shift_count, 0) AS max_invoice_term_shift_count,
        COALESCE(o.total_term_shift_delta_days, 0) AS total_term_shift_delta_days,
        COALESCE(o.max_term_shift_delta_days, 0) AS max_term_shift_delta_days,
        COALESCE(o.repeated_shift_invoice_count, 0) AS repeated_shift_invoice_count,
        COALESCE(o.heavy_repeated_shift_invoice_count, 0)
            AS heavy_repeated_shift_invoice_count
    FROM core.v_client_credit_quality_base b
    LEFT JOIN old_term_shift o
        ON b.client_id = o.client_id
),
base_new AS (
    SELECT
        client_id,
        term_shift_count,
        max_invoice_term_shift_count,
        total_term_shift_delta_days,
        max_term_shift_delta_days,
        repeated_shift_invoice_count,
        heavy_repeated_shift_invoice_count
    FROM core.v_client_credit_quality_base
),
base_old_except_new AS (
    SELECT * FROM base_old
    EXCEPT ALL
    SELECT * FROM base_new
),
base_new_except_old AS (
    SELECT * FROM base_new
    EXCEPT ALL
    SELECT * FROM base_old
)
SELECT 'old_result EXCEPT ALL new_result' AS check_name, COUNT(*) AS difference_count
FROM old_except_new
UNION ALL
SELECT 'new_result EXCEPT ALL old_result', COUNT(*)
FROM new_except_old
UNION ALL
SELECT 'old_base EXCEPT ALL new_base', COUNT(*)
FROM base_old_except_new
UNION ALL
SELECT 'new_base EXCEPT ALL old_base', COUNT(*)
FROM base_new_except_old
UNION ALL
SELECT 'duplicate client_id in base', COALESCE(SUM(client_rows - 1), 0)
FROM (
    SELECT client_id, COUNT(*) AS client_rows
    FROM core.v_client_credit_quality_base
    GROUP BY client_id
    HAVING COUNT(*) > 1
) duplicates
UNION ALL
SELECT 'duplicate client_id in rating', COALESCE(SUM(client_rows - 1), 0)
FROM (
    SELECT client_id, COUNT(*) AS client_rows
    FROM core.v_client_credit_quality_rating
    GROUP BY client_id
    HAVING COUNT(*) > 1
) duplicates
ORDER BY check_name;
