from pathlib import Path
import os

import pandas as pd
from dotenv import load_dotenv
from nicegui import ui
from sqlalchemy import create_engine, text

from src.app.pages.deltas import deltas_page
from src.app.pages.overdue import overdue_page
from src.app.pages.client_card import client_card_page


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
        return "🔴 Высокий"
    if category == "MEDIUM":
        return "🟡 Средний"
    return "🟢 Низкий"


def risk_order(category: str) -> int:
    if category == "HIGH":
        return 3
    if category == "MEDIUM":
        return 2
    return 1


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
            client_id,
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

    selected_branches: list[str] = []

    def normalize_numeric_columns(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        for col in ["total_debt", "overdue_debt", "overdue_share_pct"]:
            if col in df.columns:
                df[col] = df[col].astype(float)
        return df

    def prepare_branch_rows():
        df = normalize_numeric_columns(branches)

        if selected_branches:
            df = df[df["client_group"].isin(selected_branches)]

        df["total_debt_fmt"] = df["total_debt"].apply(money)
        df["overdue_debt_fmt"] = df["overdue_debt"].apply(money)
        df["overdue_share_fmt"] = df["overdue_share_pct"].apply(percent)

        return df.to_dict("records")

    def prepare_priority_rows(search_text: str = ""):
        df = priority.copy()

        for col in ["total_debt", "overdue_debt"]:
            df[col] = df[col].astype(float)

        if selected_branches:
            df = df[df["client_group"].isin(selected_branches)]

        search_text = (search_text or "").strip().lower()
        if search_text:
            df = df[
                df["client_id"].astype(str).str.lower().str.contains(search_text, na=False)
                | df["client_name"].astype(str).str.lower().str.contains(search_text, na=False)
            ]

        df["risk_fmt"] = df["risk_category"].apply(risk_badge)
        df["risk_order"] = df["risk_category"].apply(risk_order)

        return df.to_dict("records")

    ui.label("АРС — Дебиторка").classes("text-3xl font-bold mb-2")

    with ui.row().classes("mb-4"):
        ui.button(
            "📊 Dashboard",
            on_click=lambda: ui.navigate.to("/")
        ).props("flat color=primary")

        ui.button(
            "📈 Динамика",
            on_click=lambda: ui.navigate.to("/deltas")
        ).props("flat color=primary")

        ui.button(
            "🔴 Просрочено",
            on_click=lambda: ui.navigate.to("/overdue")
        ).props("flat color=negative")

    with ui.row().classes("gap-4"):
        kpi_card("Общая задолженность", money(kpi.total_debt))

        with ui.card().classes("w-64 h-36 p-4 cursor-pointer hover:shadow-lg").on(
            "click", lambda: ui.navigate.to("/overdue")
        ):
            with ui.column().classes("w-full h-full items-center justify-between text-center"):
                ui.label("Просрочено").classes("text-sm text-gray-500 h-6 flex items-center justify-center")
                ui.label(money(kpi.overdue_debt)).classes("text-2xl font-bold h-10 flex items-center justify-center")
                ui.label(f"{percent(kpi.overdue_share_pct)} от общей задолженности").classes(
                    "text-sm text-gray-500 h-8 flex items-center justify-center"
                )

        kpi_card(
            "К оплате сегодня",
            money(kpi.due_today),
            "согласно срокам оплаты",
        )

        kpi_card("Высокий риск", str(kpi.high_risk_client_count), "клиентов в красной зоне")

    ui.separator().classes("my-4")

    with ui.row().classes("items-center gap-4"):
        selected_branch_label = ui.label("Показаны все филиалы").classes("text-sm text-gray-500")
        ui.button(
            "ВСЕ ФИЛИАЛЫ",
            on_click=lambda: reset_branch_filter(),
        ).props("flat color=primary")

    ui.label("Филиалы").classes("text-xl mt-6")

    branch_table = ui.table(
        columns=[
            {"name": "client_group", "label": "Филиал", "field": "client_group", "align": "left", "sortable": True},
            {"name": "total_debt", "label": "Долг", "field": "total_debt", "align": "right", "sortable": True},
            {"name": "overdue_debt", "label": "Просрочка", "field": "overdue_debt", "align": "right", "sortable": True},
            {"name": "overdue_share_pct", "label": "% просрочки", "field": "overdue_share_pct", "align": "right", "sortable": True},
        ],
        rows=prepare_branch_rows(),
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
        "body-cell-total_debt",
        """
        <q-td :props="props" class="text-right">
            {{ props.row.total_debt_fmt }}
        </q-td>
        """,
    )

    branch_table.add_slot(
        "body-cell-overdue_debt",
        """
        <q-td :props="props" class="text-right">
            {{ props.row.overdue_debt_fmt }}
        </q-td>
        """,
    )

    branch_table.add_slot(
        "body-cell-overdue_share_pct",
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

    with ui.row().classes("items-center gap-4 mb-2"):
        search_input = ui.input(
            label="Поиск клиента по ID или названию",
            placeholder="Например: Регинас или 2755",
        ).props("clearable").classes("w-96")

    priority_grid = ui.aggrid({
        "columnDefs": [
            {
                "headerName": "Клиент",
                "field": "client_name",
                "sortable": True,
                "filter": True,
                "minWidth": 260,
                ":cellRenderer": """
                    params => `<span style="color:#1976d2; cursor:pointer; font-weight:500;">${params.value}</span>`
                """,
            },
            {
                "headerName": "Филиал",
                "field": "client_group",
                "sortable": True,
                "filter": True,
                "minWidth": 130,
            },
            {
                "headerName": "Долг",
                "field": "total_debt",
                "sortable": True,
                "filter": "agNumberColumnFilter",
                "type": "rightAligned",
                "minWidth": 140,
                ":valueFormatter": """
                    params => params.value == null ? '' : Math.round(params.value).toLocaleString('ru-RU')
                """,
            },
            {
                "headerName": "Просрочка",
                "field": "overdue_debt",
                "sortable": True,
                "filter": "agNumberColumnFilter",
                "type": "rightAligned",
                "minWidth": 140,
                ":valueFormatter": """
                    params => params.value == null ? '' : Math.round(params.value).toLocaleString('ru-RU')
                """,
            },
            {
                "headerName": "Риск",
                "field": "risk_order",
                "sortable": True,
                "filter": True,
                "minWidth": 130,
                ":cellRenderer": """
                    params => {
                        const risk = params.data.risk_category;
                        const label = params.data.risk_fmt;
                        const color = risk === 'HIGH' ? '#dc2626' : risk === 'MEDIUM' ? '#f59e0b' : '#16a34a';
                        return `<span style="color:${color}; font-weight:600;">${label}</span>`;
                    }
                """,
            },
            {
                "headerName": "Действие",
                "field": "recommended_action",
                "sortable": True,
                "filter": True,
                "minWidth": 160,
                ":cellRenderer": """
                    params => {
                        const value = params.value;
                        const color = value === 'CALL NOW' ? '#dc2626'
                            : value === 'CONTROL TODAY' ? '#f59e0b'
                            : '#2563eb';
                        return `<span style="color:${color}; font-weight:600;">${value}</span>`;
                    }
                """,
            },
        ],
        "rowData": prepare_priority_rows(),
        "defaultColDef": {
            "resizable": True,
            "sortable": True,
            "filter": True,
        },
        "pagination": True,
        "paginationPageSize": 20,
        "domLayout": "autoHeight",
    }).classes("w-full")

    def apply_filters():
        if selected_branches:
            selected_branch_label.text = f"Фильтр: {', '.join(selected_branches)}"
        else:
            selected_branch_label.text = "Показаны все филиалы"
        selected_branch_label.update()

        branch_table.rows = prepare_branch_rows()
        branch_table.update()

        priority_grid.options["rowData"] = prepare_priority_rows(search_input.value)
        priority_grid.update()

    def select_branch_from_table(event):
        selected_branches.clear()
        selected_branches.append(event.args)
        apply_filters()

    def reset_branch_filter():
        selected_branches.clear()
        apply_filters()

    def open_client_card_from_grid(event):
        args = event.args or {}
        data = args.get("data") or {}

        col_id = (
            args.get("colId")
            or (args.get("column") or {}).get("colId")
            or (args.get("colDef") or {}).get("field")
        )

        if col_id == "client_name" and data.get("client_id"):
            ui.navigate.to(f"/client/{data['client_id']}")

    branch_table.on("branch_click", select_branch_from_table)
    priority_grid.on("cellClicked", open_client_card_from_grid)
    search_input.on_value_change(lambda _: apply_filters())


ui.run()