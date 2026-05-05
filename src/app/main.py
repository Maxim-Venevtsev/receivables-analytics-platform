from pathlib import Path
import os

import pandas as pd
from dotenv import load_dotenv
from nicegui import ui
from sqlalchemy import create_engine, text

from src.app.pages.deltas import deltas_page


PROJECT_ROOT = Path(__file__).resolve().parents[2]
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


def kpi_card(title: str, value: str, subtitle: str | None = None):
    with ui.card().classes("w-64 h-36 p-4"):
        with ui.column().classes("w-full h-full items-center justify-between text-center"):
            ui.label(title).classes("text-sm text-gray-500 h-6 flex items-center justify-center")
            ui.label(value).classes("text-2xl font-bold h-10 flex items-center justify-center")
            ui.label(subtitle or "").classes("text-sm text-gray-500 h-8 flex items-center justify-center")


def risk_badge(category: str) -> str:
    if category == "HIGH":
        return "🔴 HIGH"
    if category == "MEDIUM":
        return "🟡 MEDIUM"
    return "🟢 LOW"


@ui.page("/")
def dashboard():
    kpi = query_df("SELECT * FROM core.v_dashboard_overview").iloc[0]

    branches = query_df("""
        SELECT
            client_group,
            total_debt,
            overdue_debt,
            overdue_share_pct
        FROM core.v_branch_summary
        ORDER BY total_debt DESC
    """)

    priority = query_df("""
        SELECT
            client_name,
            client_group,
            total_debt,
            overdue_debt,
            risk_category,
            recommended_action
        FROM core.v_client_priority
        ORDER BY risk_score DESC
        LIMIT 15
    """)

    branches["total_debt_fmt"] = branches["total_debt"].apply(money)
    branches["overdue_debt_fmt"] = branches["overdue_debt"].apply(money)
    branches["overdue_share_fmt"] = branches["overdue_share_pct"].apply(percent)

    priority["total_debt_fmt"] = priority["total_debt"].apply(money)
    priority["overdue_debt_fmt"] = priority["overdue_debt"].apply(money)
    priority["risk_fmt"] = priority["risk_category"].apply(risk_badge)

    ui.label("АРС — Дебиторка").classes("text-3xl font-bold mb-2")

    with ui.row().classes("mb-4"):
        ui.button("📊 Dashboard", on_click=lambda: ui.navigate.to("/")).props("flat color=primary")
        ui.button("📈 Динамика", on_click=lambda: ui.navigate.to("/deltas")).props("flat color=primary")

    with ui.row().classes("gap-4"):
        kpi_card("Общая задолженность", money(kpi.total_debt))
        kpi_card(
            "Просрочено",
            money(kpi.overdue_debt),
            f"{percent(kpi.overdue_share_pct)} от общей задолженности",
        )
        kpi_card("К оплате сегодня", money(kpi.due_today))
        kpi_card("HIGH RISK", str(kpi.high_risk_client_count), "клиентов в красной зоне")

    ui.label("Филиалы").classes("text-xl mt-6")

    branch_table = ui.table(
        columns=[
            {"name": "client_group", "label": "Филиал", "field": "client_group", "align": "left"},
            {"name": "total_debt_fmt", "label": "Долг", "field": "total_debt_fmt", "align": "right"},
            {"name": "overdue_debt_fmt", "label": "Просрочка", "field": "overdue_debt_fmt", "align": "right"},
            {"name": "overdue_share_fmt", "label": "% просрочки", "field": "overdue_share_fmt", "align": "right"},
        ],
        rows=branches.to_dict("records"),
    ).classes("w-full")

    branch_table.add_slot(
        "body-cell-overdue_share_fmt",
        """
        <q-td :props="props">
            <q-badge
                :color="props.row.overdue_share_pct > 20 ? 'red' : props.row.overdue_share_pct > 0 ? 'orange' : 'green'"
                :label="props.row.overdue_share_fmt"
            />
        </q-td>
        """,
    )

    ui.label("Клиенты в работе").classes("text-xl mt-6")

    priority_table = ui.table(
        columns=[
            {"name": "client_name", "label": "Клиент", "field": "client_name", "align": "left"},
            {"name": "client_group", "label": "Филиал", "field": "client_group", "align": "left"},
            {"name": "total_debt_fmt", "label": "Долг", "field": "total_debt_fmt", "align": "right"},
            {"name": "overdue_debt_fmt", "label": "Просрочка", "field": "overdue_debt_fmt", "align": "right"},
            {"name": "risk_fmt", "label": "Риск", "field": "risk_fmt", "align": "center"},
            {"name": "recommended_action", "label": "Действие", "field": "recommended_action", "align": "center"},
        ],
        rows=priority.to_dict("records"),
    ).classes("w-full")

    priority_table.add_slot(
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

    priority_table.add_slot(
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


ui.run()