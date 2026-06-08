CREATE OR REPLACE VIEW core.v_term_shift_events AS

WITH invoice_history AS (

    SELECT
        report_generated_date,
        client_id,
        client_name,

        print_invoice_number,
        order_number,

        invoice_date,
        due_date,
        payment_term_days,
        invoice_amount,

        LAG(due_date) OVER (
            PARTITION BY client_id,
                         print_invoice_number
            ORDER BY report_generated_date
        ) AS previous_due_date,

        LAG(payment_term_days) OVER (
            PARTITION BY client_id,
                         print_invoice_number
            ORDER BY report_generated_date
        ) AS previous_payment_term_days

    FROM core.receivables_snapshot_fact
)

SELECT
    report_generated_date,

    client_id,
    client_name,

    print_invoice_number,
    order_number,

    invoice_date,

    previous_due_date,
    due_date,

    previous_payment_term_days,
    payment_term_days,

    (
        payment_term_days
        - previous_payment_term_days
    ) AS payment_term_delta_days,

    invoice_amount

FROM invoice_history

WHERE
    previous_payment_term_days IS NOT NULL
    AND payment_term_days > previous_payment_term_days;