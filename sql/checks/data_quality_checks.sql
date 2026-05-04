-- 1. Row count
SELECT
    COUNT(*) AS total_rows
FROM core.receivables_snapshot_fact;


-- 2. Проверка пустых ключевых полей
SELECT
    COUNT(*) AS rows_with_missing_keys
FROM core.receivables_snapshot_fact
WHERE client_id IS NULL
   OR client_name IS NULL
   OR invoice_date IS NULL
   OR due_date IS NULL
   OR invoice_amount IS NULL;


-- 3. Проверка валют
SELECT
    currency_code,
    COUNT(*) AS rows_count
FROM core.receivables_snapshot_fact
GROUP BY currency_code
ORDER BY rows_count DESC;


-- 4. Проверка филиалов
SELECT
    client_group,
    COUNT(*) AS rows_count,
    SUM(invoice_amount) AS total_debt
FROM core.receivables_snapshot_fact
GROUP BY client_group
ORDER BY total_debt DESC;


-- 5. Проверка аналитики
SELECT
    analytics_type,
    COUNT(*) AS rows_count,
    SUM(invoice_amount) AS total_debt
FROM core.receivables_snapshot_fact
GROUP BY analytics_type
ORDER BY total_debt DESC;


-- 6. Проверка отрицательных документов
SELECT
    client_id,
    client_name,
    client_group,
    invoice_date,
    due_date,
    analytics_type,
    invoice_amount,
    currency_code
FROM core.receivables_snapshot_fact
WHERE invoice_amount < 0
ORDER BY invoice_amount;


-- 7. Проверка странных отсрочек платежа
SELECT
    client_id,
    client_name,
    client_group,
    invoice_date,
    due_date,
    payment_term_days,
    invoice_amount
FROM core.receivables_snapshot_fact
WHERE payment_term_days < 0
   OR payment_term_days > 120
ORDER BY payment_term_days DESC;


-- 8. Проверка дублей накладных в рамках одной загрузки
SELECT
    load_id,
    system_invoice_number,
    COUNT(*) AS duplicate_count,
    SUM(invoice_amount) AS duplicate_amount
FROM core.receivables_snapshot_fact
WHERE system_invoice_number IS NOT NULL
GROUP BY load_id, system_invoice_number
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC;


-- 9. Сверка загрузок
SELECT
    load_id,
    source_file_name,
    report_generated_date,
    debt_asof_date_param,
    row_count_loaded,
    loaded_at,
    status
FROM raw.snapshot_loads
ORDER BY loaded_at DESC;


-- 10. Проверка KPI
SELECT *
FROM core.v_dashboard_kpi;


-- 11. Проверка филиальной сводки
SELECT *
FROM core.v_branch_summary
ORDER BY total_debt DESC;


-- 12. Проверка приоритетного списка
SELECT
    client_name,
    client_group,
    invoice_count,
    total_debt,
    overdue_debt,
    due_today,
    due_in_3_days,
    due_in_7_days,
    max_days_overdue,
    nearest_due_date,
    negative_amount,
    risk_category,
    recommended_action,
    risk_score
FROM core.v_client_priority
ORDER BY risk_score DESC
LIMIT 30;