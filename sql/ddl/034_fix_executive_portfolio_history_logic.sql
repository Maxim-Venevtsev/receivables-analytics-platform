-- ============================================================
-- 034_fix_executive_portfolio_history_logic.sql
-- Purpose:
--   1) Fix double counting in Executive debt structure chart:
--      normal_debt must exclude overdue, due today and due soon.
--   2) Refine reliable/control-required debt logic:
--      reliable debt = 4–5★ clients, invoice age < 45 days,
--      no repeated term shifts, and no overdue.
--   3) Keep green debt maturity chart unchanged.
-- ============================================================


CREATE OR REPLACE VIEW core.v_executive_portfolio_daily_history AS
WITH fact_enriched AS (
    SELECT
        f.report_generated_date,
        f.client_id,
        f.invoice_date,
        f.order_number,
        f.print_invoice_number,
        f.invoice_amount,
        f.payment_term_days,

        f.is_overdue_real,
        f.is_due_today,
        f.is_due_in_3_days,

        (f.report_generated_date::date - f.invoice_date::date) AS invoice_age_days,

        COALESCE(cq.credit_quality_stars, r.stars, 0) AS stars,
        COALESCE(ts.term_shift_count, 0) AS term_shift_count

    FROM core.receivables_snapshot_fact f

    LEFT JOIN core.v_client_rating r
        ON f.client_id = r.client_id

    LEFT JOIN core.v_client_credit_quality_rating cq
        ON f.client_id = cq.client_id

    LEFT JOIN core.v_term_shift_invoice_summary ts
        ON f.client_id = ts.client_id
       AND f.print_invoice_number = ts.print_invoice_number
       AND f.order_number = ts.order_number
       AND f.invoice_date = ts.invoice_date
)

SELECT
    report_generated_date,

    SUM(invoice_amount) AS total_debt,

    SUM(
        CASE
            WHEN is_overdue_real
            THEN invoice_amount
            ELSE 0::numeric
        END
    ) AS overdue_debt,

    -- В нормальном режиме:
    -- не просрочено, не к оплате сегодня, не к оплате в ближайшие дни.
    -- Это устраняет двойной учет в stacked structure chart.
    SUM(
        CASE
            WHEN NOT is_overdue_real
             AND NOT is_due_today
             AND NOT is_due_in_3_days
            THEN invoice_amount
            ELSE 0::numeric
        END
    ) AS normal_debt,

    SUM(
        CASE
            WHEN is_due_today
            THEN invoice_amount
            ELSE 0::numeric
        END
    ) AS due_today,

    SUM(
        CASE
            WHEN is_due_in_3_days
             AND NOT is_due_today
            THEN invoice_amount
            ELSE 0::numeric
        END
    ) AS due_soon_only,

    -- Надежная задолженность:
    -- 4–5★, не просрочено, возраст накладной < 45 дней,
    -- нет повторных переносов.
    SUM(
        CASE
            WHEN NOT is_overdue_real
             AND COALESCE(stars, 0) >= 4
             AND invoice_age_days < 45
             AND COALESCE(term_shift_count, 0) < 2
             AND invoice_amount > 0::numeric
            THEN invoice_amount
            ELSE 0::numeric
        END
    ) AS reliable_debt,

    SUM(
        CASE
            WHEN NOT (
                NOT is_overdue_real
                AND COALESCE(stars, 0) >= 4
                AND invoice_age_days < 45
                AND COALESCE(term_shift_count, 0) < 2
                AND invoice_amount > 0::numeric
            )
            THEN invoice_amount
            ELSE 0::numeric
        END
    ) AS control_required_debt,

    ROUND(
        SUM(
            CASE
                WHEN is_overdue_real
                THEN invoice_amount
                ELSE 0::numeric
            END
        )
        / NULLIF(SUM(invoice_amount), 0::numeric)
        * 100::numeric,
        2
    ) AS overdue_share_pct

FROM fact_enriched

GROUP BY report_generated_date;