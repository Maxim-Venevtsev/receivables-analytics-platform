DROP VIEW IF EXISTS core.v_recent_paid_invoices_behavior CASCADE;

CREATE OR REPLACE VIEW core.v_recent_paid_invoices_behavior AS

SELECT
    *
FROM core.v_recent_paid_invoices
WHERE NOT (
    COALESCE(actual_payment_term_days, 0) = 0
    AND COALESCE(analytics_type, '') <> 'ARS_NEW'
);