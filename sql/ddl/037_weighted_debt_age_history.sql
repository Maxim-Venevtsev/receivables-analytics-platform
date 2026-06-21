-- ============================================================
-- Executive weighted debt age history
-- ============================================================
-- Weighted debt age measures how old currently open invoice debt is
-- from invoice_date as of each historical report_generated_date.
-- This is not overdue days and not contractual payment term.
-- ============================================================

CREATE OR REPLACE VIEW core.v_executive_weighted_debt_age_history AS
SELECT
    report_generated_date,

    ROUND(
        SUM(
            invoice_amount
            * GREATEST(report_generated_date - invoice_date, 0)
        )
        / NULLIF(SUM(invoice_amount), 0),
        1
    ) AS weighted_avg_debt_age_days,

    SUM(invoice_amount) AS total_debt,

    COUNT(*) AS invoice_count

FROM core.receivables_snapshot_fact
WHERE invoice_amount > 0
  AND invoice_date IS NOT NULL
  AND report_generated_date IS NOT NULL
GROUP BY report_generated_date
ORDER BY report_generated_date;
