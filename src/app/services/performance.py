from __future__ import annotations

import asyncio
import contextvars
import functools
import hashlib
import json
import math
import os
import queue
import re
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping


SCHEMA_VERSION = 1
DEFAULT_LOG_PATH = "data/performance/performance.jsonl"
_STOP = object()
_ALLOWED_EVENTS = {
    "process_start",
    "process_stop",
    "page_build",
    "query_timing",
    "pandas_timing",
    "serialization_timing",
    "plotly_timing",
    "event_loop_lag",
    "uncaught_exception",
    "event_queue_overflow",
    "client_connect",
    "client_disconnect",
}
_ALLOWED_FIELDS = {
    "page",
    "route",
    "operation",
    "duration_ms",
    "rows",
    "request_id",
    "span_id",
    "parent_span_id",
    "success",
    "lag_ms",
    "interval_ms",
    "exception_class",
    "error",
    "error_fingerprint",
    "dropped_events",
}
_SENSITIVE_KEY = re.compile(
    r"(?:sql|param|password|passwd|secret|token|authorization|cookie|credential|"
    r"database_url|db_url|mailbox|username|host|address)",
    re.IGNORECASE,
)
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(password|passwd|secret|token|authorization|cookie|credential|"
    r"database_url|db_url|username|host)\b\s*[:=]\s*[^\s,;]+"
)
_URI_CREDENTIALS = re.compile(r"(?i)\b[a-z][a-z0-9+.-]*://[^/\s:@]+:[^@\s/]+@")
_REQUEST_ID: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "perf_request_id",
    default=None,
)
_PAGE: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "perf_page",
    default=None,
)
_ROUTE: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "perf_route",
    default=None,
)
_SPAN_ID: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "perf_span_id",
    default=None,
)


def parse_bool(value: str | bool | None, *, default: bool = False) -> bool:
    """Parse an environment-style boolean without accepting ambiguous values."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise ValueError(f"Expected 'true' or 'false', got {value!r}")


def get_reload_enabled(environ: Mapping[str, str] | None = None) -> bool:
    source = os.environ if environ is None else environ
    return parse_bool(source.get("APP_RELOAD_ENABLED"), default=False)


def _positive_float(
    environ: Mapping[str, str],
    name: str,
    default: float,
) -> float:
    raw = environ.get(name)
    if raw is None:
        return default
    value = float(raw)
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return value


@dataclass(frozen=True)
class PerformanceConfig:
    enabled: bool
    log_path: Path
    slow_query_ms: float = 500.0
    slow_page_ms: float = 2000.0
    event_loop_lag_ms: float = 500.0
    event_loop_interval_ms: float = 250.0
    log_all_spans: bool = False
    queue_size: int = 10_000

    @classmethod
    def from_env(
        cls,
        project_root: Path,
        environ: Mapping[str, str] | None = None,
    ) -> "PerformanceConfig":
        source = os.environ if environ is None else environ
        configured_path = Path(source.get("PERF_LOG_PATH", DEFAULT_LOG_PATH))
        if not configured_path.is_absolute():
            configured_path = project_root / configured_path
        return cls(
            enabled=parse_bool(
                source.get("PERF_INSTRUMENTATION_ENABLED"),
                default=False,
            ),
            log_path=configured_path.resolve(),
            slow_query_ms=_positive_float(
                source,
                "PERF_SLOW_QUERY_MS",
                500.0,
            ),
            slow_page_ms=_positive_float(
                source,
                "PERF_SLOW_PAGE_MS",
                2000.0,
            ),
            event_loop_lag_ms=_positive_float(
                source,
                "PERF_EVENT_LOOP_LAG_MS",
                500.0,
            ),
            event_loop_interval_ms=_positive_float(
                source,
                "PERF_EVENT_LOOP_INTERVAL_MS",
                250.0,
            ),
            log_all_spans=parse_bool(
                source.get("PERF_LOG_ALL_SPANS"),
                default=False,
            ),
        )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00",
        "Z",
    )


def _sanitize_text(value: Any, *, limit: int = 300) -> str:
    text = str(value).replace("\x00", "")
    text = _SECRET_ASSIGNMENT.sub(lambda match: f"{match.group(1)}=[REDACTED]", text)
    text = _URI_CREDENTIALS.sub("[REDACTED_URL]", text)
    text = text.replace("\r", " ").replace("\n", " ")
    return text[:limit]


def _sanitize_error(exc: BaseException) -> dict[str, str]:
    # Exception messages can contain SQL driver details or business identifiers.
    # V1 intentionally keeps only the class and a non-reversible generic marker.
    error = "[REDACTED]" if str(exc) else ""
    fingerprint_source = type(exc).__name__
    return {
        "exception_class": type(exc).__name__,
        "error": error,
        "error_fingerprint": hashlib.sha256(
            fingerprint_source.encode("utf-8"),
        ).hexdigest()[:16],
    }


class _NullSpan:
    def __enter__(self) -> "_NullSpan":
        return self

    def __exit__(self, *_: Any) -> bool:
        return False

    def set_rows(self, _rows: int | None) -> None:
        return None


class PerformanceSpan:
    def __init__(
        self,
        service: "PerformanceService",
        event: str,
        operation: str,
        *,
        page: str | None = None,
        route: str | None = None,
        rows: int | None = None,
    ) -> None:
        self.service = service
        self.event = event
        self.operation = operation
        self.page = page
        self.route = route
        self.rows = rows
        self.span_id = uuid.uuid4().hex
        self.parent_span_id: str | None = None
        self.request_id: str | None = None
        self._start_ns = 0
        self._tokens: list[tuple[contextvars.ContextVar, contextvars.Token]] = []

    def __enter__(self) -> "PerformanceSpan":
        self._start_ns = time.perf_counter_ns()
        self.parent_span_id = _SPAN_ID.get()
        if self.event == "page_build":
            self.request_id = uuid.uuid4().hex
            self._tokens.extend([
                (_REQUEST_ID, _REQUEST_ID.set(self.request_id)),
                (_PAGE, _PAGE.set(self.page)),
                (_ROUTE, _ROUTE.set(self.route)),
            ])
            self.service.note_page_started(
                self.request_id,
                self.page,
                self.route,
            )
        else:
            self.request_id = _REQUEST_ID.get()
            self.page = self.page or _PAGE.get()
            self.route = self.route or _ROUTE.get()
        self._tokens.append((_SPAN_ID, _SPAN_ID.set(self.span_id)))
        return self

    def set_rows(self, rows: int | None) -> None:
        self.rows = rows

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        _traceback: Any,
    ) -> bool:
        duration_ms = (time.perf_counter_ns() - self._start_ns) / 1_000_000
        fields: dict[str, Any] = {
            "operation": self.operation,
            "duration_ms": round(duration_ms, 3),
            "rows": self.rows,
            "request_id": self.request_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "page": self.page,
            "route": self.route,
            "success": exc is None,
        }
        if exc is not None:
            fields.update(_sanitize_error(exc))
            if self.event == "page_build":
                self.service.emit(
                    "uncaught_exception",
                    operation=self.operation,
                    request_id=self.request_id,
                    page=self.page,
                    route=self.route,
                    success=False,
                    **_sanitize_error(exc),
                )
        if self.service.should_log_span(self.event, duration_ms, exc):
            self.service.emit(self.event, **fields)
        if self.event == "page_build":
            self.service.note_page_finished(
                self.request_id,
                self.page,
                self.route,
            )
        for variable, token in reversed(self._tokens):
            variable.reset(token)
        return False


class PerformanceService:
    def __init__(self, config: PerformanceConfig) -> None:
        self.config = config
        self.process_instance_id = uuid.uuid4().hex
        self._queue: queue.Queue[dict[str, Any] | object] = queue.Queue(
            maxsize=config.queue_size,
        )
        self._writer_thread: threading.Thread | None = None
        self._monitor_task: asyncio.Task | None = None
        self._monitor_stop: asyncio.Event | None = None
        self._dropped_events = 0
        self._dropped_lock = threading.Lock()
        self._page_context_lock = threading.Lock()
        self._active_page_context: tuple[str, str | None, str | None] | None = None
        self._last_page_context: (
            tuple[str, str | None, str | None, float] | None
        ) = None
        self._started = False

    @property
    def dropped_events(self) -> int:
        with self._dropped_lock:
            return self._dropped_events

    @property
    def monitor_running(self) -> bool:
        return self._monitor_task is not None and not self._monitor_task.done()

    def note_page_started(
        self,
        request_id: str,
        page: str | None,
        route: str | None,
    ) -> None:
        with self._page_context_lock:
            self._active_page_context = (request_id, page, route)

    def note_page_finished(
        self,
        request_id: str,
        page: str | None,
        route: str | None,
    ) -> None:
        with self._page_context_lock:
            if (
                self._active_page_context is not None
                and self._active_page_context[0] == request_id
            ):
                self._active_page_context = None
            self._last_page_context = (
                request_id,
                page,
                route,
                time.perf_counter(),
            )

    def lag_page_context(
        self,
        actual: float,
        lag_ms: float,
    ) -> tuple[str | None, str | None, str | None]:
        with self._page_context_lock:
            if self._active_page_context is not None:
                return self._active_page_context
            if self._last_page_context is None:
                return None, None, None
            request_id, page, route, finished_at = self._last_page_context
            correlation_window = (
                lag_ms / 1000
                + 2 * self.config.event_loop_interval_ms / 1000
            )
            if actual - finished_at <= correlation_window:
                return request_id, page, route
            return None, None, None

    def span(
        self,
        event: str,
        operation: str,
        *,
        page: str | None = None,
        route: str | None = None,
        rows: int | None = None,
    ) -> PerformanceSpan | _NullSpan:
        if not self.config.enabled:
            return _NullSpan()
        return PerformanceSpan(
            self,
            event,
            operation,
            page=page,
            route=route,
            rows=rows,
        )

    def should_log_span(
        self,
        event: str,
        duration_ms: float,
        exc: BaseException | None,
    ) -> bool:
        if exc is not None or self.config.log_all_spans:
            return True
        if event == "page_build":
            return True
        if event == "query_timing":
            return duration_ms >= self.config.slow_query_ms
        return False

    def emit(self, event: str, **fields: Any) -> None:
        if not self.config.enabled or event not in _ALLOWED_EVENTS:
            return
        safe_fields: dict[str, Any] = {}
        for key, value in fields.items():
            if key not in _ALLOWED_FIELDS or _SENSITIVE_KEY.search(key):
                continue
            if value is None:
                continue
            if key in {"error", "exception_class", "operation", "page", "route"}:
                value = _sanitize_text(value)
            safe_fields[key] = value
        event_data = {
            "schema_version": SCHEMA_VERSION,
            "ts": _utc_now(),
            "event": event,
            **safe_fields,
            "process_id": os.getpid(),
            "process_instance_id": self.process_instance_id,
            "thread_id": threading.get_ident(),
        }
        try:
            self._queue.put_nowait(event_data)
        except queue.Full:
            with self._dropped_lock:
                self._dropped_events += 1

    def _overflow_event(self, dropped_events: int) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "ts": _utc_now(),
            "event": "event_queue_overflow",
            "dropped_events": dropped_events,
            "process_id": os.getpid(),
            "process_instance_id": self.process_instance_id,
            "thread_id": threading.get_ident(),
        }

    def _take_dropped_events(self) -> int:
        with self._dropped_lock:
            dropped = self._dropped_events
            self._dropped_events = 0
            return dropped

    def _writer_loop(self) -> None:
        try:
            self.config.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.config.log_path.open("a", encoding="utf-8") as stream:
                last_flush = time.monotonic()
                while True:
                    try:
                        item = self._queue.get(timeout=0.5)
                    except queue.Empty:
                        stream.flush()
                        last_flush = time.monotonic()
                        continue
                    try:
                        dropped = self._take_dropped_events()
                        if dropped:
                            stream.write(
                                json.dumps(
                                    self._overflow_event(dropped),
                                    ensure_ascii=False,
                                    separators=(",", ":"),
                                )
                                + "\n"
                            )
                        if item is _STOP:
                            stream.flush()
                            return
                        stream.write(
                            json.dumps(
                                item,
                                ensure_ascii=False,
                                separators=(",", ":"),
                            )
                            + "\n"
                        )
                        if (
                            self._queue.empty()
                            or time.monotonic() - last_flush >= 1
                        ):
                            stream.flush()
                            last_flush = time.monotonic()
                    finally:
                        self._queue.task_done()
        except Exception:
            # Instrumentation failures must never affect application behavior.
            while True:
                try:
                    item = self._queue.get_nowait()
                except queue.Empty:
                    return
                else:
                    self._queue.task_done()
                    if item is _STOP:
                        return

    def start_writer(self) -> None:
        if not self.config.enabled or self._writer_thread is not None:
            return
        self._writer_thread = threading.Thread(
            target=self._writer_loop,
            name="performance-jsonl-writer",
            daemon=True,
        )
        self._writer_thread.start()

    async def start(self) -> None:
        if not self.config.enabled or self._started:
            return
        self._started = True
        self.start_writer()
        self.emit("process_start", success=True)
        await self.start_lag_monitor()

    async def stop(self) -> None:
        if not self.config.enabled or not self._started:
            return
        await self.stop_lag_monitor()
        self.emit("process_stop", success=True)
        if self._writer_thread is not None:
            try:
                self._queue.put(_STOP, timeout=1)
                await asyncio.to_thread(self._writer_thread.join, 5)
            except Exception:
                pass
        self._started = False

    async def start_lag_monitor(self) -> None:
        if not self.config.enabled or self.monitor_running:
            return
        self._monitor_stop = asyncio.Event()
        self._monitor_task = asyncio.create_task(
            self._lag_monitor(),
            name="performance-event-loop-lag",
        )

    async def stop_lag_monitor(self) -> None:
        if self._monitor_task is None:
            return
        if self._monitor_stop is not None:
            self._monitor_stop.set()
        self._monitor_task.cancel()
        try:
            await self._monitor_task
        except asyncio.CancelledError:
            pass
        self._monitor_task = None
        self._monitor_stop = None

    async def _lag_monitor(self) -> None:
        interval = self.config.event_loop_interval_ms / 1000
        expected = time.perf_counter() + interval
        while self._monitor_stop is not None and not self._monitor_stop.is_set():
            await asyncio.sleep(max(0, expected - time.perf_counter()))
            actual = time.perf_counter()
            lag_ms = max(0.0, (actual - expected) * 1000)
            if lag_ms >= self.config.event_loop_lag_ms:
                request_id, page, route = self.lag_page_context(actual, lag_ms)
                self.emit(
                    "event_loop_lag",
                    lag_ms=round(lag_ms, 3),
                    interval_ms=self.config.event_loop_interval_ms,
                    request_id=request_id,
                    page=page,
                    route=route,
                    success=True,
                )
            expected += interval
            if actual - expected >= interval:
                missed_intervals = int((actual - expected) // interval)
                expected += missed_intervals * interval


_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_service = PerformanceService(PerformanceConfig.from_env(_PROJECT_ROOT))


def configure(project_root: Path) -> PerformanceService:
    global _service
    _service = PerformanceService(PerformanceConfig.from_env(project_root))
    return _service


def get_service() -> PerformanceService:
    return _service


def span(
    event: str,
    operation: str,
    *,
    page: str | None = None,
    route: str | None = None,
    rows: int | None = None,
) -> PerformanceSpan | _NullSpan:
    return _service.span(
        event,
        operation,
        page=page,
        route=route,
        rows=rows,
    )


def page_build(page: str, route: str) -> Callable:
    def decorator(func: Callable) -> Callable:
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapped(*args: Any, **kwargs: Any) -> Any:
                with span(
                    "page_build",
                    f"{page}_page_build",
                    page=page,
                    route=route,
                ):
                    return await func(*args, **kwargs)

            return async_wrapped

        @functools.wraps(func)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            with span(
                "page_build",
                f"{page}_page_build",
                page=page,
                route=route,
            ):
                return func(*args, **kwargs)

        return wrapped

    return decorator


def record_exception(exc: BaseException, *, operation: str) -> None:
    if not _service.config.enabled:
        return
    _service.emit(
        "uncaught_exception",
        operation=operation,
        request_id=_REQUEST_ID.get(),
        page=_PAGE.get(),
        route=_ROUTE.get(),
        success=False,
        **_sanitize_error(exc),
    )
