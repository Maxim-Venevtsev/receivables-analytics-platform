from pathlib import Path
import os
from urllib.parse import quote

import pandas as pd
from dotenv import load_dotenv
from nicegui import ui
from sqlalchemy import create_engine, text

from src.app.components.navigation import top_navigation
from src.app.components.kpi_cards import money
from src.app.components.charts import build_long_green_exposure_chart
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


@ui.page("/executive/long-green")
def executive_long_green_page():
    ui.label("Длинная непросроченная задолженность").classes("text-3xl font-bold mb-2")
    ui.label(
        "Контроль клиентов с длинными сроками оплаты при отсутствии формальной просрочки"
    ).classes("text-gray-500 mb-4")

    top_navigation()

    ui.button(
        "← Вернуться к Сводке",
        on_click=lambda: ui.navigate.to("/executive"),
    ).props("flat color=primary").classes("mb-4")

    long_green_clients = query_df("""
        SELECT *
        FROM core.v_client_operational_summary
        WHERE
            green_45_plus_debt > 0
            OR green_60_plus_debt > 0
            OR green_90_plus_debt > 0
            OR green_120_plus_debt > 0
    """)

    long_green_history = query_df("""
        SELECT *
        FROM core.v_executive_long_green_exposure
        ORDER BY report_generated_date
    """)

    if long_green_clients.empty:
        ui.label(
            "Клиентов с длинной непросроченной задолженностью не обнаружено."
        ).classes("text-green-700 text-lg")
        return

    total_45 = float(long_green_clients["green_45_plus_debt"].sum())
    total_90 = float(long_green_clients["green_90_plus_debt"].sum())
    total_120 = float(long_green_clients["green_120_plus_debt"].sum())
    max_term = int(long_green_clients["max_payment_term_days"].max())
    client_count = int(long_green_clients["client_id"].nunique())
    branch_count = int(long_green_clients["client_group"].nunique())

    with ui.row().classes("gap-4 mb-6"):
        compact_kpi("Клиентов под контролем", str(client_count))
        compact_kpi("Филиалов", str(branch_count))
        compact_kpi("45+ дней", money(total_45))
        compact_kpi("90+ дней", money(total_90))
        compact_kpi("120+ дней", money(total_120))
        compact_kpi("Макс. отсрочка", f"{max_term} дней")

    with ui.card().classes("w-full p-4 mb-6"):
        ui.label("Динамика длинной непросроченной задолженности").classes(
            "text-xl font-bold mb-3"
        )
        ui.plotly(build_long_green_exposure_chart(long_green_history)).classes("w-full")

    client_table = render_clients_table(
        long_green_clients,
        title="Контрагенты",
        visible_columns=[
            "client_group",
            "client",
            "rating",
            "contract_payment_term_days",
            "max_payment_term_days",
            "total_debt",
            "green_45_plus_debt",
            "green_60_plus_debt",
            "green_90_plus_debt",
            "green_120_plus_debt",
            "invoice_count",
        ],
        show_branch=True,
        show_search=True,
        from_route="executive-long-green",
    )

    def open_client(event):
        ui.navigate.to(f"/client/{event.args}?from=executive-long-green")

    def open_branch(event):
        ui.navigate.to(f"/branch/{quote(str(event.args))}?from=/executive/long-green")

    if client_table is not None:
        client_table.on("client_click", open_client)
        client_table.on("branch_click", open_branch)
