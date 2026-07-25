import asyncio
import contextvars
from collections.abc import Callable, Mapping
from typing import Any, TypeVar

import pandas as pd
from nicegui import run
from sqlalchemy import text
from sqlalchemy.engine import Engine

from src.app.services.performance import span


Result = TypeVar("Result")


def _run_with_context(
    context: contextvars.Context,
    callback: Callable[..., Result],
    *args: Any,
) -> tuple[Result]:
    return (context.run(callback, *args),)


async def _io_bound(
    callback: Callable[..., Result],
    *args: Any,
) -> Result:
    outcome = await run.io_bound(
        _run_with_context,
        contextvars.copy_context(),
        callback,
        *args,
    )
    if outcome is None:
        raise asyncio.CancelledError
    return outcome[0]


def _read_dataframe(
    engine: Engine,
    statement: str,
    params: Mapping[str, Any] | None,
    operation: str,
) -> pd.DataFrame:
    with span("query_timing", operation) as query_span:
        with engine.connect() as connection:
            result = pd.read_sql(text(statement), connection, params=params)
        query_span.set_rows(len(result))
        return result


async def read_dataframe(
    engine: Engine,
    statement: str,
    *,
    operation: str,
    params: Mapping[str, Any] | None = None,
) -> pd.DataFrame:
    return await _io_bound(
        _read_dataframe,
        engine,
        statement,
        params,
        operation,
    )


def _read_scalar(engine: Engine, statement: str, operation: str) -> Any:
    with span("query_timing", operation, rows=1):
        with engine.connect() as connection:
            return connection.execute(text(statement)).scalar()


async def read_scalar(
    engine: Engine,
    statement: str,
    *,
    operation: str,
) -> Any:
    return await _io_bound(
        _read_scalar,
        engine,
        statement,
        operation,
    )
