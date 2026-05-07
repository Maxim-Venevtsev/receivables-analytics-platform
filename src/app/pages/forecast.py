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


def kpi_card(title: str, value: str, subtitle: str | None = None):
    with ui.card().classes("w-64 h-36 p-4"):
        with ui.column().classes("w-full h-full items-center justify-between text-center"):
            ui.label(title).classes("text-sm text-gray-500 h-6 flex items-center justify-center")
            ui.label(value).classes("text-2xl font-bold h-10 flex items-center justify-center")
            ui.label(subtitle or "").classes("text-sm text-gray-500 h-8 flex items-center justify-center")


@ui.page("/due-today")
def due_today_page():
    ui.label("К оплате сегодня").classes("text-3xl font-bold mb-2")

    with ui.row().classes("mb-4"):
        ui.button("📊 Dashboard", on_click=lambda: ui.navigate.to("/")).props("flat color=primary")
        ui.button("📈 Динамика", on_click=lambda: ui.navigate.to("/deltas")).props("flat color=primary")
        ui.button("🔴 Просрочено", on_click=lambda: ui.navigate.to("/overdue")).props("flat color=negative")
        ui.button("🟠 К оплате сегодня", on_click=lambda: ui.navigate.to("/due-today")).props("flat color=warning")

    df = query_df("""
        SELECT
            client_id,
            client_name,
            client_group,
            total_debt,
            overdue_debt,
            due_today,
            due_in_3_days,
            risk_category,
            recommended_action
        FROM core.v_client_priority
        WHERE due_today > 0 OR due_in_3_days > 0
        ORDER BY due_today DESC, due_in_3_days DESC
    """)

    df["due_soon_only"] = df["due_in_3_days"] - df["due_today"]
    df["due_soon_only"] = df["due_soon_only"].clip(lower=0)

    if df.empty:
        ui.label("На сегодня и ближайшие дни нет платежей к контролю.").classes("text-lg text-green-700")
        return

    branches = (
        df.groupby("client_group", as_index=False)
        .agg(
            total_debt=("total_debt", "sum"),
            due_today=("due_today", "sum"),
            clients_to_control=("client_id", "nunique"),
        )
    )

    selected_branches: list[str] = []

    def normalize_numeric_columns(source_df: pd.DataFrame) -> pd.DataFrame:
        result = source_df.copy()
        for col in ["total_debt", "overdue_debt", "due_today", "due_in_3_days", "clients_to_control"]:
            if col in result.columns:
                result[col] = result[col].astype(float)
        return result

    def prepare_branch_rows():
        branch_df = normalize_numeric_columns(branches)

        if selected_branches:
            branch_df = branch_df[branch_df["client_group"].isin(selected_branches)]

        branch_df["total_debt_fmt"] = branch_df["total_debt"].apply(money)
        branch_df["due_today_fmt"] = branch_df["due_today"].apply(money)
        branch_df["clients_to_control_fmt"] = branch_df["clients_to_control"].astype(int).astype(str)

        return branch_df.to_dict("records")

    def prepare_due_today_rows(search_text: str = ""):
        due_df = normalize_numeric_columns(df)

        if selected_branches:
            due_df = due_df[due_df["client_group"].isin(selected_branches)]

        search_text = (search_text or "").strip().lower()
        if search_text:
            due_df = due_df[
                due_df["client_id"].astype(str).str.lower().str.contains(search_text, na=False)
                | due_df["client_name"].astype(str).str.lower().str.contains(search_text, na=False)
            ]

        due_df["risk_fmt"] = due_df["risk_category"].apply(risk_badge)
        due_df["risk_order"] = due_df["risk_category"].apply(risk_order)

        return due_df.to_dict("records")

    total_due_today = df["due_today"].sum()
    total_due_soon = df["due_soon_only"].sum()
    client_count = df["client_id"].nunique()
    high_risk_count = int((df["risk_category"] == "HIGH").sum())

    with ui.row().classes("gap-4"):
        kpi_card("К оплате сегодня", money(total_due_today))
        kpi_card("К оплате в ближайшие дни", money(total_due_soon))
        kpi_card("Клиентов к контролю", str(client_count))
        kpi_card("Высокий риск", str(high_risk_count), "клиентов в красной зоне")

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
            {"name": "total_debt", "label": "Весь долг", "field": "total_debt", "align": "right", "sortable": True},
            {"name": "due_today", "label": "К оплате сегодня", "field": "due_today", "align": "right", "sortable": True},
            {"name": "clients_to_control", "label": "Клиентов к контролю", "field": "clients_to_control", "align": "right", "sortable": True},
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
        "body-cell-due_today",
        """
        <q-td :props="props" class="text-right">
            {{ props.row.due_today_fmt }}
        </q-td>
        """,
    )

    branch_table.add_slot(
        "body-cell-clients_to_control",
        """
        <q-td :props="props" class="text-right">
            {{ props.row.clients_to_control_fmt }}
        </q-td>
        """,
    )

    ui.label("Клиенты к контролю").classes("text-xl mt-6")

    with ui.row().classes("items-center gap-4 mb-2"):
        search_input = ui.input(
            label="Поиск клиента по ID или названию",
            placeholder="Например: Регинас или 2755",
        ).props("clearable").classes("w-96")

    due_grid = ui.aggrid({
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
                "headerName": "Весь долг",
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
                "headerName": "К оплате сегодня",
                "field": "due_today",
                "sortable": True,
                "filter": "agNumberColumnFilter",
                "type": "rightAligned",
                "minWidth": 170,
                ":cellRenderer": """
                    params => {
                        const value = params.value || 0;
                        return `<span style="color:#f59e0b; font-weight:600;">${Math.round(value).toLocaleString('ru-RU')}</span>`;
                    }
                """,
            },
            {
                "headerName": "К оплате в ближайшие дни",
                "field": "due_soon_only",
                "sortable": True,
                "filter": "agNumberColumnFilter",
                "type": "rightAligned",
                "minWidth": 210,
                ":cellRenderer": """
                    params => {
                        const value = params.value || 0;
                        return `<span style="color:#ca8a04; font-weight:600;">${Math.round(value).toLocaleString('ru-RU')}</span>`;
                    }
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
        "rowData": prepare_due_today_rows(),
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

        due_grid.options["rowData"] = prepare_due_today_rows(search_input.value)
        due_grid.update()

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
    due_grid.on("cellClicked", open_client_card_from_grid)
    search_input.on_value_change(lambda _: apply_filters())