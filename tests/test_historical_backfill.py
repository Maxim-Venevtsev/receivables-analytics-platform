from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from src.ingestion import historical_backfill as backfill


def _row(**overrides):
    value = {
        "parent_org_id": "100",
        "client_id": "27444",
        "client_name": "ИП Богачкин А. В.",
        "client_group": "КГ_Красн",
        "order_number": "26063885",
        "print_invoice_number": "26017382",
        "system_invoice_number": "IS2116419",
        "invoice_date": date(2026, 7, 2),
        "due_date": date(2026, 6, 29),
        "payment_term_days": -3,
        "invoice_amount": 3020.76,
        "currency_code": "RUR",
        "analytics_type": "ARS_NEW",
    }
    value.update(overrides)
    return value


def _make_complete_directory(tmp_path: Path) -> Path:
    for item in backfill.APPROVED_REPORTS:
        (tmp_path / item.filename).write_bytes(item.filename.encode("utf-8"))
    (tmp_path / backfill.EXCLUDED_REPORT_FILENAME).write_bytes(b"excluded")
    return tmp_path


def _prepared(approved, path):
    return backfill.PreparedReport(
        approved=approved,
        source_path=path,
        dataframe=pd.DataFrame([_row()]),
        metadata={"report_generated_date": approved.report_date},
    )


def test_complete_batch_is_accepted_and_sorted(monkeypatch, tmp_path):
    source = _make_complete_directory(tmp_path)
    monkeypatch.setattr(
        backfill,
        "_prepare_report",
        lambda path, approved: _prepared(approved, path),
    )

    plan = backfill.prepare_batch(source)

    assert len(plan.reports) == 8
    assert [item.approved.report_date for item in plan.reports] == sorted(
        item.report_date for item in backfill.APPROVED_REPORTS
    )
    assert all(item.source_path.exists() for item in plan.reports)


def test_missing_approved_file_is_rejected(monkeypatch, tmp_path):
    source = _make_complete_directory(tmp_path)
    (source / backfill.APPROVED_REPORTS[3].filename).unlink()

    with pytest.raises(backfill.HistoricalBackfillError, match="incomplete"):
        backfill.prepare_batch(source)


def test_unapproved_duplicate_or_extra_file_is_rejected(tmp_path):
    source = _make_complete_directory(tmp_path)
    (source / "duplicate-report.txt").write_bytes(b"duplicate")

    with pytest.raises(backfill.HistoricalBackfillError, match="Unapproved"):
        backfill.prepare_batch(source)


def test_july_10_is_never_part_of_the_batch(monkeypatch, tmp_path):
    source = _make_complete_directory(tmp_path)
    seen = []

    def prepare(path, approved):
        seen.append(path.name)
        return _prepared(approved, path)

    monkeypatch.setattr(backfill, "_prepare_report", prepare)
    backfill.prepare_batch(source)

    assert backfill.EXCLUDED_REPORT_FILENAME not in seen


def test_altered_sha_is_rejected(monkeypatch, tmp_path):
    approved = backfill.APPROVED_REPORTS[0]
    path = tmp_path / approved.filename
    path.write_bytes(b"altered")
    monkeypatch.setattr(backfill, "compute_sha256", lambda path: "0" * 64)

    with pytest.raises(backfill.HistoricalBackfillError, match="SHA256"):
        backfill._prepare_report(path, approved)


def test_exact_anomaly_is_accepted(monkeypatch, tmp_path):
    approved = backfill.APPROVED_REPORTS[0]
    path = tmp_path / approved.filename
    path.write_bytes(b"approved")
    frame = pd.DataFrame([_row()] * approved.row_count)
    frame.loc[1:, "payment_term_days"] = 0
    frame.loc[1:, "due_date"] = date(2026, 7, 2)
    monkeypatch.setattr(backfill, "compute_sha256", lambda path: approved.sha256)
    monkeypatch.setattr(
        backfill,
        "parse_receivables_txt",
        lambda path: (frame, {"report_generated_date": approved.report_date}),
    )

    report = backfill._prepare_report(path, approved)

    assert report.approved_exception_used is True


def test_additional_anomaly_is_rejected(monkeypatch, tmp_path):
    approved = backfill.APPROVED_REPORTS[0]
    path = tmp_path / approved.filename
    path.write_bytes(b"approved")
    rows = [_row(), _row(system_invoice_number="OTHER")]
    rows.extend(
        _row(
            client_id=str(index + 1000),
            due_date=date(2026, 7, 2),
            payment_term_days=0,
        )
        for index in range(approved.row_count - 2)
    )
    frame = pd.DataFrame(rows)
    monkeypatch.setattr(backfill, "compute_sha256", lambda path: approved.sha256)
    monkeypatch.setattr(
        backfill,
        "parse_receivables_txt",
        lambda path: (frame, {"report_generated_date": approved.report_date}),
    )

    with pytest.raises(backfill.HistoricalBackfillError, match="Validation"):
        backfill._prepare_report(path, approved)


class FakeTransaction:
    def __init__(self, connection):
        self.connection = connection
        self.committed = False
        self.rolled_back = False

    def __enter__(self):
        return self.connection

    def __exit__(self, exc_type, exc, traceback):
        self.committed = exc_type is None
        self.rolled_back = exc_type is not None
        return False


class FakeConnection:
    def execute(self, statement, params=None):
        return FakeResult()


class FakeResult:
    def scalar_one(self):
        return None

    def mappings(self):
        return self

    def all(self):
        return []


class FakeEngine:
    def __init__(self):
        self.connection = FakeConnection()
        self.transaction = FakeTransaction(self.connection)
        self.begin_called = 0
        self.connect_called = 0

    def begin(self):
        self.begin_called += 1
        return self.transaction

    @contextmanager
    def connect(self):
        self.connect_called += 1
        yield self.connection


def _batch_plan(tmp_path):
    reports = [
        _prepared(item, tmp_path / item.filename) for item in backfill.APPROVED_REPORTS
    ]
    return backfill.BatchPlan(tmp_path, reports)


def _all_missing_state():
    dates = [item.report_date for item in backfill.APPROVED_REPORTS]
    return backfill.DatabaseState("all_missing", dates, dates)


def _patch_success_path(monkeypatch, tmp_path):
    plan = _batch_plan(tmp_path)
    dates = [date(2026, 7, 13), date(2026, 7, 24)]
    monkeypatch.setattr(backfill, "prepare_batch", lambda path: plan)
    monkeypatch.setattr(
        backfill, "inspect_database_state", lambda conn, plan, lock=False: _all_missing_state()
    )
    monkeypatch.setattr(backfill, "_acquire_locks", lambda conn: None)
    monkeypatch.setattr(backfill, "_affected_fact_dates", lambda conn: dates)
    monkeypatch.setattr(backfill, "_create_stage_tables", lambda conn: None)
    monkeypatch.setattr(backfill, "_read_maintenance_sql", lambda name: "SELECT 1")
    monkeypatch.setattr(backfill, "_verify_stage", lambda conn, dates: (20, 20))
    monkeypatch.setattr(backfill, "_replace_history_suffix", lambda conn: None)
    monkeypatch.setattr(
        backfill, "_verify_final_state", lambda conn, plan, dates: (20, 20)
    )
    return plan, dates


def test_dry_run_performs_no_write_transaction(monkeypatch, tmp_path):
    plan = _batch_plan(tmp_path)
    state = _all_missing_state()
    monkeypatch.setattr(backfill, "prepare_batch", lambda path: plan)
    monkeypatch.setattr(
        backfill, "inspect_database_state", lambda conn, plan: state
    )
    engine = FakeEngine()

    result = backfill.run_batch(tmp_path, dry_run=True, engine=engine)

    assert engine.connect_called == 1
    assert engine.begin_called == 0
    assert result.loaded_dates == []


def test_all_missing_batch_loads_all_facts_in_one_transaction(monkeypatch, tmp_path):
    plan, dates = _patch_success_path(monkeypatch, tmp_path)
    loaded = []
    monkeypatch.setattr(
        backfill,
        "load_receivables_snapshot_in_transaction",
        lambda conn, df, metadata, path: loaded.append(path.name),
    )
    engine = FakeEngine()

    result = backfill.run_batch(tmp_path, engine=engine)

    assert loaded == [item.approved.filename for item in plan.reports]
    assert result.rebuilt_dates == dates
    assert engine.begin_called == 1
    assert engine.transaction.committed is True


@pytest.mark.parametrize(
    "failure_point",
    ["fact", "rating", "credit", "stage"],
)
def test_any_batch_failure_rolls_back_everything(
    monkeypatch, tmp_path, failure_point
):
    _patch_success_path(monkeypatch, tmp_path)

    def load(*args):
        if failure_point == "fact":
            raise RuntimeError("fact failed")

    def sql(name):
        if failure_point == "rating" and "rating.sql" in name:
            raise RuntimeError("rating failed")
        if failure_point == "credit" and "credit_quality" in name:
            raise RuntimeError("credit failed")
        return "SELECT 1"

    monkeypatch.setattr(backfill, "load_receivables_snapshot_in_transaction", load)
    monkeypatch.setattr(backfill, "_read_maintenance_sql", sql)
    if failure_point == "stage":
        monkeypatch.setattr(
            backfill,
            "_verify_stage",
            lambda *args: (_ for _ in ()).throw(RuntimeError("stage failed")),
        )
    engine = FakeEngine()

    with pytest.raises(RuntimeError):
        backfill.run_batch(tmp_path, engine=engine)

    assert engine.transaction.rolled_back is True
    assert engine.transaction.committed is False


def test_exact_existing_complete_batch_is_idempotent(monkeypatch, tmp_path):
    plan = _batch_plan(tmp_path)
    state = backfill.DatabaseState(
        "all_exact",
        [date(2026, 7, 13), date(2026, 7, 24)],
        history_complete=True,
    )
    monkeypatch.setattr(backfill, "prepare_batch", lambda path: plan)
    monkeypatch.setattr(backfill, "_acquire_locks", lambda conn: None)
    monkeypatch.setattr(
        backfill,
        "inspect_database_state",
        lambda conn, plan, lock=False: state,
    )
    monkeypatch.setattr(
        backfill,
        "load_receivables_snapshot_in_transaction",
        lambda *args: pytest.fail("must not load exact facts"),
    )
    engine = FakeEngine()

    result = backfill.run_batch(tmp_path, engine=engine)

    assert result.no_op is True


class InvariantResult:
    def __init__(self, *, scalar=None, rows=None):
        self.scalar = scalar
        self.rows = rows or []

    def scalar_one(self):
        return self.scalar

    def mappings(self):
        return self

    def all(self):
        return self.rows


class InvariantConnection:
    def __init__(self, future_rows=None):
        self.future_rows = future_rows or []

    def execute(self, statement, params=None):
        sql = str(statement)
        if "effective_snapshot_date" in sql or "relpersistence" in sql:
            return InvariantResult(scalar=False)
        if "v_receivables_current_snapshot" in sql:
            return InvariantResult(scalar=date(2026, 7, 24))
        if "MAX(report_generated_date)" in sql:
            return InvariantResult(scalar=date(2026, 7, 24))
        if "future_rows" in sql:
            return InvariantResult(rows=self.future_rows)
        raise AssertionError(f"Unexpected invariant SQL: {sql}")


@pytest.mark.parametrize(
    ("history_table", "earliest", "latest"),
    [
        ("core.client_rating_history", date(2026, 7, 25), date(2026, 7, 26)),
        (
            "core.client_credit_quality_history",
            date(2026, 7, 27),
            date(2026, 7, 27),
        ),
    ],
)
def test_common_invariant_rejects_future_history(
    history_table, earliest, latest
):
    connection = InvariantConnection(
        [{
            "history_table": history_table,
            "future_rows": 2,
            "earliest_date": earliest,
            "latest_date": latest,
        }]
    )

    with pytest.raises(backfill.HistoricalBackfillError) as error:
        backfill._verify_production_invariants(connection)

    message = str(error.value)
    assert "latest fact date 2026-07-24" in message
    assert f"table={history_table}" in message
    assert "future_rows=2" in message
    assert f"earliest={earliest}" in message
    assert f"latest={latest}" in message


def test_common_invariant_accepts_history_ending_at_latest_fact_date():
    backfill._verify_production_invariants(InvariantConnection())


def test_dry_run_rejects_future_history_without_writes(monkeypatch, tmp_path):
    plan = _batch_plan(tmp_path)
    monkeypatch.setattr(backfill, "prepare_batch", lambda path: plan)
    engine = FakeEngine()
    engine.connection = InvariantConnection(
        [{
            "history_table": "core.client_rating_history",
            "future_rows": 1,
            "earliest_date": date(2026, 7, 25),
            "latest_date": date(2026, 7, 25),
        }]
    )

    with pytest.raises(backfill.HistoricalBackfillError, match="future_rows=1"):
        backfill.run_batch(tmp_path, dry_run=True, engine=engine)

    assert engine.connect_called == 1
    assert engine.begin_called == 0


def test_all_exact_no_op_rejects_future_history(monkeypatch, tmp_path):
    plan = _batch_plan(tmp_path)
    state = backfill.DatabaseState(
        "all_exact",
        [date(2026, 7, 13), date(2026, 7, 24)],
        history_complete=True,
    )
    monkeypatch.setattr(backfill, "prepare_batch", lambda path: plan)
    monkeypatch.setattr(
        backfill,
        "inspect_database_state",
        lambda conn, plan, lock=False: state,
    )
    monkeypatch.setattr(backfill, "_acquire_locks", lambda conn: None)
    engine = FakeEngine()
    engine.connection = InvariantConnection(
        [{
            "history_table": "core.client_rating_history",
            "future_rows": 1,
            "earliest_date": date(2026, 7, 25),
            "latest_date": date(2026, 7, 25),
        }]
    )
    engine.transaction = FakeTransaction(engine.connection)

    with pytest.raises(backfill.HistoricalBackfillError, match="future_rows=1"):
        backfill.run_batch(tmp_path, engine=engine)

    assert engine.transaction.rolled_back is True
    assert engine.transaction.committed is False


def test_reconstruction_final_verification_rechecks_future_history(
    monkeypatch, tmp_path
):
    plan = _batch_plan(tmp_path)
    expected = [
        {
            "report_generated_date": report.approved.report_date,
            "loads": 1,
            "filenames": 1,
            "fact_rows": report.approved.row_count,
        }
        for report in plan.reports
    ]

    class FinalConnection:
        def execute(self, statement, params=None):
            sql = str(statement)
            if "COUNT(DISTINCT load_id)" in sql:
                return InvariantResult(rows=expected)
            if "v_receivables_current_snapshot" in sql:
                return InvariantResult(scalar=date(2026, 7, 24))
            if "MAX(report_generated_date)" in sql:
                return InvariantResult(scalar=date(2026, 7, 24))
            if "future_rows" in sql:
                return InvariantResult(rows=[{
                    "history_table": "core.client_credit_quality_history",
                    "future_rows": 1,
                    "earliest_date": date(2026, 7, 25),
                    "latest_date": date(2026, 7, 25),
                }])
            raise AssertionError(f"Unexpected final verification SQL: {sql}")

    monkeypatch.setattr(
        backfill, "_verify_history_tables", lambda conn, dates: (20, 20)
    )

    with pytest.raises(backfill.HistoricalBackfillError, match="future_rows=1"):
        backfill._verify_final_state(
            FinalConnection(),
            plan,
            [date(2026, 7, 13), date(2026, 7, 24)],
        )


def test_all_exact_cli_wording_is_metadata_qualified(tmp_path):
    result = backfill.BatchResult(
        plan=_batch_plan(tmp_path),
        dry_run=True,
        database_state=backfill.DatabaseState(
            "all_exact",
            [date(2026, 7, 13), date(2026, 7, 24)],
            history_complete=True,
        ),
        no_op=True,
    )

    output = backfill.format_result(result)

    assert "Database state: facts_match_available_database_metadata" in output
    assert "Source file identity: audited SHA256 validation passed" in output
    assert "raw.snapshot_loads does not store SHA256" in output
    assert "Cryptographic identity of already-loaded database rows cannot be proven" in output
    assert "Database state: all_exact" not in output


def test_mixed_state_is_rejected_before_writes(monkeypatch, tmp_path):
    plan = _batch_plan(tmp_path)
    state = backfill.DatabaseState("mixed", [], [date(2026, 7, 20)])
    monkeypatch.setattr(backfill, "prepare_batch", lambda path: plan)
    monkeypatch.setattr(backfill, "_acquire_locks", lambda conn: None)
    monkeypatch.setattr(
        backfill,
        "inspect_database_state",
        lambda conn, plan, lock=False: state,
    )
    engine = FakeEngine()

    with pytest.raises(backfill.HistoricalBackfillError, match="Mixed"):
        backfill.run_batch(tmp_path, engine=engine)

    assert engine.transaction.rolled_back is True


def test_conflicting_date_is_rejected_by_database_inspection(tmp_path):
    plan = _batch_plan(tmp_path)
    first = plan.reports[0].approved

    class ConflictResult:
        def mappings(self):
            return self

        def all(self):
            return [{
                "load_id": 99,
                "source_file_name": "different-source.txt",
                "report_generated_date": first.report_date,
                "row_count_loaded": first.row_count,
                "status": "loaded",
                "fact_rows": first.row_count,
            }]

    class ConflictConnection:
        def execute(self, statement, params=None):
            return ConflictResult()

    with pytest.raises(backfill.HistoricalBackfillError, match="conflicting"):
        backfill.inspect_database_state(ConflictConnection(), plan)


def test_source_files_are_never_modified(monkeypatch, tmp_path):
    source = _make_complete_directory(tmp_path)
    before = {path.name: path.read_bytes() for path in source.iterdir()}
    monkeypatch.setattr(
        backfill,
        "_prepare_report",
        lambda path, approved: _prepared(approved, path),
    )

    backfill.prepare_batch(source)

    after = {path.name: path.read_bytes() for path in source.iterdir()}
    assert after == before


def test_normal_ingestion_entry_point_and_session_context_are_unchanged():
    source = Path(backfill.__file__).read_text(encoding="utf-8")
    normal = (backfill.PROJECT_ROOT / "src/ingestion/run_ingestion.py").read_text(
        encoding="utf-8"
    )

    assert "debt_management.snapshot_date" not in source
    assert "set_config" not in source
    assert "load_receivables_snapshot(df, metadata, path)" in normal
    assert not (
        backfill.PROJECT_ROOT
        / "sql/ddl/038_historical_backfill_snapshot_context.sql"
    ).exists()
