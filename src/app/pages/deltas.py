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


def percent(value) -> str:
    if pd.isna(value):
        return "0%"
    return f"{float(value):.1f}%"


@ui.page("/deltas")
def deltas_page():
    ui.label("Динамика дебиторки").classes("text-3xl font-bold mb-2")

    top_navigation()

    branches = query_df("""
        SELECT
            client_group,
            total_debt,
            overdue_debt,
            overdue_share_pct
        FROM core.v_branch_summary
        ORDER BY total_debt DESC
    """)

    deltas = query_df("""
        SELECT
            d.report_generated_date,
            d.client_id,
            d.client_name,
            r.stars,
            r.rating_display_label,
            r.confidence_level,
            d.client_group,
            d.previous_total_debt,
            d.total_debt,
            d.total_debt_delta,
            d.debt_change_status
        FROM core.v_client_deltas d
        LEFT JOIN core.v_client_rating r
            ON d.client_id = r.client_id
        WHERE d.previous_total_debt IS NOT NULL
        ORDER BY d.report_generated_date DESC, ABS(d.total_debt_delta) DESC
    """)

    deltas["debt_change_status"] = deltas["debt_change_status"].replace({
        "DEBT INCREASED": "Вырос",
        "DEBT DECREASED": "Уменьшился",
        "NO CHANGE": "Не изменился",
        "NEW IN SNAPSHOT": "Новый в срезе",
    })

    selected_branches: list[str] = []

    def normalize_numeric_columns(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        for col in [
            "total_debt",
            "overdue_debt",
            "overdue_share_pct",
            "previous_total_debt",
            "total_debt_delta",
        ]:
            if col in df.columns:
                df[col] = df[col].astype(float)
        return df

    def filtered_deltas() -> pd.DataFrame:
        df = normalize_numeric_columns(deltas)
        if selected_branches:
            df = df[df["client_group"].isin(selected_branches)]
        return df

    def prepare_delta_rows(search_text: str = ""):
        df = filtered_deltas()

        search_text = (search_text or "").strip().lower()
        if search_text:
            df = df[
                df["client_id"].astype(str).str.lower().str.contains(search_text, na=False)
                | df["client_name"].astype(str).str.lower().str.contains(search_text, na=False)
            ]

        return df.to_dict("records")

    def get_kpi_metrics() -> dict[str, float | int]:
        df = filtered_deltas()
        increased_count = int((df["total_debt_delta"] > 0).sum())
        decreased_count = int((df["total_debt_delta"] < 0).sum())
        unchanged_count = int((df["total_debt_delta"] == 0).sum())
        total_increase = float(df.loc[df["total_debt_delta"] > 0, "total_debt_delta"].sum())
        total_decrease = float(df.loc[df["total_debt_delta"] < 0, "total_debt_delta"].sum())

        return {
            "increased_count": increased_count,
            "decreased_count": decreased_count,
            "unchanged_count": unchanged_count,
            "total_increase": total_increase,
            "total_decrease_abs": abs(total_decrease),
            "rows_count": len(df),
        }

    initial_kpi = get_kpi_metrics()

    with ui.row().classes("gap-4"):
        with ui.card().classes("w-64 h-36 p-4"):
            with ui.column().classes("w-full h-full items-center justify-between text-center"):
                ui.label("Долг вырос").classes("text-sm text-gray-500 h-6 flex items-center justify-center")
                increased_value_label = ui.label(money(initial_kpi["total_increase"])).classes("text-2xl font-bold h-10 flex items-center justify-center")
                increased_subtitle_label = ui.label(f"{initial_kpi['increased_count']} клиентов").classes("text-sm text-gray-500 h-8 flex items-center justify-center")

        with ui.card().classes("w-64 h-36 p-4"):
            with ui.column().classes("w-full h-full items-center justify-between text-center"):
                ui.label("Долг снизился").classes("text-sm text-gray-500 h-6 flex items-center justify-center")
                decreased_value_label = ui.label(money(initial_kpi["total_decrease_abs"])).classes("text-2xl font-bold h-10 flex items-center justify-center")
                decreased_subtitle_label = ui.label(f"{initial_kpi['decreased_count']} клиентов").classes("text-sm text-gray-500 h-8 flex items-center justify-center")

        with ui.card().classes("w-64 h-36 p-4"):
            with ui.column().classes("w-full h-full items-center justify-between text-center"):
                ui.label("Без изменений").classes("text-sm text-gray-500 h-6 flex items-center justify-center")
                unchanged_value_label = ui.label(str(initial_kpi["unchanged_count"])).classes("text-2xl font-bold h-10 flex items-center justify-center")
                ui.label("клиентов").classes("text-sm text-gray-500 h-8 flex items-center justify-center")

        with ui.card().classes("w-64 h-36 p-4"):
            with ui.column().classes("w-full h-full items-center justify-between text-center"):
                ui.label("Строк в анализе").classes("text-sm text-gray-500 h-6 flex items-center justify-center")
                rows_count_label = ui.label(str(initial_kpi["rows_count"])).classes("text-2xl font-bold h-10 flex items-center justify-center")
                ui.label("изменения по клиентам").classes("text-sm text-gray-500 h-8 flex items-center justify-center")

    def update_kpi_cards():
        metrics = get_kpi_metrics()
        increased_value_label.text = money(metrics["total_increase"])
        increased_subtitle_label.text = f"{metrics['increased_count']} клиентов"
        decreased_value_label.text = money(metrics["total_decrease_abs"])
        decreased_subtitle_label.text = f"{metrics['decreased_count']} клиентов"
        unchanged_value_label.text = str(metrics["unchanged_count"])
        rows_count_label.text = str(metrics["rows_count"])

        increased_value_label.update()
        increased_subtitle_label.update()
        decreased_value_label.update()
        decreased_subtitle_label.update()
        unchanged_value_label.update()
        rows_count_label.update()

    branch_filter = None

    def apply_filters():
        branch_filter.update()
        update_kpi_cards()
        delta_grid.options["rowData"] = prepare_delta_rows(search_input.value)
        delta_grid.update()

    branch_columns = [
        {"name": "client_group", "label": "Филиал", "field": "client_group", "align": "left", "sortable": True},
        {"name": "total_debt", "label": "Долг", "field": "total_debt", "align": "right", "sortable": True},
        {"name": "overdue_debt", "label": "Просрочка", "field": "overdue_debt", "align": "right", "sortable": True},
        {"name": "overdue_share_pct", "label": "% просрочки", "field": "overdue_share_pct", "align": "right", "sortable": True},
    ]

    branch_filter = create_branch_filter(
        branches=branches,
        selected_branches=selected_branches,
        on_change=apply_filters,
        columns=branch_columns,
    )

    ui.label("Изменения по клиентам").classes("text-xl mt-6")

    with ui.row().classes("items-center gap-4 mb-2"):
        search_input = ui.input(
            label="Поиск клиента по ID или названию",
            placeholder="Например: Регинас или 2755",
        ).props("clearable").classes("w-96")

    delta_grid = ui.aggrid({
        "columnDefs": [
            {"headerName": "Дата", "field": "report_generated_date", "sortable": True, "filter": True, "minWidth": 130},
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
                "headerName": "Было",
                "field": "previous_total_debt",
                "sortable": True,
                "filter": "agNumberColumnFilter",
                "type": "rightAligned",
                "minWidth": 140,
                ":valueFormatter": """
                    params => params.value == null ? '' : Math.round(params.value).toLocaleString('ru-RU')
                """,
            },
            {
                "headerName": "Стало",
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
                "headerName": "Изменение",
                "field": "total_debt_delta",
                "sortable": True,
                "filter": "agNumberColumnFilter",
                "type": "rightAligned",
                "minWidth": 150,
                ":cellRenderer": """
                    params => {
                        const value = params.value || 0;
                        const formatted = Math.round(value).toLocaleString('ru-RU', {signDisplay: 'exceptZero'});
                        const color = value > 0 ? '#dc2626' : value < 0 ? '#16a34a' : '#6b7280';
                        return `<span style="color:${color}; font-weight:600;">${formatted}</span>`;
                    }
                """,
            },
            {
                "headerName": "Статус",
                "field": "debt_change_status",
                "sortable": True,
                "filter": True,
                "minWidth": 180,
                ":cellRenderer": """
                    params => {
                        const delta = params.data.total_debt_delta || 0;
                        const color = delta > 0 ? '#dc2626' : delta < 0 ? '#16a34a' : '#6b7280';
                        return `<span style="color:${color}; font-weight:600;">${params.value}</span>`;
                    }
                """,
            },
        ],
        "rowData": prepare_delta_rows(),
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
            ui.navigate.to(f"/client/{data['client_id']}?from=deltas")

    delta_grid.on("cellClicked", open_client_card_from_grid)
    search_input.on_value_change(lambda _: apply_filters())
