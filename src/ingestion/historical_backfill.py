from __future__ import annotations

import argparse
import hashlib
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from sqlalchemy import text

from src.ingestion.load_to_postgres import (
    get_engine,
    load_receivables_snapshot_in_transaction,
)
from src.ingestion.parse_ascii import parse_receivables_txt
from src.quality.validations import validate_receivables_snapshot


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MAINTENANCE_DIR = PROJECT_ROOT / "sql" / "maintenance"
EARLIEST_AFFECTED_DATE = date(2026, 7, 13)
BACKFILL_LOCK_KEY = "debt_management_historical_backfill"
NEGATIVE_TERM_ERROR = "Found 1 rows where due_date is earlier than invoice_date."


@dataclass(frozen=True)
class ApprovedReport:
    filename: str
    report_date: date
    sha256: str
    row_count: int


APPROVED_REPORTS = (
    ApprovedReport(
        "АРС 13.07.2029.txt",
        date(2026, 7, 13),
        "e58b6f9a364271692ab4dc23cee301bdba73375fa14f28f768ac97a4be110a81",
        1166,
    ),
    ApprovedReport(
        "АРС 14.07.2029.txt",
        date(2026, 7, 14),
        "83d132aa9ac938615bb5f0456643c93a31aa8361ca518dcbde49efe8cf38440d",
        1115,
    ),
    ApprovedReport(
        "АРС 15.07.2029.txt",
        date(2026, 7, 15),
        "91786d686b9a3856a8eda7039d1b936d5e1d4c4b5757791bb80c26beb7f4471d",
        1121,
    ),
    ApprovedReport(
        "АРС 16.07.2029.txt",
        date(2026, 7, 16),
        "f66a92dc768a33246a6250b8edc27188408fc09380c483ca4098d797ecb1aea0",
        1103,
    ),
    ApprovedReport(
        "АРС 17.07.2029.txt",
        date(2026, 7, 17),
        "60097b774944178fa05fedf7b7d76cb9447e395b47e6614feb77db70f8169cdd",
        1107,
    ),
    ApprovedReport(
        "АРС 20.07.2029.txt",
        date(2026, 7, 20),
        "9130df74e26d53d25cbac69733cee0dd835b931de733ae28599b80d9ad29de81",
        1195,
    ),
    ApprovedReport(
        "АРС 21.07.2029.txt",
        date(2026, 7, 21),
        "f5fe2a9c003fc150a89a56d88f63defdf21a3ed3fa40b878314224eb9ddada9d",
        1163,
    ),
    ApprovedReport(
        "АРС 22.07.2029.txt",
        date(2026, 7, 22),
        "3de7a8e11f893c917137b1568798e9c9bda03af37830badaf490deab3048d2d3",
        1262,
    ),
)
APPROVED_BY_DATE = {item.report_date: item for item in APPROVED_REPORTS}
APPROVED_ANOMALY_DATES = {
    date(2026, 7, 13),
    date(2026, 7, 14),
    date(2026, 7, 15),
    date(2026, 7, 16),
    date(2026, 7, 17),
    date(2026, 7, 20),
}
EXCLUDED_REPORT_FILENAME = "АРС 10.07.2029.txt"


class HistoricalBackfillError(RuntimeError):
    pass


@dataclass
class PreparedReport:
    approved: ApprovedReport
    source_path: Path
    dataframe: object
    metadata: dict
    warnings: list[str] = field(default_factory=list)
    approved_exception_used: bool = False


@dataclass
class BatchPlan:
    source_dir: Path
    reports: list[PreparedReport]


@dataclass
class DatabaseState:
    kind: str
    history_dates: list[date]
    facts_to_load: list[date] = field(default_factory=list)
    history_complete: bool = False
    limitation: str = (
        "raw.snapshot_loads does not store SHA256; existing facts are matched only "
        "by report date, source filename, loaded status, metadata row count, and "
        "fact row count. Cryptographic identity of already-loaded database rows "
        "cannot be proven."
    )


@dataclass
class BatchResult:
    plan: BatchPlan
    dry_run: bool
    database_state: DatabaseState
    loaded_dates: list[date] = field(default_factory=list)
    rebuilt_dates: list[date] = field(default_factory=list)
    rating_rows: int = 0
    credit_quality_rows: int = 0
    no_op: bool = False


def compute_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def prepare_batch(source_dir: Path) -> BatchPlan:
    source_dir = source_dir.resolve()
    if not source_dir.is_dir():
        raise HistoricalBackfillError(f"Backfill source directory not found: {source_dir}")

    expected_names = {item.filename for item in APPROVED_REPORTS}
    actual_txt = [path for path in source_dir.iterdir() if path.is_file() and path.suffix.lower() == ".txt"]
    actual_names = {path.name for path in actual_txt}

    missing = sorted(expected_names - actual_names)
    if missing:
        raise HistoricalBackfillError(
            "Approved batch is incomplete; missing: " + ", ".join(missing)
        )

    extras = sorted(
        name
        for name in actual_names - expected_names
        if name != EXCLUDED_REPORT_FILENAME
    )
    if extras:
        raise HistoricalBackfillError(
            "Unapproved TXT files are present: " + ", ".join(extras)
        )

    reports = [_prepare_report(source_dir / approved.filename, approved) for approved in APPROVED_REPORTS]
    dates = [report.metadata["report_generated_date"] for report in reports]
    if len(dates) != len(set(dates)):
        raise HistoricalBackfillError("Duplicate parser-derived report date in approved batch")
    if set(dates) != set(APPROVED_BY_DATE):
        raise HistoricalBackfillError("Approved report-date set is incomplete or unexpected")

    reports.sort(key=lambda item: item.approved.report_date)
    return BatchPlan(source_dir=source_dir, reports=reports)


def _prepare_report(path: Path, approved: ApprovedReport) -> PreparedReport:
    if path.name == EXCLUDED_REPORT_FILENAME:
        raise HistoricalBackfillError("The unusable 2026-07-10 report is excluded")
    if compute_sha256(path) != approved.sha256:
        raise HistoricalBackfillError(f"SHA256 mismatch: {path.name}")

    dataframe, metadata = parse_receivables_txt(path)
    report_date = metadata["report_generated_date"]
    if report_date != approved.report_date:
        raise HistoricalBackfillError(
            f"Parser-derived date mismatch for {path.name}: {report_date}"
        )
    if len(dataframe) != approved.row_count:
        raise HistoricalBackfillError(
            f"Parsed row-count mismatch for {path.name}: "
            f"expected {approved.row_count}, got {len(dataframe)}"
        )

    errors, warnings = validate_receivables_snapshot(dataframe)
    exception_used = False
    if errors:
        if (
            errors == [NEGATIVE_TERM_ERROR]
            and report_date in APPROVED_ANOMALY_DATES
            and _matches_approved_anomaly(dataframe)
        ):
            exception_used = True
        else:
            raise HistoricalBackfillError(
                f"Validation failed for {path.name}: " + "; ".join(errors)
            )

    return PreparedReport(
        approved=approved,
        source_path=path,
        dataframe=dataframe,
        metadata=metadata,
        warnings=warnings,
        approved_exception_used=exception_used,
    )


def _matches_approved_anomaly(dataframe) -> bool:
    invalid = dataframe[dataframe["payment_term_days"] < 0]
    if len(invalid) != 1:
        return False
    row = invalid.iloc[0]
    return (
        str(row["client_id"]) == "27444"
        and str(row["client_name"]) == "ИП Богачкин А. В."
        and str(row["client_group"]) == "КГ_Красн"
        and str(row["order_number"]) == "26063885"
        and str(row["print_invoice_number"]) == "26017382"
        and str(row["system_invoice_number"]) == "IS2116419"
        and row["invoice_date"] == date(2026, 7, 2)
        and row["due_date"] == date(2026, 6, 29)
        and int(row["payment_term_days"]) == -3
        and abs(float(row["invoice_amount"]) - 3020.76) < 0.005
        and str(row["currency_code"]) == "RUR"
        and str(row["analytics_type"]) == "ARS_NEW"
    )


def run_batch(
    source_dir: Path,
    *,
    dry_run: bool = False,
    rebuild_history: bool = False,
    engine=None,
) -> BatchResult:
    plan = prepare_batch(source_dir)
    engine = engine or get_engine()

    if dry_run:
        with engine.connect() as conn:
            _verify_production_invariants(conn)
            state = inspect_database_state(conn, plan)
        _validate_requested_action(state, rebuild_history)
        return BatchResult(
            plan=plan,
            dry_run=True,
            database_state=state,
            rebuilt_dates=state.history_dates if state.kind == "all_missing" or rebuild_history else [],
            no_op=state.kind == "all_exact" and state.history_complete and not rebuild_history,
        )

    with engine.begin() as conn:
        _acquire_locks(conn)
        _verify_production_invariants(conn)
        state = inspect_database_state(conn, plan, lock=True)
        _validate_requested_action(state, rebuild_history)

        if state.kind == "all_exact" and state.history_complete and not rebuild_history:
            return BatchResult(plan, False, state, no_op=True)

        loaded_dates: list[date] = []
        if state.kind == "all_missing":
            for report in plan.reports:
                load_receivables_snapshot_in_transaction(
                    conn,
                    report.dataframe,
                    report.metadata,
                    report.source_path,
                )
                loaded_dates.append(report.approved.report_date)

        history_dates = _affected_fact_dates(conn)
        _create_stage_tables(conn)
        rating_sql = _read_maintenance_sql("rebuild_historical_rating.sql")
        credit_sql = _read_maintenance_sql("rebuild_historical_credit_quality.sql")
        for snapshot_date in history_dates:
            conn.execute(text(rating_sql), {"snapshot_date": snapshot_date})
            conn.execute(text(credit_sql), {"snapshot_date": snapshot_date})

        stage_counts = _verify_stage(conn, history_dates)
        _replace_history_suffix(conn)
        final_counts = _verify_final_state(conn, plan, history_dates)
        if stage_counts != final_counts:
            raise HistoricalBackfillError(
                "Final history counts differ from verified staging counts"
            )

        return BatchResult(
            plan=plan,
            dry_run=False,
            database_state=state,
            loaded_dates=loaded_dates,
            rebuilt_dates=history_dates,
            rating_rows=stage_counts[0],
            credit_quality_rows=stage_counts[1],
        )


def _acquire_locks(conn) -> None:
    conn.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
        {"lock_key": BACKFILL_LOCK_KEY},
    )
    conn.execute(
        text(
            """
            LOCK TABLE
                raw.snapshot_loads,
                core.receivables_snapshot_fact,
                core.client_rating_history,
                core.client_credit_quality_history
            IN SHARE ROW EXCLUSIVE MODE
            """
        )
    )


def _verify_production_invariants(conn) -> None:
    persistent_context = conn.execute(
        text(
            "SELECT to_regprocedure('core.effective_snapshot_date()') IS NOT NULL"
        )
    ).scalar_one()
    if persistent_context:
        raise HistoricalBackfillError(
            "Persistent historical snapshot context is installed; restore normal "
            "production views before using the isolated backfill"
        )

    persistent_stage = conn.execute(
        text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM pg_class
                WHERE relname IN (
                    'backfill_rating_stage',
                    'backfill_credit_quality_stage'
                )
                  AND relpersistence <> 't'
            )
            """
        )
    ).scalar_one()
    if persistent_stage:
        raise HistoricalBackfillError(
            "A persistent backfill staging object exists unexpectedly"
        )

    latest = conn.execute(
        text("SELECT MAX(report_generated_date) FROM core.receivables_snapshot_fact")
    ).scalar_one()
    current = conn.execute(
        text(
            "SELECT MAX(report_generated_date) "
            "FROM core.v_receivables_current_snapshot"
        )
    ).scalar_one()
    if latest != current:
        raise HistoricalBackfillError(
            "Normal current-snapshot view does not resolve to latest fact date"
        )
    _verify_no_future_history(conn, latest)


def _verify_no_future_history(conn, latest_fact_date: date | None) -> None:
    violations = conn.execute(
        text(
            """
            SELECT
                'core.client_rating_history' AS history_table,
                COUNT(*) AS future_rows,
                MIN(snapshot_date) AS earliest_date,
                MAX(snapshot_date) AS latest_date
            FROM core.client_rating_history
            WHERE CAST(:latest_fact_date AS date) IS NULL
               OR snapshot_date > CAST(:latest_fact_date AS date)
            HAVING COUNT(*) > 0

            UNION ALL

            SELECT
                'core.client_credit_quality_history' AS history_table,
                COUNT(*) AS future_rows,
                MIN(snapshot_date) AS earliest_date,
                MAX(snapshot_date) AS latest_date
            FROM core.client_credit_quality_history
            WHERE CAST(:latest_fact_date AS date) IS NULL
               OR snapshot_date > CAST(:latest_fact_date AS date)
            HAVING COUNT(*) > 0

            ORDER BY history_table
            """
        ),
        {"latest_fact_date": latest_fact_date},
    ).mappings().all()
    if not violations:
        return

    latest_label = str(latest_fact_date) if latest_fact_date else "none"
    details = "; ".join(
        f"table={row['history_table']}, future_rows={row['future_rows']}, "
        f"earliest={row['earliest_date']}, latest={row['latest_date']}"
        for row in violations
    )
    raise HistoricalBackfillError(
        f"History exists later than latest fact date {latest_label}: {details}"
    )


def inspect_database_state(conn, plan: BatchPlan, *, lock: bool = False) -> DatabaseState:
    suffix = " FOR UPDATE OF l" if lock else ""
    rows = conn.execute(
        text(
            """
            SELECT
                l.load_id,
                l.source_file_name,
                l.report_generated_date,
                l.row_count_loaded,
                l.status,
                (
                    SELECT COUNT(*)
                    FROM core.receivables_snapshot_fact f
                    WHERE f.load_id = l.load_id
                ) AS fact_rows
            FROM raw.snapshot_loads l
            WHERE l.report_generated_date = ANY(:dates)
               OR l.source_file_name = ANY(:filenames)
            """
            + suffix
        ),
        {
            "dates": [item.approved.report_date for item in plan.reports],
            "filenames": [item.approved.filename for item in plan.reports],
        },
    ).mappings().all()

    by_date: dict[date, list] = {}
    for row in rows:
        by_date.setdefault(row["report_generated_date"], []).append(row)

    exact_dates: list[date] = []
    missing_dates: list[date] = []
    conflicts: list[str] = []
    for report in plan.reports:
        matches = by_date.get(report.approved.report_date, [])
        filename_matches = [
            row for row in rows if row["source_file_name"] == report.approved.filename
        ]
        candidates = {row["load_id"]: row for row in matches + filename_matches}
        if not candidates:
            missing_dates.append(report.approved.report_date)
            continue
        if len(candidates) != 1:
            conflicts.append(f"{report.approved.report_date}: multiple loads")
            continue
        row = next(iter(candidates.values()))
        if (
            row["source_file_name"] == report.approved.filename
            and row["report_generated_date"] == report.approved.report_date
            and row["status"] == "loaded"
            and row["row_count_loaded"] == report.approved.row_count
            and row["fact_rows"] == report.approved.row_count
        ):
            exact_dates.append(report.approved.report_date)
        else:
            conflicts.append(
                f"{report.approved.report_date}: conflicting metadata/fact count"
            )

    if conflicts:
        raise HistoricalBackfillError("; ".join(conflicts))
    if exact_dates and missing_dates:
        kind = "mixed"
    elif exact_dates:
        kind = "all_exact"
    else:
        kind = "all_missing"

    history_dates = _affected_fact_dates(conn, include_planned=kind == "all_missing")
    complete = _history_is_complete(conn, history_dates) if kind == "all_exact" else False
    return DatabaseState(
        kind=kind,
        history_dates=history_dates,
        facts_to_load=missing_dates,
        history_complete=complete,
    )


def _validate_requested_action(state: DatabaseState, rebuild_history: bool) -> None:
    if state.kind == "mixed":
        raise HistoricalBackfillError(
            "Mixed database state: some approved facts exist and some are missing"
        )
    if state.kind == "all_exact" and not state.history_complete and not rebuild_history:
        raise HistoricalBackfillError(
            "Approved facts are exact by available metadata, but history is incomplete; "
            "rerun deliberately with --rebuild-history"
        )


def _affected_fact_dates(conn, *, include_planned: bool = False) -> list[date]:
    dates = list(
        conn.execute(
            text(
                """
                SELECT DISTINCT report_generated_date
                FROM core.receivables_snapshot_fact
                WHERE report_generated_date >= :start_date
                ORDER BY report_generated_date
                """
            ),
            {"start_date": EARLIEST_AFFECTED_DATE},
        ).scalars()
    )
    if include_planned:
        dates = sorted(set(dates) | set(APPROVED_BY_DATE))
    return dates


def _history_is_complete(conn, dates: list[date]) -> bool:
    if not dates:
        return False
    rows = conn.execute(
        text(
            """
            SELECT
                d.snapshot_date,
                COALESCE(r.row_count, 0) AS rating_rows,
                COALESCE(r.client_count, 0) AS rating_clients,
                COALESCE(c.row_count, 0) AS credit_rows,
                COALESCE(c.client_count, 0) AS credit_clients
            FROM unnest(:dates) AS d(snapshot_date)
            LEFT JOIN (
                SELECT
                    snapshot_date,
                    COUNT(*) AS row_count,
                    COUNT(DISTINCT client_id) AS client_count
                FROM core.client_rating_history
                WHERE snapshot_date = ANY(:dates)
                GROUP BY snapshot_date
            ) r USING (snapshot_date)
            LEFT JOIN (
                SELECT
                    snapshot_date,
                    COUNT(*) AS row_count,
                    COUNT(DISTINCT client_id) AS client_count
                FROM core.client_credit_quality_history
                WHERE snapshot_date = ANY(:dates)
                GROUP BY snapshot_date
            ) c USING (snapshot_date)
            ORDER BY d.snapshot_date
            """
        ),
        {"dates": dates},
    ).mappings().all()
    return (
        len(rows) == len(dates)
        and all(
            row["rating_rows"] > 0
            and row["credit_rows"] > 0
            and row["rating_rows"] == row["rating_clients"]
            and row["credit_rows"] == row["credit_clients"]
            and row["credit_rows"] <= row["rating_rows"]
            for row in rows
        )
        and _history_coverage_matches(conn, dates)
    )


def _history_coverage_matches(conn, dates: list[date]) -> bool:
    differences = conn.execute(
        text(
            """
            SELECT EXISTS (
                (
                    SELECT h.snapshot_date, h.client_id
                    FROM core.client_credit_quality_history h
                    WHERE snapshot_date = ANY(:dates)
                    EXCEPT
                    SELECT h.snapshot_date, h.client_id
                    FROM core.client_rating_history h
                    WHERE snapshot_date = ANY(:dates)
                )
                UNION ALL
                (
                    SELECT f.report_generated_date, f.client_id
                    FROM core.receivables_snapshot_fact f
                    JOIN core.client_rating_history r
                      ON r.snapshot_date = f.report_generated_date
                     AND r.client_id = f.client_id
                    WHERE f.report_generated_date = ANY(:dates)
                    EXCEPT
                    SELECT h.snapshot_date, h.client_id
                    FROM core.client_credit_quality_history h
                    WHERE h.snapshot_date = ANY(:dates)
                )
                UNION ALL
                (
                    SELECT h.snapshot_date, h.client_id
                    FROM core.client_credit_quality_history h
                    WHERE h.snapshot_date = ANY(:dates)
                    EXCEPT
                    SELECT f.report_generated_date, f.client_id
                    FROM core.receivables_snapshot_fact f
                    JOIN core.client_rating_history r
                      ON r.snapshot_date = f.report_generated_date
                     AND r.client_id = f.client_id
                    WHERE f.report_generated_date = ANY(:dates)
                )
            )
            """
        ),
        {"dates": dates},
    ).scalar_one()
    return not differences


def _create_stage_tables(conn) -> None:
    conn.execute(
        text(
            """
            CREATE TEMP TABLE backfill_rating_stage
                (LIKE core.client_rating_history INCLUDING DEFAULTS)
                ON COMMIT DROP
            """
        )
    )
    conn.execute(
        text(
            """
            CREATE TEMP TABLE backfill_credit_quality_stage
                (LIKE core.client_credit_quality_history INCLUDING DEFAULTS)
                ON COMMIT DROP
            """
        )
    )


def _read_maintenance_sql(filename: str) -> str:
    path = MAINTENANCE_DIR / filename
    if not path.is_file():
        raise HistoricalBackfillError(f"Maintenance SQL not found: {path}")
    return path.read_text(encoding="utf-8")


def _verify_stage(conn, dates: list[date]) -> tuple[int, int]:
    rows = conn.execute(
        text(
            """
            SELECT
                d.snapshot_date,
                COALESCE(r.row_count, 0) AS rating_rows,
                COALESCE(r.client_count, 0) AS rating_clients,
                COALESCE(c.row_count, 0) AS credit_rows,
                COALESCE(c.client_count, 0) AS credit_clients
            FROM unnest(:dates) AS d(snapshot_date)
            LEFT JOIN (
                SELECT
                    snapshot_date,
                    COUNT(*) AS row_count,
                    COUNT(DISTINCT client_id) AS client_count
                FROM backfill_rating_stage
                GROUP BY snapshot_date
            ) r USING (snapshot_date)
            LEFT JOIN (
                SELECT
                    snapshot_date,
                    COUNT(*) AS row_count,
                    COUNT(DISTINCT client_id) AS client_count
                FROM backfill_credit_quality_stage
                GROUP BY snapshot_date
            ) c USING (snapshot_date)
            ORDER BY d.snapshot_date
            """
        ),
        {"dates": dates},
    ).mappings().all()
    if (
        len(rows) != len(dates)
        or any(
            row["rating_rows"] <= 0
            or row["credit_rows"] <= 0
            or row["rating_rows"] != row["rating_clients"]
            or row["credit_rows"] != row["credit_clients"]
            or row["credit_rows"] > row["rating_rows"]
            for row in rows
        )
        or not _stage_coverage_matches(conn)
    ):
        raise HistoricalBackfillError(
            "Staged rating/Credit Quality coverage is incomplete or inconsistent"
        )
    return (
        sum(row["rating_rows"] for row in rows),
        sum(row["credit_rows"] for row in rows),
    )


def _stage_coverage_matches(conn) -> bool:
    differences = conn.execute(
        text(
            """
            SELECT EXISTS (
                (
                    SELECT snapshot_date, client_id
                    FROM backfill_credit_quality_stage
                    EXCEPT
                    SELECT snapshot_date, client_id
                    FROM backfill_rating_stage
                )
                UNION ALL
                (
                    SELECT f.report_generated_date, f.client_id
                    FROM core.receivables_snapshot_fact f
                    JOIN backfill_rating_stage r
                      ON r.snapshot_date = f.report_generated_date
                     AND r.client_id = f.client_id
                    EXCEPT
                    SELECT snapshot_date, client_id
                    FROM backfill_credit_quality_stage
                )
                UNION ALL
                (
                    SELECT snapshot_date, client_id
                    FROM backfill_credit_quality_stage
                    EXCEPT
                    SELECT f.report_generated_date, f.client_id
                    FROM core.receivables_snapshot_fact f
                    JOIN backfill_rating_stage r
                      ON r.snapshot_date = f.report_generated_date
                     AND r.client_id = f.client_id
                )
            )
            """
        )
    ).scalar_one()
    return not differences


def _replace_history_suffix(conn) -> None:
    conn.execute(
        text(
            "DELETE FROM core.client_credit_quality_history "
            "WHERE snapshot_date >= :start_date"
        ),
        {"start_date": EARLIEST_AFFECTED_DATE},
    )
    conn.execute(
        text(
            "DELETE FROM core.client_rating_history "
            "WHERE snapshot_date >= :start_date"
        ),
        {"start_date": EARLIEST_AFFECTED_DATE},
    )
    conn.execute(
        text(
            """
            INSERT INTO core.client_rating_history
            SELECT * FROM backfill_rating_stage
            ORDER BY snapshot_date, client_id
            """
        )
    )
    conn.execute(
        text(
            """
            INSERT INTO core.client_credit_quality_history
            SELECT * FROM backfill_credit_quality_stage
            ORDER BY snapshot_date, client_id
            """
        )
    )


def _verify_final_state(
    conn, plan: BatchPlan, dates: list[date]
) -> tuple[int, int]:
    approved = conn.execute(
        text(
            """
            SELECT
                report_generated_date,
                COUNT(DISTINCT load_id) AS loads,
                COUNT(DISTINCT source_file_name) AS filenames,
                COUNT(*) AS fact_rows
            FROM core.receivables_snapshot_fact
            WHERE report_generated_date = ANY(:dates)
            GROUP BY report_generated_date
            ORDER BY report_generated_date
            """
        ),
        {"dates": [item.approved.report_date for item in plan.reports]},
    ).mappings().all()
    expected_rows = {
        item.approved.report_date: item.approved.row_count for item in plan.reports
    }
    if len(approved) != len(plan.reports) or any(
        row["loads"] != 1
        or row["filenames"] != 1
        or row["fact_rows"] != expected_rows[row["report_generated_date"]]
        for row in approved
    ):
        raise HistoricalBackfillError("Final approved fact verification failed")

    counts = _verify_history_tables(conn, dates)
    latest = conn.execute(
        text("SELECT MAX(report_generated_date) FROM core.receivables_snapshot_fact")
    ).scalar_one()
    current_view = conn.execute(
        text("SELECT MAX(report_generated_date) FROM core.v_receivables_current_snapshot")
    ).scalar_one()
    if current_view != latest:
        raise HistoricalBackfillError(
            "Normal current-snapshot view does not resolve to latest fact date"
        )
    _verify_no_future_history(conn, latest)
    return counts


def _verify_history_tables(conn, dates: list[date]) -> tuple[int, int]:
    if not _history_is_complete(conn, dates):
        raise HistoricalBackfillError("Final history coverage verification failed")
    rating = conn.execute(
        text(
            "SELECT COUNT(*) FROM core.client_rating_history "
            "WHERE snapshot_date = ANY(:dates)"
        ),
        {"dates": dates},
    ).scalar_one()
    credit = conn.execute(
        text(
            "SELECT COUNT(*) FROM core.client_credit_quality_history "
            "WHERE snapshot_date = ANY(:dates)"
        ),
        {"dates": dates},
    ).scalar_one()
    return rating, credit


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Atomically load the complete approved July historical batch."
    )
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--rebuild-history",
        action="store_true",
        help="Rebuild history only when all eight facts already match available metadata.",
    )
    return parser


def format_result(result: BatchResult) -> str:
    database_state = (
        "facts_match_available_database_metadata"
        if result.database_state.kind == "all_exact"
        else result.database_state.kind
    )
    lines = [
        "Historical snapshot atomic batch",
        f"Dry run: {'yes' if result.dry_run else 'no'}",
        f"Source directory: {result.plan.source_dir}",
        f"Validated files: {len(result.plan.reports)}",
        f"Database state: {database_state}",
        "Source file identity: audited SHA256 validation passed",
        "Existing database fact match evidence: report date, source filename, "
        "loaded status, metadata row count, fact row count",
        f"History complete before run: "
        f"{'yes' if result.database_state.history_complete else 'no'}",
        f"Facts to load: "
        f"{', '.join(map(str, result.database_state.facts_to_load)) or '-'}",
        f"History dates: "
        f"{', '.join(map(str, result.rebuilt_dates or result.database_state.history_dates)) or '-'}",
        f"Loaded dates: {', '.join(map(str, result.loaded_dates)) or '-'}",
        f"Rating rows: {result.rating_rows}",
        f"Credit Quality rows: {result.credit_quality_rows}",
        f"No-op: {'yes' if result.no_op else 'no'}",
        f"Database identity limitation: {result.database_state.limitation}",
        f"Excluded unusable report: {EXCLUDED_REPORT_FILENAME}",
    ]
    for report in result.plan.reports:
        lines.append(
            f"- {report.approved.report_date} | {report.approved.filename} | "
            f"rows={report.approved.row_count} | sha256={report.approved.sha256} | "
            f"approved_exception={'yes' if report.approved_exception_used else 'no'}"
        )
        lines.extend(f"  warning: {warning}" for warning in report.warnings)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run_batch(
            args.source_dir,
            dry_run=args.dry_run,
            rebuild_history=args.rebuild_history,
        )
    except HistoricalBackfillError as exc:
        print(f"Historical backfill failed: {exc}")
        return 1
    print(format_result(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
