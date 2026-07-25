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
from src.app.components.kpi_cards import money, percent
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


@ui.page("/executive/hidden-risk", response_timeout=get_page_response_timeout())
@page_build("executive_hidden_risk", "/executive/hidden-risk")
async def executive_hidden_risk_page():
    ui.label("Скрытый риск").classes("text-3xl font-bold mb-2")
    ui.label(
        "Клиенты с низким рейтингом и длинными отсрочками"
    ).classes("text-gray-500 mb-4")

    top_navigation()

    ui.button(
        "← Вернуться к Сводке",
        on_click=lambda: ui.navigate.to("/executive"),
    ).props("flat color=primary").classes("mb-4")

    df = await query_df("""
        SELECT *
        FROM core.v_client_operational_summary
        WHERE stars <= 3
        AND contract_payment_term_days >= 30
        ORDER BY
            shifted_amount DESC,
            overdue_debt DESC,
            total_debt DESC
    """, operation="executive_hidden_risk_clients")

    if df.empty:
        ui.label("Скрытых рисков не обнаружено.").classes("text-green-700 text-lg")
        return
    
    client_count = int(df["client_id"].nunique())
    branch_count = int(df["client_group"].nunique())
    total_debt = float(df["total_debt"].sum())
    overdue_debt = float(df["overdue_debt"].sum())
    shifted_amount = float(df["shifted_amount"].sum())
    max_contract_term = int(df["contract_payment_term_days"].max())
    max_payment_term = int(df["max_payment_term_days"].max())

    with ui.row().classes("gap-4 mb-6"):
        compact_kpi("Клиентов риска", str(client_count))
        compact_kpi("Филиалов", str(branch_count))
        compact_kpi("Весь долг", money(total_debt))
        compact_kpi("Просрочено", money(overdue_debt))
        compact_kpi("Долг с переносами", money(shifted_amount))
        compact_kpi("Макс. контрактная отсрочка", f"{max_contract_term} дней")
        compact_kpi("Макс. отсрочка", f"{max_payment_term} дней")

    client_table = render_clients_table(
        clients=df,
        title="Контрагенты",
        subtitle=None,
        show_branch=True,
        show_search=True,
        from_route="executive-hidden-risk",
        visible_columns=[
            "client_group",
            "client",
            "rating",
            "contract_payment_term_days",
            "max_payment_term_days",
            "total_debt",
            "overdue_debt",
            "overdue_share_pct",
            "shifted_amount",
            "shifted_share_pct",
            "shifted_invoice_count",
        ],
    )

    def open_client(event):
        ui.navigate.to(f"/client/{event.args}?from=executive-hidden-risk")

    def open_branch(event):
        ui.navigate.to(
            f"/branch/{quote(str(event.args))}?from=/executive/hidden-risk"
        )

    if client_table is not None:
        client_table.on("client_click", open_client)
        client_table.on("branch_click", open_branch)
