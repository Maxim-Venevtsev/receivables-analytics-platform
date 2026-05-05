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


def query_df(sql: str, params: dict = None) -> pd.DataFrame:
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn, params=params)


def money(value):
    return f"{float(value):,.0f}".replace(",", " ")


@ui.page("/client/{client_id}")
def client_detail_page(client_id: str):

    ui.label(f"Карточка клиента: {client_id}").classes("text-3xl font-bold mb-4")

    with ui.row().classes("mb-4"):
        ui.button("← Назад", on_click=lambda: ui.navigate.to("/overdue")).props("flat color=primary")

    df = query_df("""
        SELECT
            invoice_date,
            due_date,
            invoice_amount,
            days_overdue_real,
            is_overdue_real
        FROM core.receivables_snapshot_fact
        WHERE client_id = :client_id
        ORDER BY invoice_date DESC
    """, {"client_id": client_id})

    if df.empty:
        ui.label("Нет данных по клиенту")
        return

    df["invoice_amount_fmt"] = df["invoice_amount"].apply(money)

    ui.table(
        columns=[
            {"name": "invoice_date", "label": "Дата", "field": "invoice_date"},
            {"name": "due_date", "label": "Оплатить до", "field": "due_date"},
            {"name": "invoice_amount_fmt", "label": "Сумма", "field": "invoice_amount_fmt"},
            {"name": "days_overdue_real", "label": "Просрочка (дни)", "field": "days_overdue_real"},
            {"name": "is_overdue_real", "label": "Просрочено", "field": "is_overdue_real"},
        ],
        rows=df.to_dict("records"),
    ).classes("w-full")