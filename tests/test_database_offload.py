import ast
import asyncio
import json
import threading
import time
from pathlib import Path

import pandas as pd
import pytest

from src.app.services import database, performance
from src.app.services.database import read_dataframe, read_scalar
from src.app.services.performance import PerformanceConfig, PerformanceService


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAIN = PROJECT_ROOT / "src/app/main.py"
EXECUTIVE = PROJECT_ROOT / "src/app/pages/executive.py"


class FakeConnection:
    def __init__(self, events: list[tuple]) -> None:
        self.events = events

    def __enter__(self):
        self.events.append(("enter", threading.get_ident()))
        return self

    def __exit__(self, *_args):
        self.events.append(("exit", threading.get_ident()))


class FakeEngine:
    def __init__(self, events: list[tuple]) -> None:
        self.events = events

    def connect(self) -> FakeConnection:
        self.events.append(("connect", threading.get_ident()))
        return FakeConnection(self.events)


def run(coro):
    return asyncio.run(coro)


def operations(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = [
        (node.lineno, keyword.value.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        for keyword in node.keywords
        if keyword.arg == "operation"
        and isinstance(keyword.value, ast.Constant)
        and isinstance(keyword.value.value, str)
    ]
    return [operation for _, operation in sorted(found)]


def test_dataframe_work_runs_off_event_loop_and_preserves_result_and_params(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[tuple] = []
    expected = pd.DataFrame({"value": [3, 1]})
    params = {"client": "unchanged"}
    event_thread = threading.get_ident()

    def fake_read_sql(statement, connection, params=None):
        events.append(("read_sql", threading.get_ident(), str(statement), params, connection))
        return expected

    monkeypatch.setattr(database.pd, "read_sql", fake_read_sql)
    result = run(
        read_dataframe(
            FakeEngine(events),
            "SELECT value FROM unchanged",
            operation="test_query",
            params=params,
        )
    )

    worker_threads = {event[1] for event in events}
    assert event_thread not in worker_threads
    assert events[0][0] == "connect"
    assert events[1][0] == "enter"
    assert events[2][0] == "read_sql"
    assert events[2][3] is params
    assert events[2][4] is not None
    pd.testing.assert_frame_equal(result, expected)


def test_slow_query_does_not_starve_async_ticker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[tuple] = []
    ticks: list[float] = []

    def slow_read_sql(*_args, **_kwargs):
        time.sleep(0.55)
        return pd.DataFrame({"value": [1]})

    monkeypatch.setattr(database.pd, "read_sql", slow_read_sql)

    async def scenario() -> None:
        async def ticker() -> None:
            started = time.perf_counter()
            while time.perf_counter() - started < 0.5:
                ticks.append(time.perf_counter())
                await asyncio.sleep(0.02)

        ticker_task = asyncio.create_task(ticker())
        await read_dataframe(
            FakeEngine(events),
            "SELECT 1",
            operation="slow_query",
        )
        await ticker_task

    run(scenario())
    gaps = [right - left for left, right in zip(ticks, ticks[1:])]
    assert len(ticks) >= 15
    assert max(gaps) < 0.15


def test_exceptions_propagate_and_connection_closes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[tuple] = []

    def fail(*_args, **_kwargs):
        raise RuntimeError("database failed")

    monkeypatch.setattr(database.pd, "read_sql", fail)
    with pytest.raises(RuntimeError, match="database failed"):
        run(
            read_dataframe(
                FakeEngine(events),
                "SELECT 1",
                operation="failure",
            )
        )
    assert events[-1][0] == "exit"


def test_awaited_queries_are_sequential(monkeypatch: pytest.MonkeyPatch) -> None:
    activity: list[str] = []

    def fake_read_sql(statement, *_args, **_kwargs):
        value = str(statement)
        activity.append(f"start:{value}")
        time.sleep(0.05)
        activity.append(f"end:{value}")
        return pd.DataFrame({"value": [value]})

    monkeypatch.setattr(database.pd, "read_sql", fake_read_sql)

    async def scenario() -> None:
        engine = FakeEngine([])
        await read_dataframe(engine, "first", operation="first")
        await read_dataframe(engine, "second", operation="second")

    run(scenario())
    assert activity == ["start:first", "end:first", "start:second", "end:second"]


def test_dashboard_and_executive_query_order_is_unchanged() -> None:
    assert operations(MAIN)[:4] == [
        "latest_snapshot",
        "dashboard_kpi",
        "dashboard_branches",
        "dashboard_clients",
    ]
    assert operations(EXECUTIVE)[:14] == [
        "executive_kpi",
        "executive_portfolio_history",
        "executive_maturity_history",
        "executive_debt_age_history",
        "executive_payment_term_history",
        "executive_long_green_history",
        "executive_rating_exposure",
        "executive_credit_quality_exposure",
        "executive_rating_migration",
        "executive_client_risk_bubble",
        "executive_hidden_risk_bubble",
        "executive_branch_health",
        "executive_hidden_risk",
        "executive_term_shift_kpi",
    ]


def test_pages_are_async_and_database_calls_are_awaited() -> None:
    for path, function_name in [
        (MAIN, "dashboard"),
        (EXECUTIVE, "executive_overview_page"),
    ]:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        function = next(
            node
            for node in tree.body
            if isinstance(node, ast.AsyncFunctionDef) and node.name == function_name
        )
        calls = [
            node
            for node in ast.walk(function)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in {"query_df", "get_latest_snapshot_date"}
        ]
        awaited = {
            id(node.value)
            for node in ast.walk(function)
            if isinstance(node, ast.Await) and isinstance(node.value, ast.Call)
        }
        assert calls
        assert all(id(call) in awaited for call in calls)


def test_worker_contains_no_ui_and_uses_nicegui_shared_pool() -> None:
    source = (PROJECT_ROOT / "src/app/services/database.py").read_text(encoding="utf-8")
    assert "ui." not in source
    assert "ThreadPoolExecutor" not in source
    assert "run.io_bound" in source


def test_query_instrumentation_keeps_context_rows_and_redacts_sql(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    log_path = tmp_path / "performance.jsonl"
    service = PerformanceService(
        PerformanceConfig(
            enabled=True,
            log_path=log_path,
            slow_query_ms=0.001,
            log_all_spans=True,
        )
    )
    monkeypatch.setattr(performance, "_service", service)
    monkeypatch.setattr(
        database.pd,
        "read_sql",
        lambda *_args, **_kwargs: pd.DataFrame({"value": [1, 2]}),
    )

    async def scenario() -> None:
        await service.start()
        with service.span(
            "page_build",
            "test_page_build",
            page="test_page",
            route="/test",
        ):
            await read_dataframe(
                FakeEngine([]),
                "SELECT secret_value",
                operation="correlated_query",
                params={"password": "not-logged"},
            )
        await service.stop()

    run(scenario())
    raw = log_path.read_text(encoding="utf-8")
    events = [json.loads(line) for line in raw.splitlines()]
    page = next(event for event in events if event["event"] == "page_build")
    query = next(event for event in events if event.get("operation") == "correlated_query")
    assert query["request_id"] == page["request_id"]
    assert query["parent_span_id"] == page["span_id"]
    assert query["page"] == "test_page"
    assert query["rows"] == 2
    assert "secret_value" not in raw
    assert "not-logged" not in raw


def test_disabled_instrumentation_creates_no_log(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    log_path = tmp_path / "disabled.jsonl"
    monkeypatch.setattr(
        performance,
        "_service",
        PerformanceService(PerformanceConfig(enabled=False, log_path=log_path)),
    )
    monkeypatch.setattr(
        database.pd,
        "read_sql",
        lambda *_args, **_kwargs: pd.DataFrame({"value": [1]}),
    )
    result = run(
        read_dataframe(FakeEngine([]), "SELECT 1", operation="disabled")
    )
    assert len(result) == 1
    assert not log_path.exists()


def test_scalar_connection_and_execution_are_worker_owned() -> None:
    event_thread = threading.get_ident()
    events: list[tuple] = []

    class ScalarResult:
        def scalar(self):
            events.append(("scalar", threading.get_ident()))
            return 42

    class ScalarConnection(FakeConnection):
        def execute(self, statement):
            events.append(("execute", threading.get_ident(), str(statement)))
            return ScalarResult()

    class ScalarEngine(FakeEngine):
        def connect(self):
            events.append(("connect", threading.get_ident()))
            return ScalarConnection(events)

    assert run(read_scalar(ScalarEngine(events), "SELECT 42", operation="scalar")) == 42
    assert all(event[1] != event_thread for event in events)


def test_cancelled_await_does_not_interrupt_worker_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entered = threading.Event()
    release = threading.Event()
    closed = threading.Event()

    class Connection(FakeConnection):
        def __exit__(self, *_args):
            super().__exit__(*_args)
            closed.set()

    class Engine(FakeEngine):
        def connect(self):
            self.events.append(("connect", threading.get_ident()))
            return Connection(self.events)

    def blocking_read(*_args, **_kwargs):
        entered.set()
        assert release.wait(timeout=2)
        return pd.DataFrame({"value": [1]})

    monkeypatch.setattr(database.pd, "read_sql", blocking_read)

    async def scenario() -> None:
        task = asyncio.create_task(
            read_dataframe(Engine([]), "SELECT 1", operation="cancelled")
        )
        while not entered.is_set():
            await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert not closed.is_set()
        release.set()
        assert await asyncio.to_thread(closed.wait, 2)

    run(scenario())


def test_scalar_none_is_not_confused_with_cancellation() -> None:
    class ScalarResult:
        def scalar(self):
            return None

    class Connection(FakeConnection):
        def execute(self, _statement):
            return ScalarResult()

    class Engine(FakeEngine):
        def connect(self):
            return Connection(self.events)

    assert run(read_scalar(Engine([]), "SELECT NULL", operation="null")) is None


def test_async_page_decorator_spans_full_await(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    log_path = tmp_path / "async-page.jsonl"
    service = PerformanceService(
        PerformanceConfig(enabled=True, log_path=log_path, log_all_spans=True)
    )
    monkeypatch.setattr(performance, "_service", service)

    @performance.page_build("async_page", "/async")
    async def page():
        await asyncio.sleep(0.03)
        return "done"

    async def scenario():
        await service.start()
        result = await page()
        await service.stop()
        return result

    assert run(scenario()) == "done"
    events = [json.loads(line) for line in log_path.read_text().splitlines()]
    event = next(item for item in events if item.get("operation") == "async_page_page_build")
    assert event["duration_ms"] >= 20
