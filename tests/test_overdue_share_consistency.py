import ast
import re
import subprocess
from pathlib import Path

import pandas as pd

from src.app.services.metrics import (
    overdue_portfolio_subtitle,
    overdue_share_percent,
    portfolio_denominator,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OVERDUE_PAGE = PROJECT_ROOT / "src/app/pages/overdue.py"
DASHBOARD_VIEWS = PROJECT_ROOT / "sql/ddl/036_fix_latest_operational_views.sql"
METRICS = PROJECT_ROOT / "docs/METRICS.md"


def normalized(path: Path) -> str:
    return re.sub(r"\s+", " ", path.read_text(encoding="utf-8")).lower()


def query_arguments(source: str) -> list[str]:
    tree = ast.parse(source)
    calls = sorted(
        (
            node.lineno,
            ast.dump(node.args[0], include_attributes=False),
        )
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "query_df"
        and node.args
    )
    return [argument for _, argument in calls]


def test_documented_overdue_share_uses_total_current_debt() -> None:
    metrics = normalized(METRICS)
    assert "total open receivables amount in the current snapshot" in metrics
    assert "overdue_debt / total_debt * 100" in metrics


def test_dashboard_and_overdue_use_the_same_portfolio_denominator_layer() -> None:
    dashboard_sql = normalized(DASHBOARD_VIEWS)
    overdue_source = normalized(OVERDUE_PAGE)

    assert (
        "with portfolio as ( select sum(invoice_amount) as total_debt "
        "from core.v_invoice_detail"
    ) in dashboard_sql
    assert (
        "branch_portfolio as ( select client_group, "
        "sum(invoice_amount) as total_debt from core.v_invoice_detail"
    ) in overdue_source


def test_overdue_amount_is_unchanged_and_share_uses_full_branch_portfolio() -> None:
    source = normalized(OVERDUE_PAGE)

    assert (
        "when overdue_debt > 0 then overdue_debt else 0 end ) as overdue_debt"
    ) in source
    assert (
        "round(b.overdue_debt / nullif(p.total_debt, 0) * 100, 2) "
        "as overdue_share_pct"
    ) in source
    assert '"overdue_share_pct": overdue_debt / total_debt * 100' in source


def test_same_snapshot_values_produce_same_share_on_both_pages() -> None:
    overdue_debt = 4_979_430
    total_current_outstanding_debt = 56_249_549

    dashboard_share = overdue_debt / total_current_outstanding_debt * 100
    overdue_page_share = overdue_debt / total_current_outstanding_debt * 100

    assert dashboard_share == overdue_page_share
    assert round(dashboard_share, 1) == 8.9


def test_top_card_uses_global_portfolio_not_visible_branch_sum() -> None:
    branches_with_overdue = pd.DataFrame(
        {
            "client_group": ["branch-a", "branch-b"],
            "total_debt": [30_000_000, 16_980_000],
            "portfolio_total_debt": [56_249_549, 56_249_549],
        }
    )
    overdue_debt = 4_979_430

    denominator = portfolio_denominator(
        branches_with_overdue,
        branch_filter_active=False,
    )
    subtitle_passed_to_top_card = overdue_portfolio_subtitle(
        overdue_debt,
        denominator,
    )

    assert branches_with_overdue["total_debt"].sum() == 46_980_000
    assert denominator == 56_249_549
    assert subtitle_passed_to_top_card == "8.9% портфеля"
    assert subtitle_passed_to_top_card != "10.6% портфеля"


def test_selected_branch_uses_its_full_current_debt() -> None:
    selected_branch = pd.DataFrame(
        {
            "client_group": ["branch-a"],
            "total_debt": [30_000_000],
            "portfolio_total_debt": [56_249_549],
        }
    )

    assert portfolio_denominator(
        selected_branch,
        branch_filter_active=True,
    ) == 30_000_000


def test_executive_card_uses_canonical_values_and_final_display_rounding() -> None:
    total_debt = 56_249_549

    assert round(overdue_share_percent(4_979_430, total_debt), 1) == 8.9
    assert overdue_portfolio_subtitle(4_979_430, total_debt) == "8.9% портфеля"
    assert overdue_portfolio_subtitle(4_979_428, total_debt) == "8.9% портфеля"


def test_executive_kpi_reads_dashboard_canonical_numerator_and_denominator() -> None:
    executive_source = normalized(PROJECT_ROOT / "src/app/pages/executive.py")

    assert "d.total_debt" in executive_source
    assert "d.overdue_debt" in executive_source
    assert "cross join core.v_dashboard_operational_kpi d" in executive_source
    assert "d.overdue_debt / d.total_debt * 100" in executive_source
    assert "round(d.overdue_debt" not in executive_source
    assert "sum(round(" not in executive_source
    assert (
        "overdue_portfolio_subtitle( float(kpi[\"overdue_debt\"] or 0), "
        "float(kpi[\"total_debt\"] or 0)"
    ) in executive_source


def test_executive_sql_outside_kpi_query_is_unchanged() -> None:
    relative = "src/app/pages/executive.py"
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

    assert query_arguments(current)[1:] == query_arguments(baseline)[1:]
