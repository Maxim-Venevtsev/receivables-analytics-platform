import ast
import asyncio
from pathlib import Path

import pytest

from src.app.services.settings import (
    DEFAULT_PAGE_RESPONSE_TIMEOUT_SECONDS,
    get_page_response_timeout,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAIN = PROJECT_ROOT / "src/app/main.py"
EXECUTIVE = PROJECT_ROOT / "src/app/pages/executive.py"


def page_decorator(path: Path, function_name: str) -> ast.Call:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == function_name
    )
    return next(
        decorator
        for decorator in function.decorator_list
        if isinstance(decorator, ast.Call)
        and isinstance(decorator.func, ast.Attribute)
        and decorator.func.attr == "page"
    )


def test_default_exceeds_nicegui_default_and_equals_project_default() -> None:
    assert DEFAULT_PAGE_RESPONSE_TIMEOUT_SECONDS == 30.0
    assert get_page_response_timeout({}) == 30.0
    assert get_page_response_timeout({}) > 3.0


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("0.25", 0.25),
        ("12", 12.0),
        ("30.5", 30.5),
    ],
)
def test_environment_override_is_parsed(raw: str, expected: float) -> None:
    assert get_page_response_timeout(
        {"APP_PAGE_RESPONSE_TIMEOUT_SECONDS": raw}
    ) == expected


@pytest.mark.parametrize(
    "raw",
    ["", "invalid", "0", "-1", "nan", "NaN", "inf", "-inf"],
)
def test_invalid_timeout_fails_clearly(raw: str) -> None:
    with pytest.raises(
        ValueError,
        match="APP_PAGE_RESPONSE_TIMEOUT_SECONDS must be a positive finite number",
    ):
        get_page_response_timeout({"APP_PAGE_RESPONSE_TIMEOUT_SECONDS": raw})


@pytest.mark.parametrize(
    ("path", "function_name"),
    [
        (MAIN, "dashboard"),
        (EXECUTIVE, "executive_overview_page"),
    ],
)
def test_slow_async_pages_receive_configured_response_timeout(
    path: Path,
    function_name: str,
) -> None:
    decorator = page_decorator(path, function_name)
    response_timeout = next(
        keyword.value
        for keyword in decorator.keywords
        if keyword.arg == "response_timeout"
    )
    assert isinstance(response_timeout, ast.Call)
    assert isinstance(response_timeout.func, ast.Name)
    assert response_timeout.func.id == "get_page_response_timeout"
    assert not any(
        keyword.arg == "reconnect_timeout"
        for keyword in decorator.keywords
    )


def test_synthetic_page_exceeds_old_default_ratio_without_cancellation() -> None:
    completed = False

    async def page_builder() -> str:
        nonlocal completed
        await asyncio.sleep(0.08)
        completed = True
        return "unchanged-output"

    async def scenario() -> str:
        configured_timeout = 0.2
        old_default_ratio = 0.03
        task = asyncio.create_task(page_builder())
        await asyncio.sleep(old_default_ratio)
        assert not task.done()
        return await asyncio.wait_for(task, timeout=configured_timeout)

    assert asyncio.run(scenario()) == "unchanged-output"
    assert completed


def test_configured_timeout_cancels_safely_once() -> None:
    starts = 0
    cancelled = 0

    async def page_builder() -> None:
        nonlocal starts, cancelled
        starts += 1
        try:
            await asyncio.sleep(1)
        except asyncio.CancelledError:
            cancelled += 1
            raise

    async def scenario() -> None:
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(page_builder(), timeout=0.03)

    asyncio.run(scenario())
    assert starts == 1
    assert cancelled == 1


def test_no_global_reconnect_or_heartbeat_setting_was_added() -> None:
    source = MAIN.read_text(encoding="utf-8")
    run_call = next(
        node
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "run"
    )
    keyword_names = {keyword.arg for keyword in run_call.keywords}
    assert "reconnect_timeout" not in keyword_names
    assert "ping_timeout" not in keyword_names
    assert "ping_interval" not in keyword_names
