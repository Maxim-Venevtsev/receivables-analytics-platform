from __future__ import annotations

import os
from datetime import timedelta

import pytest
from sqlalchemy import create_engine, text

from src.ingestion import historical_backfill as backfill


TRACKED_TABLES = (
    "raw.snapshot_loads",
    "core.receivables_snapshot_fact",
    "core.client_rating_history",
    "core.client_credit_quality_history",
)


def _table_counts(connection):
    return {
        table: connection.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
        for table in TRACKED_TABLES
    }


def _persistent_backfill_object_count(connection):
    return connection.execute(
        text(
            """
            SELECT COUNT(*)
            FROM pg_class
            WHERE relname LIKE 'backfill_%'
              AND relpersistence <> 't'
            """
        )
    ).scalar_one()


@pytest.fixture
def disposable_connection():
    url = os.getenv("HISTORICAL_BACKFILL_TEST_DATABASE_URL")
    confirmed = os.getenv("HISTORICAL_BACKFILL_TEST_DB_DISPOSABLE")
    if not url or confirmed != "YES":
        pytest.skip(
            "Set HISTORICAL_BACKFILL_TEST_DATABASE_URL and "
            "HISTORICAL_BACKFILL_TEST_DB_DISPOSABLE=YES for a disposable "
            "PostgreSQL database containing the current project schema and fixtures."
        )

    engine = create_engine(url)
    connection = engine.connect()
    transaction = connection.begin()
    baseline_counts = _table_counts(connection)
    try:
        yield connection
    finally:
        transaction.rollback()
        connection.close()
        with engine.connect() as verification:
            assert _table_counts(verification) == baseline_counts
            assert _persistent_backfill_object_count(verification) == 0
            assert verification.execute(
                text(
                    "SELECT COUNT(*) FROM raw.snapshot_loads "
                    "WHERE source_file_name = '__backfill_future_test__.txt'"
                )
            ).scalar_one() == 0
        engine.dispose()


def _run_maintenance(connection, snapshot_date):
    backfill._create_stage_tables(connection)
    rating_sql = (
        backfill.MAINTENANCE_DIR / "rebuild_historical_rating.sql"
    ).read_text(encoding="utf-8")
    credit_sql = (
        backfill.MAINTENANCE_DIR / "rebuild_historical_credit_quality.sql"
    ).read_text(encoding="utf-8")
    connection.execute(text(rating_sql), {"snapshot_date": snapshot_date})
    connection.execute(text(credit_sql), {"snapshot_date": snapshot_date})


def _rating_difference_count(connection):
    return connection.execute(
        text(
            """
            SELECT COUNT(*) FROM (
                (
                    SELECT
                        client_id, client_name, parent_org_id, client_group,
                        stars, rating_label, rating_display_label,
                        confidence_level, snapshot_days, overdue_snapshot_days,
                        overdue_occurrence_ratio, avg_overdue_share_pct,
                        max_days_overdue
                    FROM backfill_rating_stage
                    EXCEPT
                    SELECT
                        client_id, client_name, parent_org_id, client_group,
                        stars, rating_label, rating_display_label,
                        confidence_level, snapshot_days, overdue_snapshot_days,
                        overdue_occurrence_ratio, avg_overdue_share_pct,
                        max_days_overdue
                    FROM core.v_client_rating
                )
                UNION ALL
                (
                    SELECT
                        client_id, client_name, parent_org_id, client_group,
                        stars, rating_label, rating_display_label,
                        confidence_level, snapshot_days, overdue_snapshot_days,
                        overdue_occurrence_ratio, avg_overdue_share_pct,
                        max_days_overdue
                    FROM core.v_client_rating
                    EXCEPT
                    SELECT
                        client_id, client_name, parent_org_id, client_group,
                        stars, rating_label, rating_display_label,
                        confidence_level, snapshot_days, overdue_snapshot_days,
                        overdue_occurrence_ratio, avg_overdue_share_pct,
                        max_days_overdue
                    FROM backfill_rating_stage
                )
            ) differences
            """
        )
    ).scalar_one()


def _credit_difference_count(connection):
    return connection.execute(
        text(
            """
            SELECT COUNT(*) FROM (
                (
                    SELECT
                        client_id, client_name, parent_org_id, client_group,
                        base_stars, credit_quality_stars,
                        credit_quality_display_label, confidence_level,
                        total_debt, overdue_debt, severity_level,
                        severity_penalty, severity_reasons
                    FROM backfill_credit_quality_stage
                    EXCEPT
                    SELECT
                        client_id, client_name, parent_org_id, client_group,
                        base_stars, credit_quality_stars,
                        credit_quality_display_label, confidence_level,
                        total_debt, overdue_debt, severity_level,
                        severity_penalty, severity_reasons
                    FROM core.v_client_credit_quality_rating
                )
                UNION ALL
                (
                    SELECT
                        client_id, client_name, parent_org_id, client_group,
                        base_stars, credit_quality_stars,
                        credit_quality_display_label, confidence_level,
                        total_debt, overdue_debt, severity_level,
                        severity_penalty, severity_reasons
                    FROM core.v_client_credit_quality_rating
                    EXCEPT
                    SELECT
                        client_id, client_name, parent_org_id, client_group,
                        base_stars, credit_quality_stars,
                        credit_quality_display_label, confidence_level,
                        total_debt, overdue_debt, severity_level,
                        severity_penalty, severity_reasons
                    FROM backfill_credit_quality_stage
                )
            ) differences
            """
        )
    ).scalar_one()


def _stage_fingerprint(connection):
    return connection.execute(
        text(
            """
            SELECT
                (
                    SELECT md5(string_agg(
                        concat_ws('|', snapshot_date, client_id, stars,
                            confidence_level, snapshot_days,
                            overdue_snapshot_days, overdue_occurrence_ratio,
                            avg_overdue_share_pct, max_days_overdue),
                        E'\n' ORDER BY snapshot_date, client_id
                    ))
                    FROM backfill_rating_stage
                ),
                (
                    SELECT md5(string_agg(
                        concat_ws('|', snapshot_date, client_id, base_stars,
                            credit_quality_stars, confidence_level, total_debt,
                            overdue_debt, severity_level, severity_penalty,
                            array_to_string(severity_reasons, ',')),
                        E'\n' ORDER BY snapshot_date, client_id
                    ))
                    FROM backfill_credit_quality_stage
                )
            """
        )
    ).one()


def test_maintenance_sql_parity_future_isolation_and_no_persistent_objects(
    disposable_connection,
):
    connection = disposable_connection
    latest = connection.execute(
        text("SELECT MAX(report_generated_date) FROM core.receivables_snapshot_fact")
    ).scalar_one()
    assert latest is not None

    _run_maintenance(connection, latest)
    assert _rating_difference_count(connection) == 0
    assert _credit_difference_count(connection) == 0
    before_future = _stage_fingerprint(connection)

    new_load_id = connection.execute(
        text(
            """
            INSERT INTO raw.snapshot_loads (
                source_file_name, source_file_path, report_generated_date,
                report_generated_time, debt_asof_date_param,
                client_group_filter, analytics_filter, row_count_loaded, status
            )
            SELECT
                '__backfill_future_test__.txt', '__transaction_rollback__',
                :latest + 1, MAX(report_generated_time),
                MAX(debt_asof_date_param) + 1, NULL, NULL, COUNT(*), 'loaded'
            FROM core.receivables_snapshot_fact
            WHERE report_generated_date = :latest
            RETURNING load_id
            """
        ),
        {"latest": latest},
    ).scalar_one()
    connection.execute(
        text(
            """
            INSERT INTO core.receivables_snapshot_fact (
                load_id, source_file_name, report_generated_date,
                report_generated_time, debt_asof_date_param, parent_org_id,
                client_id, client_name, invoice_date, order_number,
                print_invoice_number, system_invoice_number, analytics_type,
                invoice_amount, currency_code, due_date,
                days_overdue_report_param, overdue_amount_rub,
                overdue_amount_eur, client_group, payment_term_days,
                days_overdue_real, days_until_due_real, is_overdue_real,
                is_due_today, is_due_in_3_days, is_due_in_7_days,
                is_negative_document
            )
            SELECT
                :load_id, '__backfill_future_test__.txt', :latest + 1,
                report_generated_time, debt_asof_date_param + 1, parent_org_id,
                client_id, client_name, invoice_date, order_number,
                print_invoice_number, system_invoice_number, analytics_type,
                invoice_amount, currency_code, due_date + 30,
                days_overdue_report_param, overdue_amount_rub,
                overdue_amount_eur, client_group, payment_term_days + 30,
                GREATEST((:latest + 1) - (due_date + 30), 0),
                (due_date + 30) - (:latest + 1),
                ((:latest + 1) - (due_date + 30)) > 0,
                (due_date + 30) - (:latest + 1) = 0,
                (due_date + 30) - (:latest + 1) BETWEEN 0 AND 3,
                (due_date + 30) - (:latest + 1) BETWEEN 0 AND 7,
                is_negative_document
            FROM core.receivables_snapshot_fact
            WHERE report_generated_date = :latest
            """
        ),
        {"load_id": new_load_id, "latest": latest},
    )

    connection.execute(text("DROP TABLE backfill_credit_quality_stage"))
    connection.execute(text("DROP TABLE backfill_rating_stage"))
    _run_maintenance(connection, latest)

    assert _stage_fingerprint(connection) == before_future
    assert connection.execute(
        text(
            "SELECT MAX(report_generated_date) "
            "FROM core.v_receivables_current_snapshot"
        )
    ).scalar_one() == latest + timedelta(days=1)
    assert _persistent_backfill_object_count(connection) == 0
