import ast
import subprocess
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PAGES = PROJECT_ROOT / "src/app/pages"

DATABASE_PAGES = {
    "deltas.py": ["deltas_page"],
    "executive_overdue.py": ["executive_overdue_page"],
    "branch_card.py": ["branch_card_page"],
    "client_card.py": ["client_card_page"],
    "parent_org_card.py": ["parent_org_card_page"],
    "overdue.py": ["overdue_page"],
    "forecast.py": ["due_today_page", "due_soon_page"],
    "payment_attention.py": ["payment_attention_page"],
    "term_shifts.py": ["term_shifts_page"],
    "executive_long_green.py": ["executive_long_green_page"],
    "executive_hidden_risk.py": ["executive_hidden_risk_page"],
    "executive_branches.py": ["executive_branches_page"],
    "executive_term_shifts.py": ["executive_term_shifts_page"],
    "executive_rating_migration.py": ["executive_rating_migration_page"],
}

PRIMARY_OPERATION_ORDER = {
    "deltas.py": [
        "deltas_snapshot_info",
        "deltas_kpi",
        "deltas_client_summary",
        "deltas_branch_summary",
        "deltas_term_shifts",
        "deltas_new_overdue",
    ],
    "executive_overdue.py": ["executive_overdue_clients"],
    "branch_card.py": [
        "branch_card_invoices",
        "branch_card_paid_invoices",
        "branch_card_history",
        "branch_card_rating",
        "branch_card_rating_migration",
        "branch_card_credit_quality_clients",
        "branch_card_credit_quality_exposure",
        "branch_card_clients",
    ],
    "parent_org_card.py": [
        "parent_org_card_invoices",
        "parent_org_card_paid_invoices",
        "parent_org_card_history",
        "parent_org_card_rating_migration",
        "parent_org_card_credit_quality",
        "parent_org_card_clients",
    ],
}


def parse_page(filename: str) -> ast.Module:
    return ast.parse((PAGES / filename).read_text(encoding="utf-8"))


def call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


@pytest.mark.parametrize(
    ("filename", "function_name"),
    [
        (filename, function_name)
        for filename, functions in DATABASE_PAGES.items()
        for function_name in functions
    ],
)
def test_database_page_is_async_instrumented_and_uses_project_timeout(
    filename: str,
    function_name: str,
) -> None:
    tree = parse_page(filename)
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == function_name
    )
    decorators = [
        node for node in function.decorator_list if isinstance(node, ast.Call)
    ]
    ui_page = next(node for node in decorators if call_name(node) == "page")
    page_span = next(node for node in decorators if call_name(node) == "page_build")
    timeout = next(
        keyword.value
        for keyword in ui_page.keywords
        if keyword.arg == "response_timeout"
    )

    assert isinstance(timeout, ast.Call)
    assert call_name(timeout) == "get_page_response_timeout"
    assert not any(
        keyword.arg in {"reconnect_timeout", "ping_timeout", "ping_interval"}
        for keyword in ui_page.keywords
    )
    assert len(page_span.args) == 2
    assert all(isinstance(arg, ast.Constant) for arg in page_span.args)
    assert all(
        not any(character in str(arg.value) for character in ("?", "&", "="))
        for arg in page_span.args
    )


@pytest.mark.parametrize("filename", DATABASE_PAGES)
def test_page_query_helper_delegates_to_shared_offload(filename: str) -> None:
    source = (PAGES / filename).read_text(encoding="utf-8")
    assert "from src.app.services.database import read_dataframe" in source
    assert "return await read_dataframe(" in source
    assert "pd.read_sql" not in source
    assert "engine.connect" not in source
    assert "ThreadPoolExecutor" not in source
    assert "asyncio.gather" not in source


@pytest.mark.parametrize("filename", DATABASE_PAGES)
def test_all_page_database_calls_are_awaited(filename: str) -> None:
    tree = parse_page(filename)
    parents = {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }
    database_calls = {
        "query_df",
        "query_optional_df",
        "get_historical_client_identity",
        "load_forecast_data",
        "load_summary",
        "load_clients",
    }
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or call_name(node) not in database_calls:
            continue
        current: ast.AST = node
        while current in parents and not isinstance(current, ast.Await):
            current = parents[current]
        is_async_return = (
            isinstance(parents.get(node), ast.Return)
            and isinstance(parents.get(parents[node]), ast.AsyncFunctionDef)
        )
        assert isinstance(current, ast.Await) or is_async_return, (
            filename,
            node.lineno,
            call_name(node),
        )


@pytest.mark.parametrize(
    ("filename", "expected"),
    PRIMARY_OPERATION_ORDER.items(),
)
def test_primary_page_query_order_is_explicit_and_sequential(
    filename: str,
    expected: list[str],
) -> None:
    tree = parse_page(filename)
    operations = sorted(
        (
            node.lineno,
            keyword.value.value,
        )
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        for keyword in node.keywords
        if keyword.arg == "operation"
        and isinstance(keyword.value, ast.Constant)
        and isinstance(keyword.value.value, str)
        and keyword.value.value in expected
    )
    assert [operation for _, operation in operations] == expected


def query_arguments(source: str) -> list[tuple[str, ...]]:
    tree = ast.parse(source)
    calls = sorted(
        (
            node.lineno,
            tuple(
                ast.dump(argument, include_attributes=False)
                for argument in node.args
            ),
        )
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and call_name(node) == "query_df"
    )
    return [arguments for _, arguments in calls]


@pytest.mark.parametrize("filename", DATABASE_PAGES)
def test_sql_and_positional_parameters_match_repository_baseline(
    filename: str,
) -> None:
    relative = f"src/app/pages/{filename}"
    baseline = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={PROJECT_ROOT.as_posix()}",
            "show",
            f"HEAD:{relative}",
        ],
        cwd=PROJECT_ROOT,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=True,
    ).stdout
    current = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
    assert query_arguments(current) == query_arguments(baseline)


def test_no_direct_database_io_remains_outside_shared_service() -> None:
    offenders: list[str] = []
    for path in (PROJECT_ROOT / "src/app").rglob("*.py"):
        if path.name == "database.py":
            continue
        source = path.read_text(encoding="utf-8")
        if "pd.read_sql" in source or "engine.connect" in source:
            offenders.append(str(path.relative_to(PROJECT_ROOT)))
    assert offenders == []
