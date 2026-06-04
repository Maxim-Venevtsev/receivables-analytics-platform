from pathlib import Path
import os

import pandas as pd
from dotenv import load_dotenv
from nicegui import ui
from sqlalchemy import create_engine, text

from src.app.components.navigation import top_navigation
from src.app.components.kpi_cards import money
from src.app.components.charts import build_long_green_exposure_chart
from src.app.components.rating_stars import rating_aggrid_cell_renderer


PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env")

engine = create_engine(
    f"postgresql+psycopg2://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@"
    f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)


def query_df(sql: str, params: dict | None = None) -> pd.DataFrame:
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn, params=params)


def date_fmt(value) -> str:
    if pd.isna(value):
        return ""
    return pd.to_datetime(value).strftime("%d.%m.%Y")


def rating_fmt(stars):
    if pd.isna(stars):
        return "—"
    return f"{int(stars)}★"


def compact_kpi(title: str, value: str, subtitle: str = ""):
    with ui.card().classes("w-56 h-32 p-4"):
        with ui.column().classes("w-full h-full items-center justify-between text-center"):
            ui.label(title).classes("text-sm text-gray-500 h-6 flex items-center justify-center")
            ui.label(value).classes("text-2xl font-bold h-10 flex items-center justify-center")
            ui.label(subtitle).classes("text-sm text-gray-500 h-8 flex items-center justify-center")


@ui.page("/executive/long-green")
def executive_long_green_page():
    ui.label("Длинная непросроченная задолженность").classes("text-3xl font-bold mb-2")
    ui.label(
        "Контроль клиентов с длинными сроками оплаты при отсутствии формальной просрочки"
    ).classes("text-gray-500 mb-4")

    top_navigation()

    ui.button(
        "← Вернуться к Сводке",
        on_click=lambda: ui.navigate.to("/executive"),
    ).props("flat color=primary").classes("mb-4")

    long_green_clients = query_df("""
        SELECT *
        FROM core.v_executive_long_green_clients
    """)

    long_green_invoices = query_df("""
        SELECT *
        FROM core.v_executive_long_green_invoices
    """)

    long_green_history = query_df("""
        SELECT *
        FROM core.v_executive_long_green_exposure
        ORDER BY report_generated_date
    """)

    if long_green_clients.empty:
        ui.label(
            "Клиентов с длинной непросроченной задолженностью не обнаружено."
        ).classes("text-green-700 text-lg")
        return

    total_45 = float(long_green_clients["green_45_plus_debt"].sum())
    total_90 = float(long_green_clients["green_90_plus_debt"].sum())
    total_120 = float(long_green_clients["green_120_plus_debt"].sum())
    max_term = int(long_green_clients["max_payment_term_days"].max())
    client_count = int(long_green_clients["client_id"].nunique())
    branch_count = int(long_green_clients["client_group"].nunique())

    with ui.row().classes("gap-4 mb-6"):
        compact_kpi("Клиентов под контролем", str(client_count))
        compact_kpi("Филиалов", str(branch_count))
        compact_kpi("45+ дней", money(total_45))
        compact_kpi("90+ дней", money(total_90))
        compact_kpi("120+ дней", money(total_120))
        compact_kpi("Макс. отсрочка", f"{max_term} дней")

    with ui.card().classes("w-full p-4 mb-6"):
        ui.label("Динамика длинной непросроченной задолженности").classes(
            "text-xl font-bold mb-3"
        )
        ui.plotly(build_long_green_exposure_chart(long_green_history)).classes("w-full")

    filtered_clients = long_green_clients.copy()
    filtered_clients["rating_display"] = filtered_clients["stars"].apply(rating_fmt)

    with ui.card().classes("w-full p-4 mb-6"):
        ui.label("Клиенты с длинной непросроченной задолженностью").classes(
            "text-xl font-bold mb-3"
        )

    grid_clients = ui.aggrid({
        "columnDefs": [
            {
                "headerName": "Клиент",
                "field": "client_name",
                "sortable": True,
                "filter": True,
                "minWidth": 300,
                ":cellRenderer": """
                    params => `
                        <span style="color:#1976d2; cursor:pointer; font-weight:500;">
                            ${params.data.client_id} · ${params.value}
                        </span>
                    `
                """,
            },
            {"headerName": "Филиал", "field": "client_group", "sortable": True, "filter": True, "minWidth": 140},
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
                "headerName": "45+",
                "field": "green_45_plus_debt",
                "sortable": True,
                "filter": "agNumberColumnFilter",
                "type": "rightAligned",
                "minWidth": 130,
                ":valueFormatter": "params => params.value == null ? '' : Math.round(params.value).toLocaleString('ru-RU')",
            },
            {
                "headerName": "60+",
                "field": "green_60_plus_debt",
                "sortable": True,
                "filter": "agNumberColumnFilter",
                "type": "rightAligned",
                "minWidth": 130,
                ":valueFormatter": "params => params.value == null ? '' : Math.round(params.value).toLocaleString('ru-RU')",
            },
            {
                "headerName": "90+",
                "field": "green_90_plus_debt",
                "sortable": True,
                "filter": "agNumberColumnFilter",
                "type": "rightAligned",
                "minWidth": 130,
                ":cellRenderer": """
                    params => {
                        const value = params.value || 0;
                        const color = value > 0 ? '#dc2626' : '#6b7280';
                        return `<span style="color:${color}; font-weight:600;">${Math.round(value).toLocaleString('ru-RU')}</span>`;
                    }
                """,
            },
            {
                "headerName": "120+",
                "field": "green_120_plus_debt",
                "sortable": True,
                "filter": "agNumberColumnFilter",
                "type": "rightAligned",
                "minWidth": 130,
                ":cellRenderer": """
                    params => {
                        const value = params.value || 0;
                        const color = value > 0 ? '#991b1b' : '#6b7280';
                        return `<span style="color:${color}; font-weight:700;">${Math.round(value).toLocaleString('ru-RU')}</span>`;
                    }
                """,
            },
            {
                "headerName": "Макс. отсрочка",
                "field": "max_payment_term_days",
                "sortable": True,
                "filter": "agNumberColumnFilter",
                "type": "rightAligned",
                "minWidth": 150,
                ":cellRenderer": """
                    params => {
                        const value = params.value || 0;
                        const color = value > 120 ? '#991b1b' : value > 90 ? '#dc2626' : value > 60 ? '#f97316' : '#ca8a04';
                        return `<span style="color:${color}; font-weight:700;">${value}</span>`;
                    }
                """,
            },
            {"headerName": "Накладных", "field": "invoice_count", "sortable": True, "filter": "agNumberColumnFilter", "type": "rightAligned", "minWidth": 120},
        ],
        "rowData": filtered_clients.to_dict("records"),
        "defaultColDef": {"resizable": True, "sortable": True, "filter": True},
        "pagination": True,
        "paginationPageSize": 25,
        }).classes("w-full h-[420px] mb-6")

    def open_client_card_from_grid(event):
        args = event.args or {}
        data = args.get("data") or {}
        col_id = (
            args.get("colId")
            or (args.get("column") or {}).get("colId")
            or (args.get("colDef") or {}).get("field")
        )

        if col_id == "client_name" and data.get("client_id"):
            ui.navigate.to(f"/client/{data['client_id']}?from=executive-long-green")

    grid_clients.on("cellClicked", open_client_card_from_grid)

    invoices = long_green_invoices.copy()
    invoices["invoice_date_fmt"] = invoices["invoice_date"].apply(date_fmt)
    invoices["due_date_fmt"] = invoices["due_date"].apply(date_fmt)

    with ui.card().classes("w-full p-4 mb-6"):
        ui.label("Накладные с длинной отсрочкой").classes("text-xl font-bold mb-3")

    ui.aggrid({
        "columnDefs": [
            {"headerName": "Клиент", "field": "client_name", "sortable": True, "filter": True, "minWidth": 300},
            {"headerName": "Филиал", "field": "client_group", "sortable": True, "filter": True, "minWidth": 140},
            {"headerName": "Рейтинг", "field": "rating_display_label", "sortable": True, "filter": True, "minWidth": 180},
            {"headerName": "Дата накладной", "field": "invoice_date_fmt", "sortable": True, "filter": True, "minWidth": 140},
            {"headerName": "Оплатить до", "field": "due_date_fmt", "sortable": True, "filter": True, "minWidth": 140},
            {
                "headerName": "Сумма",
                "field": "invoice_amount",
                "sortable": True,
                "filter": "agNumberColumnFilter",
                "type": "rightAligned",
                "minWidth": 140,
                ":valueFormatter": "params => params.value == null ? '' : Number(params.value).toLocaleString('ru-RU', {minimumFractionDigits: 2, maximumFractionDigits: 2})",
            },
            {
                "headerName": "Отсрочка, дней",
                "field": "payment_term_days",
                "sortable": True,
                "filter": "agNumberColumnFilter",
                "type": "rightAligned",
                "minWidth": 160,
                ":cellRenderer": """
                    params => {
                        const value = params.value || 0;
                        const color = value > 120 ? '#991b1b' : value > 90 ? '#dc2626' : value > 60 ? '#f97316' : '#ca8a04';
                        return `<span style="color:${color}; font-weight:700;">${value}</span>`;
                    }
                """,
            },
            {"headerName": "Корзина", "field": "payment_term_bucket", "sortable": True, "filter": True, "minWidth": 120},
            {"headerName": "Печ. номер", "field": "print_invoice_number", "sortable": True, "filter": True, "minWidth": 150},
            {"headerName": "Номер заказа", "field": "order_number", "sortable": True, "filter": True, "minWidth": 150},
        ],
        "rowData": invoices.to_dict("records"),
        "defaultColDef": {"resizable": True, "sortable": True, "filter": True},
        "pagination": True,
        "paginationPageSize": 50,
        }).classes("w-full h-[520px] mb-6")