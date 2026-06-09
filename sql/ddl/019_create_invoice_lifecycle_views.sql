DROP VIEW IF EXISTS core.v_recent_paid_invoices CASCADE;
DROP VIEW IF EXISTS core.v_invoice_snapshot_lifecycle CASCADE;


CREATE OR REPLACE VIEW core.v_invoice_snapshot_lifecycle AS

WITH snapshots AS (
    SELECT
        f.report_generated_date,
        f.client_id,
        f.client_name,
        f.client_group,
        f.parent_org_id,

        f.print_invoice_number,
        f.order_number,
        f.invoice_date,
        f.due_date,
        f.analytics_type,
        f.payment_term_days,
        f.invoice_amount,

        LAG(f.invoice_amount) OVER (
            PARTITION BY
                f.client_id,
                f.print_invoice_number,
                f.order_number,
                f.invoice_date
            ORDER BY f.report_generated_date
        ) AS previous_invoice_amount,

        LEAD(f.invoice_amount) OVER (
            PARTITION BY
                f.client_id,
                f.print_invoice_number,
                f.order_number,
                f.invoice_date
            ORDER BY f.report_generated_date
        ) AS next_invoice_amount,

        LEAD(f.report_generated_date) OVER (
            PARTITION BY
                f.client_id,
                f.print_invoice_number,
                f.order_number,
                f.invoice_date
            ORDER BY f.report_generated_date
        ) AS next_snapshot_date,

        MIN(f.report_generated_date) OVER (
            PARTITION BY
                f.client_id,
                f.print_invoice_number,
                f.order_number,
                f.invoice_date
        ) AS first_seen_snapshot,

        MAX(f.report_generated_date) OVER (
            PARTITION BY
                f.client_id,
                f.print_invoice_number,
                f.order_number,
                f.invoice_date
        ) AS last_seen_snapshot,

        MAX(f.report_generated_date) OVER () AS global_latest_snapshot_date,

        MAX(f.invoice_amount) OVER (
            PARTITION BY
                f.client_id,
                f.print_invoice_number,
                f.order_number,
                f.invoice_date
        ) AS max_observed_invoice_amount

    FROM core.receivables_snapshot_fact f

    WHERE
        f.invoice_amount > 0
        AND f.print_invoice_number IS NOT NULL
)

SELECT
    report_generated_date,
    client_id,
    client_name,
    client_group,
    parent_org_id,

    print_invoice_number,
    order_number,
    invoice_date,
    due_date,
    analytics_type,
    payment_term_days,

    invoice_amount,
    previous_invoice_amount,
    next_invoice_amount,
    max_observed_invoice_amount,

    first_seen_snapshot,
    last_seen_snapshot,
    next_snapshot_date,
    global_latest_snapshot_date,

    CASE
        WHEN previous_invoice_amount IS NOT NULL
         AND invoice_amount < previous_invoice_amount
        THEN previous_invoice_amount - invoice_amount
        ELSE 0
    END AS partial_payment_amount,

    CASE
        WHEN previous_invoice_amount IS NOT NULL
         AND invoice_amount < previous_invoice_amount
        THEN TRUE
        ELSE FALSE
    END AS is_partial_payment_event,

    CASE
        WHEN next_invoice_amount IS NULL
         AND report_generated_date < global_latest_snapshot_date
        THEN TRUE
        ELSE FALSE
    END AS is_closed_after_snapshot

FROM snapshots;


CREATE OR REPLACE VIEW core.v_recent_paid_invoices AS

WITH payment_events AS (

    -- Partial payments / partial closures
    SELECT
        client_id,
        client_name,
        client_group,
        parent_org_id,

        print_invoice_number,
        order_number,
        invoice_date,
        due_date,
        analytics_type,
        payment_term_days,

        max_observed_invoice_amount AS original_invoice_amount,
        previous_invoice_amount AS amount_before_payment,
        invoice_amount AS amount_after_payment,
        partial_payment_amount AS paid_amount_detected,

        report_generated_date AS last_seen_snapshot,
        report_generated_date AS estimated_payment_date,

        'PARTIAL' AS payment_event_type

    FROM core.v_invoice_snapshot_lifecycle

    WHERE is_partial_payment_event = TRUE

    UNION ALL

    -- Full closure: invoice disappears before the latest available snapshot
    SELECT
        client_id,
        client_name,
        client_group,
        parent_org_id,

        print_invoice_number,
        order_number,
        invoice_date,
        due_date,
        analytics_type,
        payment_term_days,

        max_observed_invoice_amount AS original_invoice_amount,
        invoice_amount AS amount_before_payment,
        0::numeric(14,2) AS amount_after_payment,
        invoice_amount AS paid_amount_detected,

        report_generated_date AS last_seen_snapshot,
        COALESCE(next_snapshot_date, report_generated_date) AS estimated_payment_date,

        'FULL' AS payment_event_type

    FROM core.v_invoice_snapshot_lifecycle

    WHERE is_closed_after_snapshot = TRUE
),

ranked_events AS (
    SELECT
        *,

        (
            estimated_payment_date::date
            - invoice_date::date
        ) AS actual_payment_term_days,

        (
            estimated_payment_date::date
            - due_date::date
        ) AS days_vs_due_date,

        ROW_NUMBER() OVER (
            PARTITION BY
                client_id,
                print_invoice_number,
                order_number,
                invoice_date,
                payment_event_type,
                estimated_payment_date
            ORDER BY paid_amount_detected DESC
        ) AS rn

    FROM payment_events

    WHERE paid_amount_detected > 0
)

SELECT
    client_id,
    client_name,
    client_group,
    parent_org_id,

    print_invoice_number,
    order_number,
    invoice_date,
    due_date,
    analytics_type,
    payment_term_days,

    original_invoice_amount,
    amount_before_payment,
    amount_after_payment,
    paid_amount_detected,

    last_seen_snapshot,
    estimated_payment_date,

    payment_event_type,

    actual_payment_term_days,
    days_vs_due_date,

    CASE
        WHEN days_vs_due_date <= 0 THEN 'ON_TIME'
        WHEN days_vs_due_date <= 3 THEN 'SMALL_DELAY'
        WHEN days_vs_due_date <= 14 THEN 'DELAY'
        ELSE 'LATE'
    END AS payment_behavior_bucket

FROM ranked_events

WHERE rn = 1

ORDER BY
    estimated_payment_date DESC,
    paid_amount_detected DESC;