CREATE OR REPLACE VIEW core.v_term_shift_invoice_summary AS

WITH invoice_snapshots AS (
    SELECT
        client_id,
        client_name,
        client_group,

        print_invoice_number,
        order_number,
        invoice_date,
        invoice_amount,
        due_date,
        payment_term_days,
        report_generated_date,

        ROW_NUMBER() OVER (
            PARTITION BY
                client_id,
                print_invoice_number,
                order_number,
                invoice_date
            ORDER BY report_generated_date ASC
        ) AS rn_first,

        ROW_NUMBER() OVER (
            PARTITION BY
                client_id,
                print_invoice_number,
                order_number,
                invoice_date
            ORDER BY report_generated_date DESC
        ) AS rn_last

    FROM core.receivables_snapshot_fact

    WHERE
        invoice_amount > 0
        AND print_invoice_number IS NOT NULL
),

invoice_history AS (
    SELECT
        client_id,
        MAX(client_name) AS client_name,
        MAX(client_group) AS client_group,

        print_invoice_number,
        order_number,
        invoice_date,

        MIN(report_generated_date) AS first_seen_snapshot,
        MAX(report_generated_date) AS last_seen_snapshot,

        (MAX(invoice_amount) FILTER (WHERE rn_last = 1))::numeric(14,2) AS invoice_amount,

        MAX(due_date) FILTER (WHERE rn_first = 1) AS original_due_date,
        MAX(due_date) FILTER (WHERE rn_last = 1) AS current_due_date,

        MAX(payment_term_days) FILTER (WHERE rn_first = 1) AS original_payment_term_days,
        MAX(payment_term_days) FILTER (WHERE rn_last = 1) AS current_payment_term_days,

        COUNT(DISTINCT payment_term_days) AS distinct_payment_terms,
        COUNT(*) AS snapshot_count

    FROM invoice_snapshots

    GROUP BY
        client_id,
        print_invoice_number,
        order_number,
        invoice_date
),

shift_events AS (
    SELECT
        client_id,
        print_invoice_number,
        order_number,
        invoice_date,

        COUNT(*) AS term_shift_count,
        SUM(payment_term_delta_days) AS total_shift_days,
        MAX(payment_term_delta_days) AS max_single_shift_days,
        MAX(report_generated_date) AS last_shift_date

    FROM core.v_term_shift_events

    GROUP BY
        client_id,
        print_invoice_number,
        order_number,
        invoice_date
)

SELECT
    h.client_id,
    h.client_name,
    h.client_group,

    h.print_invoice_number,
    h.order_number,
    h.invoice_date,
    h.invoice_amount,

    h.first_seen_snapshot,
    h.last_seen_snapshot,

    h.original_due_date,
    h.current_due_date,

    h.original_payment_term_days,
    h.current_payment_term_days,

    (
        h.current_payment_term_days
        - h.original_payment_term_days
    ) AS current_term_delta_days,

    COALESCE(e.term_shift_count, 0) AS term_shift_count,
    COALESCE(e.total_shift_days, 0) AS total_shift_days,
    COALESCE(e.max_single_shift_days, 0) AS max_single_shift_days,
    e.last_shift_date,

    h.distinct_payment_terms,
    h.snapshot_count,

    CASE
        WHEN COALESCE(e.term_shift_count, 0) >= 4
          OR (h.current_payment_term_days - h.original_payment_term_days) >= 60
        THEN 'CRITICAL'

        WHEN COALESCE(e.term_shift_count, 0) >= 3
          OR (h.current_payment_term_days - h.original_payment_term_days) >= 30
        THEN 'HIGH'

        WHEN COALESCE(e.term_shift_count, 0) >= 2
          OR (h.current_payment_term_days - h.original_payment_term_days) >= 14
        THEN 'MEDIUM'

        WHEN COALESCE(e.term_shift_count, 0) >= 1
        THEN 'WATCH'

        ELSE 'NONE'
    END AS term_shift_risk_level,

    (
        COALESCE(e.term_shift_count, 0)
        * GREATEST(
            h.current_payment_term_days - h.original_payment_term_days,
            0
        )
    ) AS term_shift_pressure_index

FROM invoice_history h

LEFT JOIN shift_events e
    ON h.client_id = e.client_id
   AND h.print_invoice_number = e.print_invoice_number
   AND h.order_number = e.order_number
   AND h.invoice_date = e.invoice_date

WHERE
    COALESCE(e.term_shift_count, 0) > 0
    OR h.current_payment_term_days > h.original_payment_term_days;


CREATE OR REPLACE VIEW core.v_client_term_shift_summary AS

SELECT
    s.client_id,
    s.client_name,
    s.client_group,

    COUNT(*) AS shifted_invoice_count,

    SUM(s.term_shift_count) AS term_shift_count,

    SUM(s.invoice_amount) AS shifted_amount,

    SUM(
        CASE
            WHEN s.term_shift_count >= 3
            THEN s.invoice_amount
            ELSE 0
        END
    ) AS repeated_shift_amount,

    MAX(s.current_term_delta_days) AS max_current_term_delta_days,
    MAX(s.max_single_shift_days) AS max_single_shift_days,

    SUM(s.total_shift_days) AS total_shift_days,

    ROUND(
        AVG(NULLIF(s.current_term_delta_days, 0)),
        1
    ) AS avg_current_term_delta_days,

    MAX(s.current_payment_term_days) AS max_current_payment_term_days,

    MAX(s.last_shift_date) AS last_shift_date,

    MAX(s.term_shift_pressure_index) AS max_term_shift_pressure_index,
    SUM(s.term_shift_pressure_index) AS total_term_shift_pressure_index,

    CASE
        WHEN MAX(s.term_shift_risk_level) = 'CRITICAL'
          OR SUM(s.term_shift_count) >= 5
          OR MAX(s.current_term_delta_days) >= 60
        THEN 'CRITICAL'

        WHEN SUM(s.term_shift_count) >= 3
          OR MAX(s.current_term_delta_days) >= 30
        THEN 'HIGH'

        WHEN SUM(s.term_shift_count) >= 2
          OR MAX(s.current_term_delta_days) >= 14
        THEN 'MEDIUM'

        ELSE 'WATCH'
    END AS client_term_shift_risk_level

FROM core.v_term_shift_invoice_summary s

GROUP BY
    s.client_id,
    s.client_name,
    s.client_group

ORDER BY
    total_term_shift_pressure_index DESC,
    term_shift_count DESC,
    shifted_amount DESC;


CREATE OR REPLACE VIEW core.v_executive_term_shift_kpi AS

SELECT
    COUNT(DISTINCT client_id) AS clients_with_term_shifts,
    COUNT(*) AS shifted_invoice_count,
    SUM(term_shift_count) AS term_shift_events_count,
    SUM(invoice_amount) AS shifted_amount,
    MAX(current_term_delta_days) AS max_term_delta_days,
    COUNT(DISTINCT client_id) FILTER (
        WHERE term_shift_count >= 3
    ) AS clients_with_repeated_shifts,
    SUM(invoice_amount) FILTER (
        WHERE term_shift_count >= 3
    ) AS repeated_shift_amount
FROM core.v_term_shift_invoice_summary;