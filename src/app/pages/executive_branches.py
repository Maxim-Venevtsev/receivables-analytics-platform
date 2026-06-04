from pathlib import Path
import os
from urllib.parse import quote

import pandas as pd
from dotenv import load_dotenv
from nicegui import ui
from sqlalchemy import create_engine, text

from src.app.components.navigation import top_navigation
from src.app.components.kpi_cards import money, percent
from src.app.components.rating_stars import rating_aggrid_cell_renderer


PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env")

engine = create_engine(
    f"postgresql+psycopg2://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@"
    f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)


def query_df(sql: str, params: dict | None = None) -> pd.DataFrame:
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn, params=params)


def compact_kpi(title: str, value: str, subtitle: str = ""):
    with ui.card().classes("w-60 h-32 p-4"):
        with ui.column().classes("w-full h-full items-center justify-between text-center"):
            ui.label(title).classes("text-sm text-gray-500 h-6 flex items-center justify-center")
            ui.label(value).classes("text-2xl font-bold h-10 flex items-center justify-center")
            ui.label(subtitle).classes("text-sm text-gray-500 h-8 flex items-center justify-center")


@ui.page("/executive/branches")
def executive_branches_page():
    ui.label("Состояние филиалов").classes("text-3xl font-bold mb-2")
    ui.label(
        "Сравнение филиалов по просрочке, длинной непросроченной задолженности и рейтингу портфеля"
    ).classes("text-gray-500 mb-4")

    top_navigation()

    ui.button(
        "← Вернуться к Сводке",
        on_click=lambda: ui.navigate.to("/executive"),
    ).props("flat color=primary").classes("mb-4")

    branch_health = query_df("""
        SELECT *
        FROM core.v_executive_branch_health
        ORDER BY overdue_share_pct DESC, green_90_plus_share_pct DESC
    """)

    long_green_by_branch = query_df("""
        SELECT
            client_group,
            SUM(green_45_plus_debt) AS green_45_plus_debt,
            SUM(green_60_plus_debt) AS green_60_plus_debt,
            SUM(green_90_plus_debt) AS green_90_plus_debt_calc,
            SUM(green_120_plus_debt) AS green_120_plus_debt
        FROM core.v_executive_long_green_clients
        GROUP BY client_group
    """)

    if branch_health.empty:
        ui.label("Нет данных по филиалам.").classes("text-green-700 text-lg")
        return

    df = branch_health.merge(
        long_green_by_branch,
        on="client_group",
        how="left",
    )

    df["weighted_rating_stars"] = (
        df["weighted_rating"]
        .round()
        .fillna(0)
        .astype(int)
    )

    for col in [
        "green_45_plus_debt",
        "green_60_plus_debt",
        "green_90_plus_debt_calc",
        "green_120_plus_debt",
    ]:
        df[col] = df[col].fillna(0)

    if "green_90_plus_debt" not in df.columns:
        df["green_90_plus_debt"] = df["green_90_plus_debt_calc"]

    total_debt = float(df["total_debt"].sum())
    overdue_debt = float(df["overdue_debt"].sum())
    branch_count = int(df["client_group"].nunique())
    branches_with_90 = int((df["green_90_plus_debt"] > 0).sum())
    branches_with_120 = int((df["green_120_plus_debt"] > 0).sum())

    worst_overdue = df.sort_values("overdue_share_pct", ascending=False).iloc[0]
    worst_long = df.sort_values("green_120_plus_debt", ascending=False).iloc[0]

    with ui.row().classes("gap-4 mb-6"):
        compact_kpi("Филиалов", str(branch_count))
        compact_kpi("Общий долг", money(total_debt))
        compact_kpi("Просрочено", money(overdue_debt), percent(overdue_debt / total_debt * 100 if total_debt else 0))
        compact_kpi("Филиалов с 90+", str(branches_with_90))
        compact_kpi("Филиалов с 120+", str(branches_with_120))
        compact_kpi(
            "Худший % просрочки",
            percent(worst_overdue["overdue_share_pct"]),
            str(worst_overdue["client_group"]),
        )
        compact_kpi(
            "Худший 120+",
            money(worst_long["green_120_plus_debt"]),
            str(worst_long["client_group"]),
        )

    with ui.card().classes("w-full p-4 mb-3"):
        ui.label("Риск-профиль филиалов").classes("text-xl font-bold mb-1")
        ui.label(
            "Абсолютные суммы длинной непросроченной задолженности показывают, где риск начинает концентрироваться."
        ).classes("text-sm text-gray-500")

    grid = ui.aggrid({
        "columnDefs": [
            {
                "headerName": "Филиал",
                "field": "client_group",
                "sortable": True,
                "filter": True,
                "minWidth": 180,
                ":cellRenderer": """
                    params => `
                        <span style="color:#1976d2; cursor:pointer; font-weight:600;">
                            ${params.value}
                        </span>
                    `
                """,
            },
            {
                "headerName": "Общий долг",
                "field": "total_debt",
                "sortable": True,
                "filter": "agNumberColumnFilter",
                "type": "rightAligned",
                "minWidth": 150,
                ":valueFormatter": "params => params.value == null ? '' : Math.round(params.value).toLocaleString('ru-RU')",
            },
            {
                "headerName": "Просрочено",
                "field": "overdue_debt",
                "sortable": True,
                "filter": "agNumberColumnFilter",
                "type": "rightAligned",
                "minWidth": 150,
                ":cellRenderer": """
                    params => {
                        const value = params.value || 0;
                        const color = value > 0 ? '#dc2626' : '#6b7280';
                        return `<span style="color:${color}; font-weight:700;">${Math.round(value).toLocaleString('ru-RU')}</span>`;
                    }
                """,
            },
            {
                "headerName": "% просрочки",
                "field": "overdue_share_pct",
                "sortable": True,
                "filter": "agNumberColumnFilter",
                "type": "rightAligned",
                "minWidth": 150,
                ":cellRenderer": """
                    params => {
                        const value = params.value || 0;
                        const color = value > 20 ? '#dc2626' : value > 10 ? '#f97316' : value > 0 ? '#ca8a04' : '#16a34a';
                        return `<span style="color:${color}; font-weight:700;">${value.toFixed(1)}%</span>`;
                    }
                """,
            },
            {
                "headerName": "45+",
                "field": "green_45_plus_debt",
                "sortable": True,
                "filter": "agNumberColumnFilter",
                "type": "rightAligned",
                "minWidth": 130,
                ":valueFormatter": "params => params.value == null ? '' : Math.round(params.value).toLocaleString('ru-RU')",
            },
            {
                "headerName": "60+",
                "field": "green_60_plus_debt",
                "sortable": True,
                "filter": "agNumberColumnFilter",
                "type": "rightAligned",
                "minWidth": 130,
                ":valueFormatter": "params => params.value == null ? '' : Math.round(params.value).toLocaleString('ru-RU')",
            },
            {
                "headerName": "90+",
                "field": "green_90_plus_debt",
                "sortable": True,
                "filter": "agNumberColumnFilter",
                "type": "rightAligned",
                "minWidth": 130,
                ":cellRenderer": """
                    params => {
                        const value = params.value || 0;
                        const color = value > 0 ? '#dc2626' : '#6b7280';
                        return `<span style="color:${color}; font-weight:700;">${Math.round(value).toLocaleString('ru-RU')}</span>`;
                    }
                """,
            },
            {
                "headerName": "120+",
                "field": "green_120_plus_debt",
                "sortable": True,
                "filter": "agNumberColumnFilter",
                "type": "rightAligned",
                "minWidth": 130,
                ":cellRenderer": """
                    params => {
                        const value = params.value || 0;
                        const color = value > 0 ? '#991b1b' : '#6b7280';
                        return `<span style="color:${color}; font-weight:700;">${Math.round(value).toLocaleString('ru-RU')}</span>`;
                    }
                """,
            },
            {
                "headerName": "Рейтинг",
                "field": "weighted_rating_stars",
                "sortable": True,
                "filter": "agNumberColumnFilter",
                "minWidth": 120,
                "maxWidth": 140,
                ":cellRenderer": rating_aggrid_cell_renderer(),
            },
            {
                "headerName": "Динамика",
                "field": "portfolio_change_label",
                "sortable": True,
                "filter": True,
                "minWidth": 180,
            },
        ],
        "rowData": df.to_dict("records"),
        "defaultColDef": {"resizable": True, "sortable": True, "filter": True},
        "pagination": True,
        "paginationPageSize": 30,
    }).classes("w-full h-[620px] mb-6")

    def open_branch_card_from_grid(event):
        args = event.args or {}
        data = args.get("data") or {}
        col_id = (
            args.get("colId")
            or (args.get("column") or {}).get("colId")
            or (args.get("colDef") or {}).get("field")
        )

        if col_id == "client_group" and data.get("client_group"):
            branch = quote(str(data["client_group"]))
            ui.navigate.to(f"/branch/{branch}?from=/executive/branches")

    grid.on("cellClicked", open_branch_card_from_grid)