from __future__ import annotations

import asyncio
import json
import subprocess
import threading
import time
from pathlib import Path

import pytest

from src.app.services.performance import (
    PerformanceConfig,
    PerformanceService,
    get_reload_enabled,
    page_build,
    parse_bool,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def make_config(
    tmp_path: Path,
    *,
    enabled: bool = True,
    log_all_spans: bool = True,
    queue_size: int = 10_000,
    lag_ms: float = 20,
    interval_ms: float = 10,
) -> PerformanceConfig:
    return PerformanceConfig(
        enabled=enabled,
        log_path=tmp_path / "performance" / "performance.jsonl",
        slow_query_ms=1,
        slow_page_ms=1,
        event_loop_lag_ms=lag_ms,
        event_loop_interval_ms=interval_ms,
        log_all_spans=log_all_spans,
        queue_size=queue_size,
    )


def run_service(service: PerformanceService, callback=None) -> None:
    async def scenario() -> None:
        await service.start()
        if callback is not None:
            result = callback()
            if asyncio.iscoroutine(result):
                await result
        await asyncio.sleep(0.03)
        await service.stop()

    asyncio.run(scenario())


def read_events(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def test_disabled_instrumentation_creates_nothing(tmp_path: Path) -> None:
    config = make_config(tmp_path, enabled=False)
    service = PerformanceService(config)

    with service.span("query_timing", "disabled_query"):
        pass
    run_service(service)

    assert not config.log_path.exists()
    assert not config.log_path.parent.exists()


def test_enabled_service_writes_independent_valid_json_lines(tmp_path: Path) -> None:
    service = PerformanceService(make_config(tmp_path))

    def callback() -> None:
        with service.span("query_timing", "safe_query") as current:
            current.set_rows(3)

    run_service(service, callback)
    events = read_events(service.config.log_path)

    assert events
    assert all(event["schema_version"] == 1 for event in events)
    assert {event["event"] for event in events} >= {
        "process_start",
        "query_timing",
        "process_stop",
    }


def test_successful_span_records_duration_rows_and_return_is_unchanged(
    tmp_path: Path,
) -> None:
    service = PerformanceService(make_config(tmp_path))

    def business_function() -> dict:
        with service.span("query_timing", "return_test") as current:
            current.set_rows(2)
            return {"unchanged": True}

    result: dict | None = None

    def callback() -> None:
        nonlocal result
        result = business_function()

    run_service(service, callback)
    event = next(
        item
        for item in read_events(service.config.log_path)
        if item.get("operation") == "return_test"
    )

    assert result == {"unchanged": True}
    assert event["success"] is True
    assert event["rows"] == 2
    assert event["duration_ms"] >= 0


def test_failed_span_is_sanitized_and_reraises(tmp_path: Path) -> None:
    service = PerformanceService(make_config(tmp_path))
    caught: BaseException | None = None

    def callback() -> None:
        nonlocal caught
        try:
            with service.span("query_timing", "failure_test"):
                raise ValueError(
                    "password=hunter2 postgresql://dbuser:dbpass@private/db"
                )
        except ValueError as exc:
            caught = exc

    run_service(service, callback)
    event = next(
        item
        for item in read_events(service.config.log_path)
        if item.get("operation") == "failure_test"
    )
    serialized = json.dumps(event)

    assert isinstance(caught, ValueError)
    assert event["success"] is False
    assert event["exception_class"] == "ValueError"
    assert "hunter2" not in serialized
    assert "dbuser" not in serialized
    assert "dbpass" not in serialized
    assert "[REDACTED]" in event["error"]


def test_event_api_drops_sql_parameters_and_sensitive_fields(tmp_path: Path) -> None:
    service = PerformanceService(make_config(tmp_path))

    def callback() -> None:
        service.emit(
            "query_timing",
            operation="allowed_name",
            success=True,
            sql="SELECT secret FROM private",
            params={"password": "do-not-log"},
            database_url="postgresql://user:password@host/db",
            rows=1,
        )

    run_service(service, callback)
    content = service.config.log_path.read_text(encoding="utf-8")

    assert "SELECT secret" not in content
    assert "do-not-log" not in content
    assert "postgresql://" not in content
    assert '"operation":"allowed_name"' in content


def test_concurrent_events_do_not_corrupt_jsonl(tmp_path: Path) -> None:
    service = PerformanceService(make_config(tmp_path))

    def callback() -> None:
        threads = [
            threading.Thread(
                target=lambda offset=index: [
                    service.emit(
                        "query_timing",
                        operation=f"thread_{offset}",
                        rows=item,
                        success=True,
                    )
                    for item in range(50)
                ]
            )
            for index in range(8)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

    run_service(service, callback)
    events = read_events(service.config.log_path)
    query_events = [item for item in events if item["event"] == "query_timing"]

    assert len(query_events) == 400


def test_queue_overflow_is_bounded_and_written_when_writer_recovers(
    tmp_path: Path,
) -> None:
    service = PerformanceService(make_config(tmp_path, queue_size=1))
    service.emit("query_timing", operation="first", success=True)
    service.emit("query_timing", operation="dropped", success=True)
    assert service.dropped_events == 1

    run_service(service)
    events = read_events(service.config.log_path)

    assert any(item["event"] == "event_queue_overflow" for item in events)
    assert service._queue.maxsize == 1


def test_writer_failure_does_not_break_business_code(tmp_path: Path) -> None:
    blocked_parent = tmp_path / "not-a-directory"
    blocked_parent.write_text("file", encoding="utf-8")
    config = make_config(tmp_path)
    config = PerformanceConfig(
        **{
            **config.__dict__,
            "log_path": blocked_parent / "performance.jsonl",
        }
    )
    service = PerformanceService(config)
    result = None

    def callback() -> None:
        nonlocal result
        with service.span("query_timing", "writer_failure"):
            result = "business-result"

    run_service(service, callback)

    assert result == "business-result"


def test_page_context_propagates_to_child_span(tmp_path: Path) -> None:
    service = PerformanceService(make_config(tmp_path))

    def callback() -> None:
        with service.span(
            "page_build",
            "test_page_build",
            page="test_page",
            route="/test",
        ):
            with service.span("query_timing", "child_query"):
                pass

    run_service(service, callback)
    events = read_events(service.config.log_path)
    page_event = next(item for item in events if item["event"] == "page_build")
    child_event = next(
        item for item in events if item.get("operation") == "child_query"
    )

    assert child_event["request_id"] == page_event["request_id"]
    assert child_event["page"] == "test_page"
    assert child_event["route"] == "/test"
    assert child_event["parent_span_id"] == page_event["span_id"]


def test_page_decorator_preserves_function_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.app.services import performance as performance_module

    service = PerformanceService(make_config(tmp_path))
    monkeypatch.setattr(performance_module, "_service", service)

    @page_build("decorated", "/decorated")
    def decorated(value: int) -> int:
        return value + 1

    result = None

    def callback() -> None:
        nonlocal result
        result = decorated(41)

    run_service(service, callback)

    assert result == 42


def test_lag_monitor_reports_synthetic_block_and_stops(tmp_path: Path) -> None:
    service = PerformanceService(make_config(tmp_path, lag_ms=15, interval_ms=5))

    async def callback() -> None:
        await asyncio.sleep(0.015)
        with service.span(
            "page_build",
            "blocking_page_build",
            page="blocking_page",
            route="/blocking",
        ):
            time.sleep(0.06)
        await asyncio.sleep(0.025)

    run_service(service, callback)
    events = read_events(service.config.log_path)

    lag_event = next(item for item in events if item["event"] == "event_loop_lag")
    page_event = next(
        item
        for item in events
        if item.get("operation") == "blocking_page_build"
    )

    assert lag_event["request_id"] == page_event["request_id"]
    assert lag_event["page"] == "blocking_page"
    assert service.monitor_running is False


def test_normal_scheduling_does_not_report_critical_lag(tmp_path: Path) -> None:
    service = PerformanceService(
        make_config(tmp_path, lag_ms=500, interval_ms=10),
    )

    async def callback() -> None:
        await asyncio.sleep(0.06)

    run_service(service, callback)
    events = read_events(service.config.log_path)

    assert not any(item["event"] == "event_loop_lag" for item in events)


def test_lag_monitor_starts_only_once(tmp_path: Path) -> None:
    service = PerformanceService(make_config(tmp_path))

    async def scenario() -> None:
        service.start_writer()
        await service.start_lag_monitor()
        first_task = service._monitor_task
        await service.start_lag_monitor()
        assert service._monitor_task is first_task
        await service.stop_lag_monitor()

    asyncio.run(scenario())


def test_process_events_share_process_instance_id(tmp_path: Path) -> None:
    service = PerformanceService(make_config(tmp_path))
    run_service(service)
    events = read_events(service.config.log_path)
    process_events = [
        event
        for event in events
        if event["event"] in {"process_start", "process_stop"}
    ]

    assert len(process_events) == 2
    assert {
        event["process_instance_id"]
        for event in process_events
    } == {service.process_instance_id}


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, False),
        ("true", True),
        ("TRUE", True),
        ("false", False),
        ("False", False),
    ],
)
def test_reload_boolean_parsing(value: str | None, expected: bool) -> None:
    environ = {} if value is None else {"APP_RELOAD_ENABLED": value}
    assert get_reload_enabled(environ) is expected


def test_ambiguous_boolean_is_rejected() -> None:
    with pytest.raises(ValueError):
        parse_bool("yes")


def test_relative_log_path_resolves_from_project_root(tmp_path: Path) -> None:
    config = PerformanceConfig.from_env(
        tmp_path,
        {
            "PERF_INSTRUMENTATION_ENABLED": "true",
            "PERF_LOG_PATH": "relative/performance.jsonl",
        },
    )

    assert config.log_path == (tmp_path / "relative/performance.jsonl").resolve()


def test_performance_log_path_is_ignored_by_git() -> None:
    result = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={PROJECT_ROOT.as_posix()}",
            "check-ignore",
            "data/performance/performance.jsonl",
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
