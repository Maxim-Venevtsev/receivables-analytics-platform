from pathlib import Path
import os

import pandas as pd
from dotenv import load_dotenv
from nicegui import ui
from sqlalchemy import create_engine, text
from src.app.components.branch_filter import create_branch_filter
from src.app.components.navigation import top_navigation
from src.app.components.rating_stars import rating_aggrid_cell_renderer


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


def load_forecast_df() -> pd.DataFrame:
    df = query_df("""
        SELECT
            p.client_id,
            p.client_name,
            r.stars,
            r.rating_display_label,
            r.confidence_level,
            p.client_group,
            p.total_debt,
            p.overdue_debt,
            p.due_today,
            p.due_in_3_days,
            p.risk_category,
            p.recommended_action
        FROM core.v_client_priority p
        LEFT JOIN core.v_client_rating r
            ON p.client_id = r.client_id
        WHERE p.due_today > 0 OR p.due_in_3_days > 0
        ORDER BY p.due_today DESC, p.due_in_3_days DESC
    """)

    df["due_soon_only"] = (df["due_in_3_days"] - df["due_today"]).clip(lower=0)
    return df


def render_forecast_page(mode: str):
    is_due_today_page = mode == "today"

    page_title = "К оплате сегодня" if is_due_today_page else "К оплате в ближайшие дни"
    ui.label(page_title).classes("text-3xl font-bold mb-2")

    top_navigation()

    df = load_forecast_df()

    if not is_due_today_page:
        df = df[df["due_soon_only"] > 0]

    if df.empty:
        message = (
            "На сегодня нет платежей к контролю."
            if is_due_today_page
            else "На ближайшие 3 дня нет платежей к контролю."
        )
        ui.label(message).classes("text-lg text-green-700")
        return

    selected_branches: list[str] = []

    def normalize_numeric_columns(source_df: pd.DataFrame) -> pd.DataFrame:
        result = source_df.copy()
        for col in ["total_debt", "overdue_debt", "due_today", "due_in_3_days", "due_soon_only", "clients_to_control"]:
            if col in result.columns:
                result[col] = result[col].astype(float)
        return result

    branches = (
        df.groupby("client_group", as_index=False)
        .agg(
            total_debt=("total_debt", "sum"),
            due_today=("due_today", "sum"),
            due_soon_only=("due_soon_only", "sum"),
            clients_to_control=("client_id", "nunique"),
        )
    )

    def filtered_df() -> pd.DataFrame:
        result = normalize_numeric_columns(df)
        if selected_branches:
            result = result[result["client_group"].isin(selected_branches)]
        return result

    def prepare_rows(search_text: str = ""):
        result = filtered_df()

        search_text = (search_text or "").strip().lower()
        if search_text:
            result = result[
                result["client_id"].astype(str).str.lower().str.contains(search_text, na=False)
                | result["client_name"].astype(str).str.lower().str.contains(search_text, na=False)
            ]

        result["risk_fmt"] = result["risk_category"].apply(risk_badge)
        result["risk_order"] = result["risk_category"].apply(risk_order)

        return result.to_dict("records")

    def get_kpi_metrics() -> dict[str, float | int]:
        result = filtered_df()
        return {
            "due_today": float(result["due_today"].sum()),
            "due_soon_only": float(result["due_soon_only"].sum()),
            "client_count": int(result["client_id"].nunique()),
            "high_risk_count": int((result["risk_category"] == "HIGH").sum()),
        }

    initial_kpi = get_kpi_metrics()

    with ui.row().classes("gap-4"):
        if is_due_today_page:
            first_title = "К оплате сегодня"
            first_value = initial_kpi["due_today"]
            second_title = "К оплате в ближайшие дни"
            second_value = initial_kpi["due_soon_only"]
        else:
            first_title = "К оплате в ближайшие дни"
            first_value = initial_kpi["due_soon_only"]
            second_title = "К оплате сегодня"
            second_value = initial_kpi["due_today"]

        with ui.card().classes("w-64 h-36 p-4"):
            with ui.column().classes("w-full h-full items-center justify-between text-center"):
                ui.label(first_title).classes("text-sm text-gray-500 h-6 flex items-center justify-center")
                first_value_label = ui.label(money(first_value)).classes("text-2xl font-bold h-10 flex items-center justify-center")
                ui.label("").classes("text-sm text-gray-500 h-8 flex items-center justify-center")

        with ui.card().classes("w-64 h-36 p-4"):
            with ui.column().classes("w-full h-full items-center justify-between text-center"):
                ui.label(second_title).classes("text-sm text-gray-500 h-6 flex items-center justify-center")
                second_value_label = ui.label(money(second_value)).classes("text-2xl font-bold h-10 flex items-center justify-center")
                ui.label("").classes("text-sm text-gray-500 h-8 flex items-center justify-center")

        with ui.card().classes("w-64 h-36 p-4"):
            with ui.column().classes("w-full h-full items-center justify-between text-center"):
                ui.label("Клиентов к контролю").classes("text-sm text-gray-500 h-6 flex items-center justify-center")
                client_count_label = ui.label(str(initial_kpi["client_count"])).classes("text-2xl font-bold h-10 flex items-center justify-center")
                ui.label("").classes("text-sm text-gray-500 h-8 flex items-center justify-center")

        with ui.card().classes("w-64 h-36 p-4"):
            with ui.column().classes("w-full h-full items-center justify-between text-center"):
                ui.label("Высокий риск").classes("text-sm text-gray-500 h-6 flex items-center justify-center")
                high_risk_label = ui.label(str(initial_kpi["high_risk_count"])).classes("text-2xl font-bold h-10 flex items-center justify-center")
                ui.label("клиентов в красной зоне").classes("text-sm text-gray-500 h-8 flex items-center justify-center")

    def update_kpi_cards():
        metrics = get_kpi_metrics()
        if is_due_today_page:
            first_value_label.text = money(metrics["due_today"])
            second_value_label.text = money(metrics["due_soon_only"])
        else:
            first_value_label.text = money(metrics["due_soon_only"])
            second_value_label.text = money(metrics["due_today"])
        client_count_label.text = str(metrics["client_count"])
        high_risk_label.text = str(metrics["high_risk_count"])

        first_value_label.update()
        second_value_label.update()
        client_count_label.update()
        high_risk_label.update()

    branch_filter = None

    def apply_filters():
        branch_filter.update()
        update_kpi_cards()
        grid.options["rowData"] = prepare_rows(search_input.value)
        grid.update()

    branch_columns = [
        {"name": "client_group", "label": "Филиал", "field": "client_group", "align": "left", "sortable": True},
        {"name": "total_debt", "label": "Весь долг", "field": "total_debt", "align": "right", "sortable": True},
    ]

    if is_due_today_page:
        branch_columns.append({"name": "due_today", "label": "К оплате сегодня", "field": "due_today", "align": "right", "sortable": True})
    else:
        branch_columns.append({"name": "due_soon_only", "label": "К оплате в ближайшие дни", "field": "due_soon_only", "align": "right", "sortable": True})

    branch_columns.append({"name": "clients_to_control", "label": "Клиентов к контролю", "field": "clients_to_control", "align": "right", "sortable": True})

    branch_filter = create_branch_filter(
        branches=branches,
        selected_branches=selected_branches,
        on_change=apply_filters,
        columns=branch_columns,
    )

    ui.label("Клиенты к контролю").classes("text-xl mt-6")

    with ui.row().classes("items-center gap-4 mb-2"):
        search_input = ui.input(
            label="Поиск клиента по ID или названию",
            placeholder="Например: Регинас или 2755",
        ).props("clearable").classes("w-96")

    client_columns = [
        {
            "headerName": "Клиент",
            "field": "client_name",
            "sortable": True,
            "filter": True,
            "minWidth": 260,
            ":cellRenderer": """
                params => `
                    <span style="color:#1976d2; cursor:pointer; font-weight:500;">
                        ${params.data.client_id} · ${params.value}
                    </span>
                `
            """,
        },
        {
            "headerName": "Рейтинг",
            "field": "stars",
            "sortable": True,
            "filter": "agNumberColumnFilter",
            "minWidth": 120,
            "maxWidth": 140,
            ":cellRenderer": rating_aggrid_cell_renderer(),
        },
        {"headerName": "Филиал", "field": "client_group", "sortable": True, "filter": True, "minWidth": 130},
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
    ]

    due_today_col = {
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
    }

    due_soon_col = {
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
    }

    if is_due_today_page:
        client_columns.extend([due_today_col, due_soon_col])
    else:
        client_columns.extend([due_soon_col, due_today_col])

    client_columns.extend([
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
    ])

    grid = ui.aggrid({
        "columnDefs": client_columns,
        "rowData": prepare_rows(),
        "defaultColDef": {"resizable": True, "sortable": True, "filter": True},
        "pagination": True,
        "paginationPageSize": 20,
        "domLayout": "autoHeight",
    }).classes("w-full")

    def open_client_card_from_grid(event):
        args = event.args or {}
        data = args.get("data") or {}

        col_id = (
            args.get("colId")
            or (args.get("column") or {}).get("colId")
            or (args.get("colDef") or {}).get("field")
        )

        if col_id == "client_name" and data.get("client_id"):
            origin = "due-today" if mode == "today" else "due-soon"
            ui.navigate.to(f"/client/{data['client_id']}?from={origin}")

    grid.on("cellClicked", open_client_card_from_grid)
    search_input.on_value_change(lambda _: apply_filters())


@ui.page("/due-today")
def due_today_page():
    render_forecast_page("today")


@ui.page("/due-soon")
def due_soon_page():
    render_forecast_page("soon")
