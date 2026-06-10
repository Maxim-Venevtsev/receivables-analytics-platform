-- 023_credit_quality_rating_v2.sql
-- Rating V2 / Credit Quality Rating
-- Base rating + severity model

DROP VIEW IF EXISTS core.v_client_credit_quality_rating;
DROP VIEW IF EXISTS core.v_client_credit_quality_severity;
DROP VIEW IF EXISTS core.v_client_credit_quality_base;

CREATE TABLE IF NOT EXISTS core.credit_quality_exposure_segments (
    segment_name TEXT PRIMARY KEY,
    max_total_debt NUMERIC,
    max_weighted_payment_term_days NUMERIC,
    multiplier NUMERIC NOT NULL,
    updated_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS core.credit_quality_severity_rules (
    rule_group TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    threshold NUMERIC NOT NULL,
    severity_points NUMERIC NOT NULL,
    updated_at TIMESTAMP DEFAULT now(),
    PRIMARY KEY (rule_group, metric_name, threshold)
);

CREATE TABLE IF NOT EXISTS core.credit_quality_penalty_mapping (
    min_severity_points NUMERIC PRIMARY KEY,
    penalty NUMERIC NOT NULL,
    updated_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS core.credit_quality_final_rating_config (
    config_key TEXT PRIMARY KEY,
    config_value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT now()
);


-- Defaults aligned with configs/client_rating_rules.yaml.
-- Later we can extend src.ingestion.load_rating_rules to load these blocks from YAML too.

DELETE FROM core.credit_quality_exposure_segments;

INSERT INTO core.credit_quality_exposure_segments (
    segment_name,
    max_total_debt,
    max_weighted_payment_term_days,
    multiplier
)
VALUES
    ('small', 500000, 30, 0.5),
    ('medium', 2000000, 60, 1.0),
    ('large', NULL, NULL, 1.5);


DELETE FROM core.credit_quality_severity_rules;

INSERT INTO core.credit_quality_severity_rules (
    rule_group,
    metric_name,
    threshold,
    severity_points
)
VALUES
    ('payment_term_quality', 'weighted_avg_payment_term_days', 45, 1),
    ('payment_term_quality', 'weighted_avg_payment_term_days', 60, 2),
    ('payment_term_quality', 'weighted_avg_payment_term_days', 90, 3),

    ('payment_term_quality', 'max_payment_term_days', 90, 1),
    ('payment_term_quality', 'max_payment_term_days', 120, 2),

    ('payment_term_quality', 'green_90_plus_share_pct', 10, 1),
    ('payment_term_quality', 'green_90_plus_share_pct', 25, 2),
    ('payment_term_quality', 'green_90_plus_share_pct', 50, 3),

    ('payment_term_quality', 'green_120_plus_debt', 1, 2),

    ('term_shift_behavior', 'term_shift_count', 2, 1),
    ('term_shift_behavior', 'term_shift_count', 4, 2),
    ('term_shift_behavior', 'term_shift_count', 6, 3);


DELETE FROM core.credit_quality_penalty_mapping;

INSERT INTO core.credit_quality_penalty_mapping (
    min_severity_points,
    penalty
)
VALUES
    (0, 0),
    (2, 0.5),
    (4, 1),
    (6, 2);


DELETE FROM core.credit_quality_final_rating_config;

INSERT INTO core.credit_quality_final_rating_config (
    config_key,
    config_value
)
VALUES
    ('min_stars', '1'),
    ('max_stars', '5'),
    ('rounding', 'floor');


CREATE OR REPLACE VIEW core.v_client_credit_quality_base AS
WITH term_shift AS (
    SELECT
        client_id,
        SUM(COALESCE(term_shift_count, 0)) AS term_shift_count,
        MAX(COALESCE(term_shift_count, 0)) AS max_invoice_term_shift_count,
        SUM(COALESCE(current_term_delta_days, 0)) AS total_term_shift_delta_days,
        MAX(COALESCE(current_term_delta_days, 0)) AS max_term_shift_delta_days
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
    END AS exposure_multiplier

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
        ), 0) AS term_shift_count_points

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
        ) AS raw_severity_points,

        ROUND(
            (
                weighted_avg_payment_term_points
                + max_payment_term_points
                + green_90_plus_share_points
                + green_120_plus_debt_points
                + term_shift_count_points
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
            THEN 'повторные переносы сроков оплаты'
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
    total_term_shift_delta_days,
    max_term_shift_delta_days,

    exposure_segment,
    exposure_multiplier,

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