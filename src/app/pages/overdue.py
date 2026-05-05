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


def percent(value) -> str:
    if pd.isna(value):
        return "0%"
    return f"{float(value):.1f}%"


def risk_badge(category: str) -> str:
    if category == "HIGH":
        return "🔴 HIGH"
    if category == "MEDIUM":
        return "🟡 MEDIUM"
    return "🟢 LOW"


def kpi_card(title: str, value: str, subtitle: str | None = None):
    with ui.card().classes("w-64 h-36 p-4"):
        with ui.column().classes("w-full h-full items-center justify-between text-center"):
            ui.label(title).classes("text-sm text-gray-500 h-6 flex items-center justify-center")
            ui.label(value).classes("text-2xl font-bold h-10 flex items-center justify-center")
            ui.label(subtitle or "").classes("text-sm text-gray-500 h-8 flex items-center justify-center")


@ui.page("/overdue")
def overdue_page():
    ui.label("Просроченная дебиторка").classes("text-3xl font-bold mb-2")

    with ui.row().classes("mb-4"):
        ui.button("📊 Dashboard", on_click=lambda: ui.navigate.to("/")).props("flat color=primary")
        ui.button("📈 Динамика", on_click=lambda: ui.navigate.to("/deltas")).props("flat color=primary")
        ui.button("🔴 Просрочено", on_click=lambda: ui.navigate.to("/overdue")).props("flat color=negative")

    df = query_df("""
        SELECT
            client_id,
            client_name,
            client_group,
            total_debt,
            overdue_debt,
            ROUND(overdue_debt / NULLIF(total_debt, 0) * 100, 2) AS overdue_share_pct,
            max_days_overdue,
            risk_category,
            recommended_action
        FROM core.v_client_priority
        WHERE overdue_debt > 0
        ORDER BY overdue_debt DESC
    """)

    if df.empty:
        ui.label("Просроченной задолженности нет.").classes("text-lg text-green-700")
        return

    total_overdue = df["overdue_debt"].sum()
    total_debt = df["total_debt"].sum()
    overdue_clients = df["client_id"].nunique()
    max_days = int(df["max_days_overdue"].max())

    with ui.row().classes("gap-4"):
        kpi_card("Просрочено", money(total_overdue))
        kpi_card("Клиентов с просрочкой", str(overdue_clients))
        kpi_card("% просрочки", percent(total_overdue / total_debt * 100 if total_debt else 0))
        kpi_card("Макс. дней просрочки", str(max_days))

    df["total_debt_fmt"] = df["total_debt"].apply(money)
    df["overdue_debt_fmt"] = df["overdue_debt"].apply(money)
    df["overdue_share_fmt"] = df["overdue_share_pct"].apply(percent)
    df["risk_fmt"] = df["risk_category"].apply(risk_badge)

    ui.label("Проблемные клиенты").classes("text-xl mt-6")

    table = ui.table(
        columns=[
            {"name": "client_name", "label": "Клиент", "field": "client_name", "align": "left"},
            {"name": "client_group", "label": "Филиал", "field": "client_group", "align": "left"},
            {"name": "total_debt_fmt", "label": "Весь долг", "field": "total_debt_fmt", "align": "right"},
            {"name": "overdue_debt_fmt", "label": "Просрочено", "field": "overdue_debt_fmt", "align": "right"},
            {"name": "overdue_share_fmt", "label": "% просрочки", "field": "overdue_share_fmt", "align": "right"},
            {"name": "max_days_overdue", "label": "Макс. дней", "field": "max_days_overdue", "align": "right"},
            {"name": "risk_fmt", "label": "Риск", "field": "risk_fmt", "align": "center"},
            {"name": "recommended_action", "label": "Действие", "field": "recommended_action", "align": "center"},
        ],
        rows=df.to_dict("records"),
        row_key="client_id",
    ).classes("w-full")

    table.add_slot(
        "body-cell-client_name",
        """
        <q-td :props="props">
            <q-btn
                flat
                dense
                color="primary"
                :label="props.row.client_name"
                @click="$parent.$emit('client_click', props.row.client_id)"
            />
        </q-td>
        """,
    )

    table.add_slot(
        "body-cell-overdue_share_fmt",
        """
        <q-td :props="props">
            <q-badge
                :color="props.row.overdue_share_pct > 50 ? 'red' : props.row.overdue_share_pct > 20 ? 'orange' : 'blue'"
                :label="props.row.overdue_share_fmt"
            />
        </q-td>
        """,
    )

    table.add_slot(
        "body-cell-risk_fmt",
        """
        <q-td :props="props">
            <q-badge
                :color="props.row.risk_category === 'HIGH' ? 'red' : props.row.risk_category === 'MEDIUM' ? 'orange' : 'green'"
                :label="props.row.risk_fmt"
            />
        </q-td>
        """,
    )

    table.add_slot(
        "body-cell-recommended_action",
        """
        <q-td :props="props">
            <q-badge
                :color="props.row.recommended_action === 'CALL NOW' ? 'red' : props.row.recommended_action === 'CONTROL TODAY' ? 'orange' : 'blue'"
                :label="props.row.recommended_action"
            />
        </q-td>
        """,
    )

    def on_client_click(event):
        ui.navigate.to(f"/client/{event.args}")

    table.on("client_click", on_client_click)