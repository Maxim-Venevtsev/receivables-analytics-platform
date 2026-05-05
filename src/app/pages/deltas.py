from pathlib import Path
import os

import pandas as pd
from dotenv import load_dotenv
from nicegui import ui
from sqlalchemy import create_engine, text


PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env")

engine = create_engine(
    f"postgresql+psycopg2://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@"
    f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)


def query_df(sql: str) -> pd.DataFrame:
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn)


def money(value) -> str:
    if pd.isna(value):
        return "0"
    return f"{float(value):,.0f}".replace(",", " ")


def signed_money(value) -> str:
    if pd.isna(value):
        return "0"
    number = float(value)
    sign = "+" if number > 0 else ""
    return f"{sign}{number:,.0f}".replace(",", " ")


def kpi_card(title: str, value: str, subtitle: str | None = None):
    with ui.card().classes("w-64 h-36 p-4"):
        with ui.column().classes("w-full h-full items-center justify-between text-center"):
            ui.label(title).classes("text-sm text-gray-500 h-6 flex items-center justify-center")
            ui.label(value).classes("text-2xl font-bold h-10 flex items-center justify-center")
            ui.label(subtitle or "").classes("text-sm text-gray-500 h-8 flex items-center justify-center")


@ui.page("/deltas")
def deltas_page():
    ui.label("Динамика дебиторки").classes("text-3xl font-bold mb-2")

    with ui.row().classes("mb-4"):
        ui.button("📊 Dashboard", on_click=lambda: ui.navigate.to("/")).props("flat color=primary")
        ui.button("📈 Динамика", on_click=lambda: ui.navigate.to("/deltas")).props("flat color=primary")

    df = query_df("""
        SELECT
            report_generated_date,
            client_name,
            client_group,
            previous_total_debt,
            total_debt,
            total_debt_delta,
            debt_change_status
        FROM core.v_client_deltas
        WHERE previous_total_debt IS NOT NULL
        ORDER BY report_generated_date DESC, ABS(total_debt_delta) DESC
        LIMIT 100
    """)

    increased_count = int((df["total_debt_delta"] > 0).sum())
    decreased_count = int((df["total_debt_delta"] < 0).sum())
    unchanged_count = int((df["total_debt_delta"] == 0).sum())

    total_increase = df.loc[df["total_debt_delta"] > 0, "total_debt_delta"].sum()
    total_decrease = df.loc[df["total_debt_delta"] < 0, "total_debt_delta"].sum()

    with ui.row().classes("gap-4"):
        kpi_card("Долг вырос", money(total_increase), f"{increased_count} клиентов")
        kpi_card("Долг снизился", money(abs(total_decrease)), f"{decreased_count} клиентов")
        kpi_card("Без изменений", str(unchanged_count), "клиентов")
        kpi_card("Строк в анализе", str(len(df)), "последние изменения")

    df["previous_total_debt_fmt"] = df["previous_total_debt"].apply(money)
    df["total_debt_fmt"] = df["total_debt"].apply(money)
    df["total_debt_delta_fmt"] = df["total_debt_delta"].apply(signed_money)

    ui.label("Изменения по клиентам").classes("text-xl mt-6")

    table = ui.table(
        columns=[
            {"name": "report_generated_date", "label": "Дата", "field": "report_generated_date", "align": "left"},
            {"name": "client_name", "label": "Клиент", "field": "client_name", "align": "left"},
            {"name": "client_group", "label": "Филиал", "field": "client_group", "align": "left"},
            {"name": "previous_total_debt_fmt", "label": "Было", "field": "previous_total_debt_fmt", "align": "right"},
            {"name": "total_debt_fmt", "label": "Стало", "field": "total_debt_fmt", "align": "right"},
            {"name": "total_debt_delta_fmt", "label": "Изменение", "field": "total_debt_delta_fmt", "align": "right"},
            {"name": "debt_change_status", "label": "Статус", "field": "debt_change_status", "align": "center"},
        ],
        rows=df.to_dict("records"),
    ).classes("w-full")

    table.add_slot(
        "body-cell-total_debt_delta_fmt",
        """
        <q-td :props="props">
            <q-badge
                :color="props.row.total_debt_delta > 0 ? 'red' : props.row.total_debt_delta < 0 ? 'green' : 'grey'"
                :label="props.row.total_debt_delta_fmt"
            />
        </q-td>
        """,
    )

    table.add_slot(
        "body-cell-debt_change_status",
        """
        <q-td :props="props">
            <q-badge
                :color="props.row.total_debt_delta > 0 ? 'red' : props.row.total_debt_delta < 0 ? 'green' : 'grey'"
                :label="props.row.debt_change_status"
            />
        </q-td>
        """,
    )