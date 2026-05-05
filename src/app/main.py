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
        LIMIT 100
    """)

    branch_options = sorted(branches["client_group"].dropna().unique().tolist())

    def normalize_selected_branches(value):
        if not value:
            return []
        if isinstance(value, str):
            return [value]
        return value

    def prepare_branch_rows(selected_branches):
        df = branches.copy()
        selected_branches = normalize_selected_branches(selected_branches)

        if selected_branches:
            df = df[df["client_group"].isin(selected_branches)]

        df["total_debt_fmt"] = df["total_debt"].apply(money)
        df["overdue_debt_fmt"] = df["overdue_debt"].apply(money)
        df["overdue_share_fmt"] = df["overdue_share_pct"].apply(percent)

        return df.to_dict("records")

    def prepare_priority_rows(selected_branches):
        df = priority.copy()
        selected_branches = normalize_selected_branches(selected_branches)

        if selected_branches:
            df = df[df["client_group"].isin(selected_branches)]

        df["total_debt_fmt"] = df["total_debt"].apply(money)
        df["overdue_debt_fmt"] = df["overdue_debt"].apply(money)
        df["risk_fmt"] = df["risk_category"].apply(risk_badge)

        return df.to_dict("records")

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
        kpi_card(
            "К оплате сегодня",
            money(kpi.due_today),
            "согласно срокам оплаты",
        )
        kpi_card("HIGH RISK", str(kpi.high_risk_client_count), "клиентов в красной зоне")

    ui.separator().classes("my-4")

    with ui.row().classes("items-center gap-4"):
        ui.label("Фильтр по филиалу").classes("text-sm text-gray-500")

        branch_select = ui.select(
            options=branch_options,
            value=[],
            multiple=True,
            label="Ничего не выбрано = все филиалы",
        ).props("use-chips clearable").classes("w-96")

        ui.button(
            "Все филиалы",
            on_click=lambda: reset_branch_filter(),
        ).props("flat color=primary")

    ui.label("Филиалы").classes("text-xl mt-6")

    branch_table = ui.table(
        columns=[
            {"name": "client_group", "label": "Филиал", "field": "client_group", "align": "left"},
            {"name": "total_debt_fmt", "label": "Долг", "field": "total_debt_fmt", "align": "right"},
            {"name": "overdue_debt_fmt", "label": "Просрочка", "field": "overdue_debt_fmt", "align": "right"},
            {"name": "overdue_share_fmt", "label": "% просрочки", "field": "overdue_share_fmt", "align": "right"},
        ],
        rows=prepare_branch_rows([]),
    ).classes("w-full")

    branch_table.add_slot(
        "body-cell-client_group",
        """
        <q-td :props="props">
            <q-btn
                flat
                dense
                color="primary"
                :label="props.row.client_group"
                @click="$parent.$emit('branch_click', props.row.client_group)"
            />
        </q-td>
        """,
    )

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
        rows=prepare_priority_rows([]),
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

    def apply_branch_filter():
        selected_branches = branch_select.value or []

        branch_table.rows = prepare_branch_rows(selected_branches)
        branch_table.update()

        priority_table.rows = prepare_priority_rows(selected_branches)
        priority_table.update()

    def select_branch_from_table(event):
        branch_select.value = [event.args]
        apply_branch_filter()

    def reset_branch_filter():
        branch_select.value = []
        apply_branch_filter()

    branch_select.on_value_change(lambda _: apply_branch_filter())
    branch_table.on("branch_click", select_branch_from_table)


ui.run()