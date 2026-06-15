from pathlib import Path
import os
from urllib.parse import quote

import pandas as pd
from dotenv import load_dotenv
from nicegui import ui
from sqlalchemy import create_engine, text

from src.app.components.navigation import top_navigation
from src.app.components.kpi_cards import money, percent
from src.app.components.clients_table import render_clients_table

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
        FROM core.v_client_operational_summary
        WHERE overdue_debt > 0
        ORDER BY
            overdue_debt DESC,
            max_days_overdue DESC,
            total_debt DESC
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

    client_table = render_clients_table(
        clients=overdue_clients,
        title="Контрагенты",
        subtitle=None,
        show_branch=True,
        show_search=True,
        from_route="executive-overdue",
        visible_columns=[
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
        ],
    )

    def open_client(event):
        ui.navigate.to(f"/client/{event.args}?from=executive-overdue")

    def open_branch(event):
        ui.navigate.to(
            f"/branch/{quote(str(event.args))}?from=/executive/overdue"
        )

    if client_table is not None:
        client_table.on("client_click", open_client)
        client_table.on("branch_click", open_branch)