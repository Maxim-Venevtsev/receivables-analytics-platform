CREATE OR REPLACE VIEW core.v_executive_green_debt_maturity_history AS
SELECT
    report_generated_date,

    CASE
        WHEN payment_term_days <= 30 THEN '0–30'
        WHEN payment_term_days <= 45 THEN '31–45'
        WHEN payment_term_days <= 60 THEN '46–60'
        WHEN payment_term_days <= 90 THEN '61–90'
        WHEN payment_term_days <= 120 THEN '91–120'
        ELSE '120+'
    END AS maturity_bucket,

    SUM(invoice_amount) AS green_debt_amount,
    COUNT(*) AS invoice_count,
    COUNT(DISTINCT client_id) AS client_count

FROM core.receivables_snapshot_fact
WHERE NOT is_overdue_real
  AND invoice_amount > 0
GROUP BY
    report_generated_date,
    maturity_bucket;


CREATE OR REPLACE VIEW core.v_executive_green_debt_maturity_current AS
SELECT *
FROM core.v_executive_green_debt_maturity_history
WHERE report_generated_date = (
    SELECT MAX(report_generated_date)
    FROM core.receivables_snapshot_fact
);


CREATE OR REPLACE VIEW core.v_executive_rating_exposure AS
SELECT
    r.stars,
    r.rating_label,

    COUNT(DISTINCT p.client_id) AS client_count,
    SUM(p.total_debt) AS total_debt,
    SUM(p.overdue_debt) AS overdue_debt,

    ROUND(
        SUM(p.overdue_debt) / NULLIF(SUM(p.total_debt), 0) * 100,
        2
    ) AS overdue_share_pct

FROM core.v_client_priority p
LEFT JOIN core.v_client_rating r
    ON p.client_id = r.client_id
GROUP BY
    r.stars,
    r.rating_label;


CREATE OR REPLACE VIEW core.v_executive_long_green_exposure AS
SELECT
    report_generated_date,

    SUM(
        CASE
            WHEN NOT is_overdue_real
             AND payment_term_days > 90
             AND invoice_amount > 0
            THEN invoice_amount
            ELSE 0
        END
    ) AS green_90_plus_debt,

    SUM(
        CASE
            WHEN NOT is_overdue_real
             AND payment_term_days > 120
             AND invoice_amount > 0
            THEN invoice_amount
            ELSE 0
        END
    ) AS green_120_plus_debt,

    SUM(
        CASE
            WHEN NOT is_overdue_real
             AND invoice_amount > 0
            THEN invoice_amount
            ELSE 0
        END
    ) AS total_green_debt,

    ROUND(
        SUM(
            CASE
                WHEN NOT is_overdue_real
                 AND payment_term_days > 90
                 AND invoice_amount > 0
                THEN invoice_amount
                ELSE 0
            END
        ) / NULLIF(SUM(invoice_amount), 0) * 100,
        2
    ) AS green_90_plus_share_of_portfolio_pct

FROM core.receivables_snapshot_fact
GROUP BY report_generated_date;


CREATE OR REPLACE VIEW core.v_executive_branch_health AS
SELECT
    b.client_group,

    b.total_debt,
    b.overdue_debt,
    b.overdue_share_pct,
    b.overdue_client_count,

    SUM(
        CASE
            WHEN NOT f.is_overdue_real
             AND f.payment_term_days > 90
             AND f.invoice_amount > 0
            THEN f.invoice_amount
            ELSE 0
        END
    ) AS green_90_plus_debt,

    ROUND(
        SUM(
            CASE
                WHEN NOT f.is_overdue_real
                 AND f.payment_term_days > 90
                 AND f.invoice_amount > 0
                THEN f.invoice_amount
                ELSE 0
            END
        ) / NULLIF(b.total_debt, 0) * 100,
        2
    ) AS green_90_plus_share_pct,

    rd.weighted_rating,
    rd.portfolio_change_label

FROM core.v_branch_summary b
LEFT JOIN core.receivables_snapshot_fact f
    ON b.client_group = f.client_group
   AND f.report_generated_date = (
        SELECT MAX(report_generated_date)
        FROM core.receivables_snapshot_fact
   )
LEFT JOIN core.v_branch_rating_dynamics rd
    ON b.client_group = rd.client_group
GROUP BY
    b.client_group,
    b.total_debt,
    b.overdue_debt,
    b.overdue_share_pct,
    b.overdue_client_count,
    rd.weighted_rating,
    rd.portfolio_change_label;


CREATE OR REPLACE VIEW core.v_executive_top_risk_clients AS
SELECT
    p.client_id,
    p.client_name,
    p.client_group,

    r.stars,
    r.rating_display_label,

    p.total_debt,
    p.overdue_debt,

    SUM(
        CASE
            WHEN NOT f.is_overdue_real
             AND f.payment_term_days > 90
             AND f.invoice_amount > 0
            THEN f.invoice_amount
            ELSE 0
        END
    ) AS green_90_plus_debt,

    p.risk_category,
    p.recommended_action

FROM core.v_client_priority p
LEFT JOIN core.v_client_rating r
    ON p.client_id = r.client_id
LEFT JOIN core.receivables_snapshot_fact f
    ON p.client_id = f.client_id
   AND f.report_generated_date = (
        SELECT MAX(report_generated_date)
        FROM core.receivables_snapshot_fact
   )
GROUP BY
    p.client_id,
    p.client_name,
    p.client_group,
    r.stars,
    r.rating_display_label,
    p.total_debt,
    p.overdue_debt,
    p.risk_category,
    p.recommended_action
ORDER BY
    green_90_plus_debt DESC,
    p.overdue_debt DESC,
    p.total_debt DESC;


CREATE OR REPLACE VIEW core.v_executive_overview_kpi AS
SELECT
    d.latest_snapshot_date,

    d.total_debt,
    d.overdue_debt,
    d.overdue_share_pct,
    d.due_today,
    d.due_in_3_days,
    d.high_risk_client_count,

    l.green_90_plus_debt,
    l.green_120_plus_debt,
    l.green_90_plus_share_of_portfolio_pct,

    ROUND(
        SUM(p.total_debt * r.stars) / NULLIF(SUM(p.total_debt), 0),
        2
    ) AS weighted_portfolio_rating

FROM core.v_dashboard_overview d
LEFT JOIN core.v_executive_long_green_exposure l
    ON d.latest_snapshot_date = l.report_generated_date
LEFT JOIN core.v_client_priority p
    ON TRUE
LEFT JOIN core.v_client_rating r
    ON p.client_id = r.client_id
GROUP BY
    d.latest_snapshot_date,
    d.total_debt,
    d.overdue_debt,
    d.overdue_share_pct,
    d.due_today,
    d.due_in_3_days,
    d.high_risk_client_count,
    l.green_90_plus_debt,
    l.green_120_plus_debt,
    l.green_90_plus_share_of_portfolio_pct;

    CREATE OR REPLACE VIEW core.v_executive_portfolio_daily_history AS
SELECT
    f.report_generated_date,

    SUM(f.invoice_amount) AS total_debt,

    SUM(
        CASE WHEN f.is_overdue_real
        THEN f.invoice_amount ELSE 0 END
    ) AS overdue_debt,

    SUM(
        CASE WHEN NOT f.is_overdue_real
        THEN f.invoice_amount ELSE 0 END
    ) AS normal_debt,

    SUM(
        CASE WHEN f.is_due_today
        THEN f.invoice_amount ELSE 0 END
    ) AS due_today,

    SUM(
        CASE
            WHEN f.is_due_in_3_days AND NOT f.is_due_today
            THEN f.invoice_amount
            ELSE 0
        END
    ) AS due_soon_only,

    SUM(
        CASE
            WHEN NOT f.is_overdue_real
             AND f.payment_term_days <= 45
             AND COALESCE(r.stars, 0) >= 4
             AND f.invoice_amount > 0
            THEN f.invoice_amount
            ELSE 0
        END
    ) AS reliable_debt,

    SUM(
        CASE
            WHEN NOT (
                NOT f.is_overdue_real
                AND f.payment_term_days <= 45
                AND COALESCE(r.stars, 0) >= 4
                AND f.invoice_amount > 0
            )
            THEN f.invoice_amount
            ELSE 0
        END
    ) AS control_required_debt,

    ROUND(
        SUM(CASE WHEN f.is_overdue_real THEN f.invoice_amount ELSE 0 END)
        / NULLIF(SUM(f.invoice_amount), 0) * 100,
        2
    ) AS overdue_share_pct

FROM core.receivables_snapshot_fact f
LEFT JOIN core.v_client_rating r
    ON f.client_id = r.client_id
GROUP BY f.report_generated_date;


CREATE OR REPLACE VIEW core.v_executive_payment_term_history AS
SELECT
    report_generated_date,

    ROUND(
        SUM(payment_term_days * invoice_amount)
        / NULLIF(SUM(invoice_amount), 0),
        1
    ) AS weighted_avg_payment_term_days,

    ROUND(
        SUM(
            CASE
                WHEN NOT is_overdue_real
                THEN payment_term_days * invoice_amount
                ELSE 0
            END
        )
        / NULLIF(
            SUM(
                CASE
                    WHEN NOT is_overdue_real
                    THEN invoice_amount
                    ELSE 0
                END
            ),
            0
        ),
        1
    ) AS weighted_avg_green_payment_term_days

FROM core.receivables_snapshot_fact
WHERE invoice_amount > 0
GROUP BY report_generated_date;


CREATE OR REPLACE VIEW core.v_executive_long_green_clients AS
SELECT
    f.client_id,
    f.client_name,
    f.client_group,

    r.stars,
    r.rating_display_label,

    SUM(f.invoice_amount) AS total_green_debt,

    SUM(
        CASE WHEN f.payment_term_days > 45
        THEN f.invoice_amount ELSE 0 END
    ) AS green_45_plus_debt,

    SUM(
        CASE WHEN f.payment_term_days > 60
        THEN f.invoice_amount ELSE 0 END
    ) AS green_60_plus_debt,

    SUM(
        CASE WHEN f.payment_term_days > 90
        THEN f.invoice_amount ELSE 0 END
    ) AS green_90_plus_debt,

    SUM(
        CASE WHEN f.payment_term_days > 120
        THEN f.invoice_amount ELSE 0 END
    ) AS green_120_plus_debt,

    MAX(f.payment_term_days) AS max_payment_term_days,

    COUNT(*) AS invoice_count

FROM core.receivables_snapshot_fact f
LEFT JOIN core.v_client_rating r
    ON f.client_id = r.client_id

WHERE f.report_generated_date = (
    SELECT MAX(report_generated_date)
    FROM core.receivables_snapshot_fact
)
  AND NOT f.is_overdue_real
  AND f.invoice_amount > 0

GROUP BY
    f.client_id,
    f.client_name,
    f.client_group,
    r.stars,
    r.rating_display_label

HAVING
    SUM(
        CASE WHEN f.payment_term_days > 45
        THEN f.invoice_amount ELSE 0 END
    ) > 0

ORDER BY
    green_120_plus_debt DESC,
    green_90_plus_debt DESC,
    green_60_plus_debt DESC,
    max_payment_term_days DESC;


CREATE OR REPLACE VIEW core.v_executive_overdue_clients AS
SELECT
    p.client_id,
    p.client_name,
    p.client_group,

    r.stars,
    r.rating_display_label,

    p.total_debt,
    p.overdue_debt,

    ROUND(
        p.overdue_debt / NULLIF(p.total_debt, 0) * 100,
        2
    ) AS overdue_share_pct,

    p.max_days_overdue,
    p.risk_category,
    p.recommended_action

FROM core.v_client_priority p
LEFT JOIN core.v_client_rating r
    ON p.client_id = r.client_id

WHERE p.overdue_debt > 0

ORDER BY
    p.overdue_debt DESC,
    p.max_days_overdue DESC;


CREATE OR REPLACE VIEW core.v_executive_hidden_risk_clients AS
SELECT
    l.*,

    ROUND(
        l.green_90_plus_debt / NULLIF(l.total_green_debt, 0) * 100,
        2
    ) AS green_90_plus_share_pct,

    ROUND(
        l.green_120_plus_debt / NULLIF(l.total_green_debt, 0) * 100,
        2
    ) AS green_120_plus_share_pct,

    CASE
        WHEN l.green_120_plus_debt > 0 THEN 'CRITICAL'
        WHEN l.green_90_plus_debt > 0 THEN 'HIGH'
        WHEN l.green_60_plus_debt > 0 THEN 'MEDIUM'
        ELSE 'WATCH'
    END AS hidden_risk_level

FROM core.v_executive_long_green_clients l

ORDER BY
    l.green_120_plus_debt DESC,
    l.green_90_plus_debt DESC,
    l.max_payment_term_days DESC;

CREATE OR REPLACE VIEW core.v_executive_long_green_invoices AS
SELECT
    f.client_id,
    f.client_name,
    f.client_group,

    r.stars,
    r.rating_display_label,

    f.invoice_date,
    f.due_date,
    f.payment_term_days,

    f.invoice_amount,

    f.order_number,
    f.print_invoice_number,
    f.system_invoice_number,

    f.days_until_due_real,
    f.is_due_today,
    f.is_due_in_3_days,
    f.is_due_in_7_days,

    CASE
        WHEN f.payment_term_days > 120 THEN '120+'
        WHEN f.payment_term_days > 90 THEN '91–120'
        WHEN f.payment_term_days > 60 THEN '61–90'
        WHEN f.payment_term_days > 45 THEN '46–60'
        ELSE '0–45'
    END AS payment_term_bucket

FROM core.receivables_snapshot_fact f
LEFT JOIN core.v_client_rating r
    ON f.client_id = r.client_id

WHERE f.report_generated_date = (
    SELECT MAX(report_generated_date)
    FROM core.receivables_snapshot_fact
)
  AND NOT f.is_overdue_real
  AND f.invoice_amount > 0
  AND f.payment_term_days > 45

ORDER BY
    f.payment_term_days DESC,
    f.invoice_amount DESC;