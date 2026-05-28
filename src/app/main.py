from pathlib import Path
import os

import pandas as pd
from dotenv import load_dotenv
from nicegui import ui
from sqlalchemy import create_engine, text

from src.app.pages.deltas import deltas_page
from src.app.pages.overdue import overdue_page
from src.app.pages.client_card import client_card_page
from src.app.pages.forecast import due_today_page
from src.app.pages.parent_org_card import parent_org_card_page
from src.app.components.aging_bar import receivables_structure_bar
from src.app.components.branch_filter import create_branch_filter
from src.app.components.rating_stars import rating_aggrid_cell_renderer
from src.app.pages.branch_card import branch_card_page


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

    priority = query_df("""
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
        ORDER BY p.risk_score DESC
    """)

    priority["due_soon_only"] = (
        priority["due_in_3_days"] - priority["due_today"]
    ).clip(lower=0)

    branches = (
        priority.groupby("client_group", as_index=False)
        .agg(
            total_debt=("total_debt", "sum"),
            due_today=("due_today", "sum"),
            due_soon_only=("due_soon_only", "sum"),
            overdue_debt=("overdue_debt", "sum"),
        )
    )
    branches["overdue_share_pct"] = (
        branches["overdue_debt"] / branches["total_debt"] * 100
    ).fillna(0)

    selected_branches: list[str] = []

    def normalize_numeric_columns(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        for col in [
            "total_debt",
            "overdue_debt",
            "overdue_share_pct",
            "due_today",
            "due_soon_only",
        ]:
            if col in df.columns:
                df[col] = df[col].astype(float)
        return df

    def prepare_priority_rows(search_text: str = ""):
        df = normalize_numeric_columns(priority)

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

    def get_filtered_structure_amounts() -> dict[str, float]:
        df = normalize_numeric_columns(priority)

        if selected_branches:
            df = df[df["client_group"].isin(selected_branches)]

        total_debt = float(df["total_debt"].sum())
        overdue_debt = float(df["overdue_debt"].sum())
        due_today = float(df["due_today"].sum())
        due_soon_only = float(df["due_soon_only"].sum())

        normal_debt = max(
            total_debt - overdue_debt - due_today - due_soon_only,
            0,
        )

        return {
            "normal_debt": normal_debt,
            "due_soon_only": due_soon_only,
            "due_today": due_today,
            "overdue_debt": overdue_debt,
        }

    def get_filtered_kpi_metrics() -> dict[str, float | int]:
        df = normalize_numeric_columns(priority)

        if selected_branches:
            df = df[df["client_group"].isin(selected_branches)]

        total_debt = float(df["total_debt"].sum())
        overdue_debt = float(df["overdue_debt"].sum())
        due_today = float(df["due_today"].sum())
        due_soon_only = float(df["due_soon_only"].sum())

        overdue_share_pct = (overdue_debt / total_debt * 100) if total_debt else 0
        high_risk_client_count = int((df["risk_category"] == "HIGH").sum())

        return {
            "total_debt": total_debt,
            "due_today": due_today,
            "due_soon_only": due_soon_only,
            "overdue_debt": overdue_debt,
            "overdue_share_pct": overdue_share_pct,
            "high_risk_client_count": high_risk_client_count,
        }


    ui.label("АВС — Дебиторка").classes("text-3xl font-bold mb-2")
    ui.label("Operational Receivables Monitoring Platform") \
        .classes("text-subtitle1 text-grey-7 mb-4")

    with ui.row().classes("mb-4"):
        ui.button("📊 Главная", on_click=lambda: ui.navigate.to("/")).props("flat color=primary")
        ui.button("📈 Динамика", on_click=lambda: ui.navigate.to("/deltas")).props("flat color=primary")
        ui.button("🔴 Просрочено", on_click=lambda: ui.navigate.to("/overdue")).props("flat color=negative")
        ui.button("🟠 К оплате сегодня", on_click=lambda: ui.navigate.to("/due-today")).props("flat color=warning")
        ui.button("🟡 Ближайшие 3 дня", on_click=lambda: ui.navigate.to("/due-soon")).props("flat color=warning")

    with ui.row().classes("gap-4"):
        initial_kpi = get_filtered_kpi_metrics()

        with ui.card().classes("w-64 h-36 p-4"):
            with ui.column().classes("w-full h-full items-center justify-between text-center"):
                ui.label("Общая задолженность").classes("text-sm text-gray-500 h-6 flex items-center justify-center")
                total_debt_label = ui.label(money(initial_kpi["total_debt"])).classes(
                    "text-2xl font-bold h-10 flex items-center justify-center"
                )
                ui.label("").classes("text-sm text-gray-500 h-8 flex items-center justify-center")

        with ui.card().classes("w-64 h-36 p-4 cursor-pointer hover:shadow-lg").on(
            "click", lambda: ui.navigate.to("/due-today")
        ):
            with ui.column().classes("w-full h-full items-center justify-between text-center"):
                ui.label("К оплате сегодня").classes("text-sm text-gray-500 h-6 flex items-center justify-center")
                due_today_label = ui.label(money(initial_kpi["due_today"])).classes(
                    "text-2xl font-bold h-10 flex items-center justify-center"
                )
                ui.label("согласно срокам оплаты").classes("text-sm text-gray-500 h-8 flex items-center justify-center")

        with ui.card().classes("w-64 h-36 p-4 cursor-pointer hover:shadow-lg").on(
            "click", lambda: ui.navigate.to("/due-soon")
        ):
            with ui.column().classes("w-full h-full items-center justify-between text-center"):
                ui.label("К оплате в ближайшие дни").classes("text-sm text-gray-500 h-6 flex items-center justify-center")
                due_soon_label = ui.label(money(initial_kpi["due_soon_only"])).classes(
                    "text-2xl font-bold h-10 flex items-center justify-center"
                )
                ui.label("в ближайшие 3 дня").classes("text-sm text-gray-500 h-8 flex items-center justify-center")

        with ui.card().classes("w-64 h-36 p-4 cursor-pointer hover:shadow-lg").on(
            "click", lambda: ui.navigate.to("/overdue")
        ):
            with ui.column().classes("w-full h-full items-center justify-between text-center"):
                ui.label("Просрочено").classes("text-sm text-gray-500 h-6 flex items-center justify-center")
                overdue_label = ui.label(money(initial_kpi["overdue_debt"])).classes(
                    "text-2xl font-bold h-10 flex items-center justify-center"
                )
                overdue_subtitle_label = ui.label(
                    f"{percent(initial_kpi['overdue_share_pct'])} от общей задолженности"
                ).classes("text-sm text-gray-500 h-8 flex items-center justify-center")

        with ui.card().classes("w-64 h-36 p-4"):
            with ui.column().classes("w-full h-full items-center justify-between text-center"):
                ui.label("Высокий риск").classes("text-sm text-gray-500 h-6 flex items-center justify-center")
                high_risk_label = ui.label(str(initial_kpi["high_risk_client_count"])).classes(
                    "text-2xl font-bold h-10 flex items-center justify-center"
                )
                ui.label("клиентов в красной зоне").classes("text-sm text-gray-500 h-8 flex items-center justify-center")

    def update_kpi_cards():
        metrics = get_filtered_kpi_metrics()

        total_debt_label.text = money(metrics["total_debt"])
        due_today_label.text = money(metrics["due_today"])
        due_soon_label.text = money(metrics["due_soon_only"])
        overdue_label.text = money(metrics["overdue_debt"])
        overdue_subtitle_label.text = f"{percent(metrics['overdue_share_pct'])} от общей задолженности"
        high_risk_label.text = str(metrics["high_risk_client_count"])

        total_debt_label.update()
        due_today_label.update()
        due_soon_label.update()
        overdue_label.update()
        overdue_subtitle_label.update()
        high_risk_label.update()

    structure_container = ui.column().classes("w-full")

    def render_structure_bar():
        amounts = get_filtered_structure_amounts()

        structure_container.clear()
        with structure_container:
            receivables_structure_bar(
                normal_amount=amounts["normal_debt"],
                due_soon_amount=amounts["due_soon_only"],
                due_today_amount=amounts["due_today"],
                overdue_amount=amounts["overdue_debt"],
            )

    render_structure_bar()

    branch_filter = create_branch_filter(
        branches=branches,
        selected_branches=selected_branches,
        on_change=lambda: apply_filters(),
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
        "defaultColDef": {"resizable": True, "sortable": True, "filter": True},
        "pagination": True,
        "paginationPageSize": 20,
        "domLayout": "autoHeight",
    }).classes("w-full")

    def apply_filters():
        branch_filter.update()

        update_kpi_cards()
        render_structure_bar()

        priority_grid.options["rowData"] = prepare_priority_rows(search_input.value)
        priority_grid.update()

    def open_client_card_from_grid(event):
        args = event.args or {}
        data = args.get("data") or {}

        col_id = (
            args.get("colId")
            or (args.get("column") or {}).get("colId")
            or (args.get("colDef") or {}).get("field")
        )

        if col_id == "client_name" and data.get("client_id"):
            ui.navigate.to(f"/client/{data['client_id']}?from=dashboard")

    priority_grid.on("cellClicked", open_client_card_from_grid)
    search_input.on_value_change(lambda _: apply_filters())


ui.run()