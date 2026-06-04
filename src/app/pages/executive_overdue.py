from pathlib import Path
import os

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


def rating_fmt(stars):
    if pd.isna(stars):
        return "—"
    return f"{int(stars)}★"


def compact_kpi(title: str, value: str, subtitle: str = ""):
    with ui.card().classes("w-56 h-32 p-4"):
        with ui.column().classes("w-full h-full items-center justify-between text-center"):
            ui.label(title).classes("text-sm text-gray-500 h-6 flex items-center justify-center")
            ui.label(value).classes("text-2xl font-bold h-10 flex items-center justify-center")
            ui.label(subtitle).classes("text-sm text-gray-500 h-8 flex items-center justify-center")


@ui.page("/executive/overdue")
def executive_overdue_page():
    ui.label("Просроченная задолженность").classes("text-3xl font-bold mb-2")
    ui.label(
        "Клиенты, формирующие текущую просрочку по портфелю дебиторской задолженности"
    ).classes("text-gray-500 mb-4")

    top_navigation()

    ui.button(
        "← Вернуться к Сводке",
        on_click=lambda: ui.navigate.to("/executive"),
    ).props("flat color=primary").classes("mb-4")

    overdue_clients = query_df("""
        SELECT *
        FROM core.v_executive_overdue_clients
        ORDER BY overdue_debt DESC, max_days_overdue DESC
    """)

    if overdue_clients.empty:
        ui.label("Просроченной задолженности не обнаружено.").classes(
            "text-green-700 text-lg"
        )
        return

    total_debt = float(overdue_clients["total_debt"].sum())
    overdue_debt = float(overdue_clients["overdue_debt"].sum())
    overdue_share = overdue_debt / total_debt * 100 if total_debt else 0
    max_days = int(overdue_clients["max_days_overdue"].max())
    client_count = int(overdue_clients["client_id"].nunique())
    branch_count = int(overdue_clients["client_group"].nunique())

    with ui.row().classes("gap-4 mb-6"):
        compact_kpi("Клиентов с просрочкой", str(client_count))
        compact_kpi("Филиалов", str(branch_count))
        compact_kpi("Просрочено", money(overdue_debt))
        compact_kpi("% просрочки", percent(overdue_share))
        compact_kpi("Макс. дней", f"{max_days} дней")

    df = overdue_clients.copy()
    df["rating_display"] = df["stars"].apply(rating_fmt)

    with ui.card().classes("w-full p-4 mb-3"):
        ui.label("Клиенты с просроченной задолженностью").classes(
            "text-xl font-bold mb-1"
        )
        ui.label(
            "Клиенты, формирующие текущую просроченную задолженность портфеля."
        ).classes("text-sm text-gray-500")

    grid = ui.aggrid({
        "columnDefs": [
            {
                "headerName": "Клиент",
                "field": "client_name",
                "sortable": True,
                "filter": True,
                "minWidth": 320,
                ":cellRenderer": """
                    params => `
                        <span style="color:#1976d2; cursor:pointer; font-weight:500;">
                            ${params.data.client_id} · ${params.value}
                        </span>
                    `
                """,
            },
            {"headerName": "Филиал", "field": "client_group", "sortable": True, "filter": True, "minWidth": 140},
            {
                "headerName": "Рейтинг",
                "field": "stars",
                "sortable": True,
                "filter": "agNumberColumnFilter",
                "minWidth": 120,
                "maxWidth": 140,
                ":cellRenderer": rating_aggrid_cell_renderer(),
            },
            {
                "headerName": "Весь долг",
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
                        return `<span style="color:#dc2626; font-weight:700;">${Math.round(value).toLocaleString('ru-RU')}</span>`;
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
                        const color = value > 50 ? '#dc2626' : value > 20 ? '#f97316' : '#ca8a04';
                        return `<span style="color:${color}; font-weight:700;">${value.toFixed(1)}%</span>`;
                    }
                """,
            },
            {
                "headerName": "Макс. дней",
                "field": "max_days_overdue",
                "sortable": True,
                "filter": "agNumberColumnFilter",
                "type": "rightAligned",
                "minWidth": 130,
                ":cellRenderer": """
                    params => {
                        const value = params.value || 0;
                        const color = value > 30 ? '#991b1b' : value > 7 ? '#dc2626' : '#f97316';
                        return `<span style="color:${color}; font-weight:700;">${value}</span>`;
                    }
                """,
            },
            {"headerName": "Риск", "field": "risk_category", "sortable": True, "filter": True, "minWidth": 120},
            {"headerName": "Действие", "field": "recommended_action", "sortable": True, "filter": True, "minWidth": 160},
        ],
        "rowData": df.to_dict("records"),
        "defaultColDef": {"resizable": True, "sortable": True, "filter": True},
        "pagination": True,
        "paginationPageSize": 25,
        "domLayout": "autoHeight",
    }).classes("w-full")

    def open_client_card_from_grid(event):
        args = event.args or {}
        data = args.get("data") or {}
        col_id = (
            args.get("colId")
            or (args.get("column") or {}).get("colId")
            or (args.get("colDef") or {}).get("field")
        )

        if col_id == "client_name" and data.get("client_id"):
            ui.navigate.to(f"/client/{data['client_id']}?from=executive-overdue")

    grid.on("cellClicked", open_client_card_from_grid)