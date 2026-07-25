from pathlib import Path
import os
from urllib.parse import quote

import pandas as pd
from dotenv import load_dotenv
from nicegui import ui
from sqlalchemy import create_engine

from src.app.components.navigation import top_navigation
from src.app.services.database import read_dataframe
from src.app.services.performance import page_build
from src.app.services.settings import get_page_response_timeout
from src.app.components.clients_table import render_clients_table
from src.app.components.branch_table import render_branch_table


PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env")

engine = create_engine(
    f"postgresql+psycopg2://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@"
    f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)


OVERDUE_CLIENT_COLUMNS = [
    "client_group",
    "client",
    "rating",
    "total_debt",
    "overdue_debt",
    "overdue_share_pct",
    "debt_45_plus",
    "debt_60_plus",
    "debt_90_plus",
    "debt_120_plus",
    "max_days_overdue",
]


OVERDUE_BRANCH_COLUMNS = [
    "client_group",
    "rating",
    "total_debt",
    "overdue_debt",
    "overdue_share_pct",
    "debt_45_plus",
    "debt_60_plus",
    "debt_90_plus",
    "debt_120_plus",
    "max_days_overdue",
]


async def query_df(sql: str, *, operation: str) -> pd.DataFrame:
    return await read_dataframe(engine, sql, operation=operation)


def money(value) -> str:
    if pd.isna(value):
        return "0"
    return f"{float(value):,.0f}".replace(",", " ")


def percent(value) -> str:
    if pd.isna(value):
        return "0%"
    return f"{float(value):.1f}%"


def compact_kpi(
    title: str,
    value: str,
    subtitle: str = "",
    color_class: str = "text-gray-900",
):
    value_label = None
    subtitle_label = None

    with ui.card().classes("w-64 h-36 p-4"):
        with ui.column().classes("w-full h-full items-center justify-between text-center"):
            ui.label(title).classes("text-sm text-gray-500 h-6 flex items-center justify-center")
            value_label = ui.label(value).classes(
                f"text-2xl font-bold h-10 flex items-center justify-center {color_class}"
            )
            subtitle_label = ui.label(subtitle).classes(
                "text-sm text-gray-500 h-8 flex items-center justify-center"
            )

    return value_label, subtitle_label


def normalize_numeric_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    result = df.copy()

    for col in columns:
        if col not in result.columns:
            result[col] = 0

        result[col] = pd.to_numeric(
            result[col],
            errors="coerce",
        ).fillna(0)

    return result


@ui.page("/overdue", response_timeout=get_page_response_timeout())
@page_build("overdue", "/overdue")
async def overdue_page():
    ui.label("Просроченная дебиторка").classes("text-3xl font-bold mb-2")
    ui.label(
        "Клиенты и филиалы с просроченной задолженностью. "
        "Отдельно выделены долги 45+, 60+, 90+ и 120+ дней."
    ).classes("text-gray-500 mb-4")

    top_navigation()

    clients = await query_df("""
        SELECT *
        FROM core.v_client_operational_summary
        WHERE overdue_debt > 0
        ORDER BY
            overdue_debt DESC,
            max_days_overdue DESC,
            total_debt DESC
    """, operation="overdue_clients")

    if clients.empty:
        ui.label("Просроченной задолженности нет.").classes("text-lg text-green-700")
        return

    branches = await query_df("""
        WITH branch_debt AS (
            SELECT
                client_group,

                SUM(total_debt) AS total_debt,

                SUM(
                    CASE
                        WHEN overdue_debt > 0
                        THEN overdue_debt
                        ELSE 0
                    END
                ) AS overdue_debt,

                SUM(
                    CASE
                        WHEN overdue_debt > 0
                        THEN debt_45_plus
                        ELSE 0
                    END
                ) AS debt_45_plus,

                SUM(
                    CASE
                        WHEN overdue_debt > 0
                        THEN debt_60_plus
                        ELSE 0
                    END
                ) AS debt_60_plus,

                SUM(
                    CASE
                        WHEN overdue_debt > 0
                        THEN debt_90_plus
                        ELSE 0
                    END
                ) AS debt_90_plus,

                SUM(
                    CASE
                        WHEN overdue_debt > 0
                        THEN debt_120_plus
                        ELSE 0
                    END
                ) AS debt_120_plus,

                MAX(
                    CASE
                        WHEN overdue_debt > 0
                        THEN max_days_overdue
                        ELSE 0
                    END
                ) AS max_days_overdue

            FROM core.v_client_operational_summary

            GROUP BY client_group
        )

        SELECT
            b.client_group,
            bh.weighted_rating,

            b.total_debt,
            b.overdue_debt,
            b.debt_45_plus,
            b.debt_60_plus,
            b.debt_90_plus,
            b.debt_120_plus,
            b.max_days_overdue,

            ROUND(b.overdue_debt / NULLIF(b.total_debt, 0) * 100, 2) AS overdue_share_pct

        FROM branch_debt b

        LEFT JOIN core.v_executive_branch_health bh
            ON b.client_group = bh.client_group

        WHERE b.overdue_debt > 0

        ORDER BY
            b.overdue_debt DESC,
            b.debt_90_plus DESC,
            b.debt_120_plus DESC,
            b.max_days_overdue DESC,
            b.total_debt DESC
    """, operation="overdue_branches")

    numeric_cols = [
        "total_debt",
        "overdue_debt",
        "overdue_share_pct",
        "debt_45_plus",
        "debt_60_plus",
        "debt_90_plus",
        "debt_120_plus",
        "max_days_overdue",
        "weighted_rating",
        "stars",
    ]

    clients = normalize_numeric_columns(clients, numeric_cols)
    branches = normalize_numeric_columns(branches, numeric_cols)

    branches = branches[branches["total_debt"] >= 1].copy()

    selected_branches: list[str] = []

    def filtered_clients() -> pd.DataFrame:
        result = clients.copy()

        if selected_branches:
            result = result[result["client_group"].isin(selected_branches)]

        sort_cols = [
            col for col in [
                "overdue_debt",
                "debt_90_plus",
                "debt_120_plus",
                "max_days_overdue",
                "total_debt",
            ]
            if col in result.columns
        ]

        if sort_cols:
            result = result.sort_values(
                by=sort_cols,
                ascending=[False] * len(sort_cols),
            )

        return result

    def filtered_branches() -> pd.DataFrame:
        return branches.sort_values(
            by=[
                "overdue_debt",
                "debt_90_plus",
                "debt_120_plus",
                "max_days_overdue",
                "total_debt",
            ],
            ascending=[False, False, False, False, False],
        )

    def get_kpi_metrics() -> dict[str, float | int]:
        branch_df = branches.copy()
        client_df = clients.copy()

        if selected_branches:
            branch_df = branch_df[branch_df["client_group"].isin(selected_branches)]
            client_df = client_df[client_df["client_group"].isin(selected_branches)]

        total_debt = float(branch_df["total_debt"].sum())
        overdue_debt = float(branch_df["overdue_debt"].sum())
        debt_90_plus = float(branch_df["debt_90_plus"].sum())
        debt_120_plus = float(branch_df["debt_120_plus"].sum())

        max_days = (
            int(client_df["max_days_overdue"].max())
            if not client_df.empty
            else 0
        )

        return {
            "total_debt": total_debt,
            "overdue_debt": overdue_debt,
            "overdue_clients": int(client_df["client_id"].nunique()) if not client_df.empty else 0,
            "overdue_share_pct": overdue_debt / total_debt * 100 if total_debt else 0,
            "max_days": max_days,
            "debt_90_plus": debt_90_plus,
            "debt_90_share_pct": debt_90_plus / total_debt * 100 if total_debt else 0,
            "debt_120_plus": debt_120_plus,
            "debt_120_share_pct": debt_120_plus / total_debt * 100 if total_debt else 0,
        }

    initial_kpi = get_kpi_metrics()

    with ui.row().classes("gap-4 mb-6"):
        overdue_label, overdue_subtitle = compact_kpi(
            "Просрочено",
            money(initial_kpi["overdue_debt"]),
            f"{percent(initial_kpi['overdue_share_pct'])} портфеля",
            "text-red-700",
        )

        overdue_clients_label, overdue_clients_subtitle = compact_kpi(
            "Клиентов с просрочкой",
            str(initial_kpi["overdue_clients"]),
        )

        max_days_label, max_days_subtitle = compact_kpi(
            "Макс. дней просрочки",
            str(initial_kpi["max_days"]),
        )

        debt_90_label, debt_90_subtitle = compact_kpi(
            "90+ просрочено",
            money(initial_kpi["debt_90_plus"]),
            f"{percent(initial_kpi['debt_90_share_pct'])} портфеля",
            "text-red-700",
        )

        debt_120_label, debt_120_subtitle = compact_kpi(
            "120+ просрочено",
            money(initial_kpi["debt_120_plus"]),
            f"{percent(initial_kpi['debt_120_share_pct'])} портфеля",
            "text-red-700",
        )

    with ui.row().classes("items-center gap-4 mb-2"):
        selected_branch_label = ui.label("Показаны все филиалы").classes("text-sm text-gray-500")
        reset_branch_button = ui.button("ВСЕ ФИЛИАЛЫ").props("flat color=primary")

    branch_table = render_branch_table(
        branches=filtered_branches(),
        title="Сводка по филиалам",
        subtitle=(
            "Агрегация просроченной задолженности по филиалам. "
            "Нажатие на филиал ограничивает клиентскую таблицу выбранным филиалом."
        ),
        mode="operational",
        selected_branches=selected_branches,
        rows_per_page=20,
        visible_columns=OVERDUE_BRANCH_COLUMNS,
    )

    client_table = render_clients_table(
        clients=filtered_clients(),
        title="Контрагенты",
        show_branch=True,
        show_search=True,
        from_route="overdue",
        visible_columns=OVERDUE_CLIENT_COLUMNS,
    )

    def update_kpi_cards():
        metrics = get_kpi_metrics()

        overdue_label.text = money(metrics["overdue_debt"])
        overdue_subtitle.text = f"{percent(metrics['overdue_share_pct'])} портфеля"

        overdue_clients_label.text = str(metrics["overdue_clients"])
        overdue_clients_subtitle.text = ""

        max_days_label.text = str(metrics["max_days"])
        max_days_subtitle.text = ""

        debt_90_label.text = money(metrics["debt_90_plus"])
        debt_90_subtitle.text = f"{percent(metrics['debt_90_share_pct'])} портфеля"

        debt_120_label.text = money(metrics["debt_120_plus"])
        debt_120_subtitle.text = f"{percent(metrics['debt_120_share_pct'])} портфеля"

        for label in [
            overdue_label,
            overdue_subtitle,
            overdue_clients_label,
            overdue_clients_subtitle,
            max_days_label,
            max_days_subtitle,
            debt_90_label,
            debt_90_subtitle,
            debt_120_label,
            debt_120_subtitle,
        ]:
            label.update()

    def apply_filters():
        if selected_branches:
            selected_branch_label.text = f"Фильтр: {', '.join(selected_branches)}"
        else:
            selected_branch_label.text = "Показаны все филиалы"

        selected_branch_label.update()

        if branch_table is not None:
            branch_table.refresh_branches(
                filtered_branches(),
                selected_branches=selected_branches,
            )

        if client_table is not None:
            client_table.refresh_clients(filtered_clients())

        update_kpi_cards()

    def toggle_branch(event):
        branch = event.args

        if branch in selected_branches:
            selected_branches.remove(branch)
        else:
            selected_branches.append(branch)

        apply_filters()

    def reset_branch_filter():
        selected_branches.clear()
        apply_filters()

    def open_branch_card(event):
        branch = event.args

        if branch:
            ui.navigate.to(f"/branch/{quote(str(branch))}?from=/overdue")

    def open_client(event):
        ui.navigate.to(f"/client/{event.args}?from=overdue")

    def open_branch_from_client_table(event):
        ui.navigate.to(f"/branch/{quote(str(event.args))}?from=/overdue")

    if branch_table is not None:
        branch_table.on("branch_click", toggle_branch)
        branch_table.on("branch_open", open_branch_card)

    if client_table is not None:
        client_table.on("client_click", open_client)
        client_table.on("branch_click", open_branch_from_client_table)

    reset_branch_button.on_click(reset_branch_filter)
