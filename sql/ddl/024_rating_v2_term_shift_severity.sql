-- 024_rating_v2_term_shift_severity.sql
-- Rating V2: repeated term-shift severity extension

DROP VIEW IF EXISTS core.v_client_credit_quality_rating;
DROP VIEW IF EXISTS core.v_client_credit_quality_severity;


CREATE TABLE IF NOT EXISTS core.credit_quality_repeated_shift_rules (
    metric_name TEXT NOT NULL,
    threshold NUMERIC NOT NULL,
    severity_points NUMERIC NOT NULL,
    updated_at TIMESTAMP DEFAULT now(),
    PRIMARY KEY (metric_name, threshold)
);


DELETE FROM core.credit_quality_repeated_shift_rules;

INSERT INTO core.credit_quality_repeated_shift_rules (
    metric_name,
    threshold,
    severity_points
)
VALUES
    ('max_invoice_term_shift_count', 2, 1),
    ('max_invoice_term_shift_count', 3, 2),
    ('repeated_shift_invoice_count', 2, 1),
    ('repeated_shift_invoice_count', 4, 2);


CREATE OR REPLACE VIEW core.v_client_credit_quality_severity AS
WITH repeated_shift AS (
    SELECT
        client_id,

        COUNT(*) FILTER (
            WHERE COALESCE(term_shift_count, 0) >= 2
        ) AS repeated_shift_invoice_count,

        COUNT(*) FILTER (
            WHERE COALESCE(term_shift_count, 0) >= 3
        ) AS heavy_repeated_shift_invoice_count

    FROM core.v_term_shift_invoice_summary
    GROUP BY client_id
),

scored AS (
    SELECT
        b.*,

        COALESCE(rs.repeated_shift_invoice_count, 0) AS repeated_shift_invoice_count,
        COALESCE(rs.heavy_repeated_shift_invoice_count, 0) AS heavy_repeated_shift_invoice_count,

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
              AND COALESCE(rs.repeated_shift_invoice_count, 0) >= r.threshold
        ), 0) AS repeated_shift_invoice_points

    FROM core.v_client_credit_quality_base b

    LEFT JOIN repeated_shift rs
        ON b.client_id = rs.client_id
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


CREATE OR REPLACE VIEW core.v_client_credit_quality_rating AS
SELECT
    client_id,
    client_name,
    client_group,
    parent_org_id,

    base_stars,
    base_rating_label,
    base_rating_display_label,
    confidence_level,

    total_debt,
    overdue_debt,
    overdue_share_pct,

    green_debt,
    green_90_plus_debt,
    green_120_plus_debt,
    green_90_plus_share_pct,
    green_120_plus_share_pct,

    weighted_avg_payment_term_days,
    max_payment_term_days,

    term_shift_count,
    max_invoice_term_shift_count,
    repeated_shift_invoice_count,
    heavy_repeated_shift_invoice_count,
    total_term_shift_delta_days,
    max_term_shift_delta_days,

    exposure_segment,
    exposure_multiplier,

    weighted_avg_payment_term_points,
    max_payment_term_points,
    green_90_plus_share_points,
    green_120_plus_debt_points,
    term_shift_count_points,
    max_invoice_term_shift_points,
    repeated_shift_invoice_points,

    raw_severity_points,
    weighted_severity_points,
    severity_level,
    severity_penalty,
    severity_reasons,

    GREATEST(
        (
            SELECT config_value::INT
            FROM core.credit_quality_final_rating_config
            WHERE config_key = 'min_stars'
        ),
        FLOOR(base_stars::numeric - severity_penalty)::INT
    ) AS credit_quality_stars,

    CASE
        WHEN GREATEST(
            (
                SELECT config_value::INT
                FROM core.credit_quality_final_rating_config
                WHERE config_key = 'min_stars'
            ),
            FLOOR(base_stars::numeric - severity_penalty)::INT
        ) = 5 THEN 'Отличное кредитное качество'
        WHEN GREATEST(
            (
                SELECT config_value::INT
                FROM core.credit_quality_final_rating_config
                WHERE config_key = 'min_stars'
            ),
            FLOOR(base_stars::numeric - severity_penalty)::INT
        ) = 4 THEN 'Хорошее кредитное качество'
        WHEN GREATEST(
            (
                SELECT config_value::INT
                FROM core.credit_quality_final_rating_config
                WHERE config_key = 'min_stars'
            ),
            FLOOR(base_stars::numeric - severity_penalty)::INT
        ) = 3 THEN 'Требует контроля'
        WHEN GREATEST(
            (
                SELECT config_value::INT
                FROM core.credit_quality_final_rating_config
                WHERE config_key = 'min_stars'
            ),
            FLOOR(base_stars::numeric - severity_penalty)::INT
        ) = 2 THEN 'Повышенный риск'
        ELSE 'Высокий риск'
    END AS credit_quality_label,

    CONCAT(
        GREATEST(
            (
                SELECT config_value::INT
                FROM core.credit_quality_final_rating_config
                WHERE config_key = 'min_stars'
            ),
            FLOOR(base_stars::numeric - severity_penalty)::INT
        ),
        '★ · ',
        CASE
            WHEN severity_level = 'NONE' THEN 'без дополнительных severity-сигналов'
            ELSE CONCAT('severity: ', severity_level)
        END
    ) AS credit_quality_display_label,

    CASE
        WHEN GREATEST(
            (
                SELECT config_value::INT
                FROM core.credit_quality_final_rating_config
                WHERE config_key = 'min_stars'
            ),
            FLOOR(base_stars::numeric - severity_penalty)::INT
        ) < base_stars
        THEN TRUE ELSE FALSE
    END AS rating_downgraded_by_severity

FROM core.v_client_credit_quality_severity
WHERE base_stars IS NOT NULL;