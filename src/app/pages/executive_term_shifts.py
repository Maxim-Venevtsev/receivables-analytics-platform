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
from src.app.components.kpi_cards import money
from src.app.components.clients_table import render_clients_table


PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env")

engine = create_engine(
    f"postgresql+psycopg2://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@"
    f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)


async def query_df(sql: str, params: dict | None = None, *, operation: str) -> pd.DataFrame:
    return await read_dataframe(engine, sql, operation=operation, params=params)


def compact_kpi(title: str, value: str, subtitle: str = ""):
    with ui.card().classes("w-60 h-32 p-4"):
        with ui.column().classes("w-full h-full items-center justify-between text-center"):
            ui.label(title).classes("text-sm text-gray-500 h-6 flex items-center justify-center")
            ui.label(value).classes("text-2xl font-bold h-10 flex items-center justify-center")
            ui.label(subtitle).classes("text-sm text-gray-500 h-8 flex items-center justify-center")


@ui.page("/executive/term-shifts", response_timeout=get_page_response_timeout())
@page_build("executive_term_shifts", "/executive/term-shifts")
async def executive_term_shifts_page():
    ui.label("Переносы сроков оплаты").classes("text-3xl font-bold mb-2")
    ui.label(
        "Контроль клиентов и накладных, по которым сроки оплаты увеличивались между срезами"
    ).classes("text-gray-500 mb-4")

    top_navigation()

    ui.button(
        "← Вернуться к Сводке",
        on_click=lambda: ui.navigate.to("/executive"),
    ).props("flat color=primary").classes("mb-4")

    
    clients = await query_df("""
        SELECT *
        FROM core.v_client_operational_summary
        WHERE shifted_amount > 0
        ORDER BY
            repeated_shift_amount DESC,
            shifted_amount DESC,
            term_shift_count DESC,
            total_debt DESC
    """, operation="executive_term_shifts_clients")

    
    if clients.empty:
        ui.label("Переносов сроков оплаты не обнаружено.").classes("text-green-700 text-lg")
        return

    shifted_amount = float(clients["shifted_amount"].sum())
    shifted_invoice_count = int(clients["shifted_invoice_count"].sum())
    term_shift_count = int(clients["term_shift_count"].sum())
    repeated_shift_amount = float(clients["repeated_shift_amount"].sum())
    max_term_delta = int(clients["max_current_term_delta_days"].max())
    client_count = int(clients["client_id"].nunique())
    branch_count = int(clients["client_group"].nunique())

    clients_with_5_plus = int((clients["term_shift_count"] >= 5).sum())
    clients_with_10_plus = int((clients["term_shift_count"] >= 10).sum())

    shifted_amount = float(clients["shifted_amount"].sum())
    shifted_invoice_count = int(clients["shifted_invoice_count"].sum())
    term_shift_count = int(clients["term_shift_count"].sum())
    max_term_delta = int(clients["max_current_term_delta_days"].max())
    client_count = int(clients["client_id"].nunique())
    branch_count = int(clients["client_group"].nunique())

    with ui.row().classes("gap-4 mb-6"):
        compact_kpi("Клиентов с переносами", str(client_count))
        compact_kpi("Филиалов", str(branch_count))
        compact_kpi("Перенесено", money(shifted_amount))
        compact_kpi("Накладных", str(shifted_invoice_count))
        compact_kpi("Событий переноса", str(term_shift_count))
        compact_kpi("Макс. рост срока", f"{max_term_delta} дней")
        compact_kpi(
            "Клиентов с 5+ переносами",
            str(clients_with_5_plus),
            f"10+: {clients_with_10_plus}",
        )

    client_table = render_clients_table(
        clients=clients,
        title="Контрагенты",
        subtitle=None,
        show_branch=True,
        show_search=True,
        from_route="executive-term-shifts",
        visible_columns=[
            "client_group",
            "client",
            "rating",
            "total_debt",
            "shifted_amount",
            "repeated_shift_amount",
            "shifted_share_pct",
            "term_shift_count",
            "repeated_shift_invoice_count",
            "last_shift_date",
            "contract_payment_term_days",
            "max_current_term_delta_days",
            "max_current_payment_term_days",
            "shifted_invoice_count",
        ],
    )

    def open_client(event):
        ui.navigate.to(f"/client/{event.args}?from=executive-term-shifts")

    def open_branch(event):
        ui.navigate.to(
            f"/branch/{quote(str(event.args))}?from=/executive/term-shifts"
        )

    if client_table is not None:
        client_table.on("client_click", open_client)
        client_table.on("branch_click", open_branch)
