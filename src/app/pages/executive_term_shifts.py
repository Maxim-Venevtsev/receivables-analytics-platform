from pathlib import Path
import os

import pandas as pd
from dotenv import load_dotenv
from nicegui import ui
from sqlalchemy import create_engine, text

from src.app.components.navigation import top_navigation
from src.app.components.kpi_cards import money
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


def compact_kpi(title: str, value: str, subtitle: str = ""):
    with ui.card().classes("w-60 h-32 p-4"):
        with ui.column().classes("w-full h-full items-center justify-between text-center"):
            ui.label(title).classes("text-sm text-gray-500 h-6 flex items-center justify-center")
            ui.label(value).classes("text-2xl font-bold h-10 flex items-center justify-center")
            ui.label(subtitle).classes("text-sm text-gray-500 h-8 flex items-center justify-center")


@ui.page("/executive/term-shifts")
def executive_term_shifts_page():
    ui.label("Переносы сроков оплаты").classes("text-3xl font-bold mb-2")
    ui.label(
        "Контроль клиентов и накладных, по которым сроки оплаты увеличивались между срезами"
    ).classes("text-gray-500 mb-4")

    top_navigation()

    ui.button(
        "← Вернуться к Сводке",
        on_click=lambda: ui.navigate.to("/executive"),
    ).props("flat color=primary").classes("mb-4")

    kpi_df = query_df("""
        SELECT *
        FROM core.v_executive_term_shift_kpi
    """)

    clients = query_df("""
        SELECT
            s.*,
            r.stars
        FROM core.v_client_term_shift_summary s
        LEFT JOIN core.v_client_rating r
            ON s.client_id = r.client_id
        ORDER BY
            s.total_term_shift_pressure_index DESC,
            s.term_shift_count DESC,
            s.shifted_amount DESC
    """)

    invoices = query_df("""
        SELECT
            s.*,
            r.stars
        FROM core.v_term_shift_invoice_summary s
        LEFT JOIN core.v_client_rating r
            ON s.client_id = r.client_id
        ORDER BY
            s.term_shift_pressure_index DESC,
            s.term_shift_count DESC,
            s.invoice_amount DESC
    """)

    if clients.empty or kpi_df.empty:
        ui.label("Переносов сроков оплаты не обнаружено.").classes("text-green-700 text-lg")
        return

    kpi = kpi_df.iloc[0]

    clients["stars_int"] = clients["stars"].round().fillna(0).astype(int)
    invoices["stars_int"] = invoices["stars"].round().fillna(0).astype(int)

    clients_with_5_plus = int((clients["term_shift_count"] >= 5).sum())
    clients_with_10_plus = int((clients["term_shift_count"] >= 10).sum())

    with ui.row().classes("gap-4 mb-6"):
        compact_kpi("Клиентов с переносами", str(int(kpi["clients_with_term_shifts"])))
        compact_kpi("Событий переноса", str(int(kpi["term_shift_events_count"])))
        compact_kpi("Накладных", str(int(kpi["shifted_invoice_count"])))
        compact_kpi("Сумма долга", money(float(kpi["shifted_amount"] or 0)))
        compact_kpi("Макс. рост срока", f"{int(kpi['max_term_delta_days'])} дней")
        compact_kpi("Клиентов с 5+ переносами", str(clients_with_5_plus), f"10+: {clients_with_10_plus}")

    with ui.card().classes("w-full p-4 mb-3"):
        ui.label("Клиенты с переносами сроков оплаты").classes("text-xl font-bold mb-1")
        ui.label(
            "Повторные переносы сроков могут указывать на ползучую неплатежеспособность или ручное удержание риска в зеленой зоне."
        ).classes("text-sm text-gray-500")

    grid_clients = ui.aggrid({
        "columnDefs": [
            {
                "headerName": "Клиент",
                "field": "client_name",
                "sortable": True,
                "filter": True,
                "minWidth": 320,
                ":cellRenderer": """
                    params => `
                        <span style="color:#1976d2; cursor:pointer; font-weight:600;">
                            ${params.data.client_id} · ${params.value}
                        </span>
                    `
                """,
            },
            {"headerName": "Филиал", "field": "client_group", "sortable": True, "filter": True, "minWidth": 140},
            {
                "headerName": "Рейтинг",
                "field": "stars_int",
                "sortable": True,
                "filter": "agNumberColumnFilter",
                "minWidth": 120,
                "maxWidth": 140,
                ":cellRenderer": rating_aggrid_cell_renderer(),
            },
            {
                "headerName": "Переносов",
                "field": "term_shift_count",
                "sortable": True,
                "filter": "agNumberColumnFilter",
                "type": "rightAligned",
                "minWidth": 130,
                ":cellRenderer": """
                    params => {
                        const value = params.value || 0;
                        const color = value >= 10 ? '#991b1b' : value >= 5 ? '#dc2626' : value >= 3 ? '#f97316' : '#ca8a04';
                        return `<span style="color:${color}; font-weight:700;">${value}</span>`;
                    }
                """,
            },
            {
                "headerName": "Накладных",
                "field": "shifted_invoice_count",
                "sortable": True,
                "filter": "agNumberColumnFilter",
                "type": "rightAligned",
                "minWidth": 130,
            },
            {
                "headerName": "Сумма",
                "field": "shifted_amount",
                "sortable": True,
                "filter": "agNumberColumnFilter",
                "type": "rightAligned",
                "minWidth": 150,
                ":valueFormatter": "params => params.value == null ? '' : Math.round(params.value).toLocaleString('ru-RU')",
            },
            {
                "headerName": "Повторные переносы",
                "field": "repeated_shift_amount",
                "sortable": True,
                "filter": "agNumberColumnFilter",
                "type": "rightAligned",
                "minWidth": 180,
                ":valueFormatter": "params => params.value == null ? '' : Math.round(params.value).toLocaleString('ru-RU')",
            },
            {
                "headerName": "Макс. рост",
                "field": "max_current_term_delta_days",
                "sortable": True,
                "filter": "agNumberColumnFilter",
                "type": "rightAligned",
                "minWidth": 140,
                ":cellRenderer": """
                    params => {
                        const value = params.value || 0;
                        const color = value >= 60 ? '#991b1b' : value >= 30 ? '#dc2626' : value >= 14 ? '#f97316' : '#ca8a04';
                        return `<span style="color:${color}; font-weight:700;">+${value}</span>`;
                    }
                """,
            },
            {
                "headerName": "Макс. срок",
                "field": "max_current_payment_term_days",
                "sortable": True,
                "filter": "agNumberColumnFilter",
                "type": "rightAligned",
                "minWidth": 140,
                ":cellRenderer": """
                    params => {
                        const value = params.value || 0;
                        const color = value >= 120 ? '#991b1b' : value >= 90 ? '#dc2626' : value >= 60 ? '#f97316' : '#ca8a04';
                        return `<span style="color:${color}; font-weight:700;">${value}</span>`;
                    }
                """,
            },
            {
                "headerName": "Последний перенос",
                "field": "last_shift_date",
                "sortable": True,
                "filter": True,
                "minWidth": 160,
                ":valueFormatter": """
                    params => {
                        if (!params.value) return '';
                        const d = new Date(params.value);
                        return d.toLocaleDateString('ru-RU');
                    }
                """,
            },
            {
                "headerName": "Риск",
                "field": "client_term_shift_risk_level",
                "sortable": True,
                "filter": True,
                "minWidth": 140,
                ":cellRenderer": """
                    params => {
                        const value = params.value || '';
                        const color = value === 'CRITICAL' ? '#991b1b'
                            : value === 'HIGH' ? '#dc2626'
                            : value === 'MEDIUM' ? '#f97316'
                            : '#ca8a04';
                        return `<span style="color:${color}; font-weight:700;">${value}</span>`;
                    }
                """,
            },
        ],
        "rowData": clients.to_dict("records"),
        "defaultColDef": {"resizable": True, "sortable": True, "filter": True},
        "pagination": True,
        "paginationPageSize": 30,
    }).classes("w-full h-[620px] mb-6")

    def open_client_card_from_grid(event):
        args = event.args or {}
        data = args.get("data") or {}
        col_id = (
            args.get("colId")
            or (args.get("column") or {}).get("colId")
            or (args.get("colDef") or {}).get("field")
        )

        if col_id == "client_name" and data.get("client_id"):
            ui.navigate.to(
                f"/client/{data['client_id']}?from=executive-term-shifts"
            )

    grid_clients.on("cellClicked", open_client_card_from_grid)

    with ui.card().classes("w-full p-4 mb-3"):
        ui.label("Накладные с измененными сроками оплаты").classes("text-xl font-bold mb-1")
        ui.label(
            "Детализация по накладным: сколько раз срок менялся, насколько он вырос и какой текущий срок оплаты."
        ).classes("text-sm text-gray-500")

    grid_invoices = ui.aggrid({
        "columnDefs": [
            {
                "headerName": "Клиент",
                "field": "client_name",
                "sortable": True,
                "filter": True,
                "minWidth": 300,
                ":cellRenderer": """
                    params => `
                        <span style="color:#1976d2; cursor:pointer; font-weight:600;">
                            ${params.data.client_id} · ${params.value}
                        </span>
                    `
                """,
            },
            {"headerName": "Филиал", "field": "client_group", "sortable": True, "filter": True, "minWidth": 140},
            {
                "headerName": "Рейтинг",
                "field": "stars_int",
                "sortable": True,
                "filter": "agNumberColumnFilter",
                "minWidth": 120,
                "maxWidth": 140,
                ":cellRenderer": rating_aggrid_cell_renderer(),
            },
            {"headerName": "Печ. номер", "field": "print_invoice_number", "sortable": True, "filter": True, "minWidth": 150},
            {"headerName": "Номер заказа", "field": "order_number", "sortable": True, "filter": True, "minWidth": 150},
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
                "headerName": "Переносов",
                "field": "term_shift_count",
                "sortable": True,
                "filter": "agNumberColumnFilter",
                "type": "rightAligned",
                "minWidth": 130,
                ":cellRenderer": """
                    params => {
                        const value = params.value || 0;
                        const color = value >= 4 ? '#991b1b' : value >= 3 ? '#dc2626' : value >= 2 ? '#f97316' : '#ca8a04';
                        return `<span style="color:${color}; font-weight:700;">${value}</span>`;
                    }
                """,
            },
            {
                "headerName": "Было",
                "field": "original_payment_term_days",
                "sortable": True,
                "filter": "agNumberColumnFilter",
                "type": "rightAligned",
                "minWidth": 110,
            },
            {
                "headerName": "Стало",
                "field": "current_payment_term_days",
                "sortable": True,
                "filter": "agNumberColumnFilter",
                "type": "rightAligned",
                "minWidth": 110,
            },
            {
                "headerName": "Рост",
                "field": "current_term_delta_days",
                "sortable": True,
                "filter": "agNumberColumnFilter",
                "type": "rightAligned",
                "minWidth": 110,
                ":cellRenderer": """
                    params => {
                        const value = params.value || 0;
                        const color = value >= 60 ? '#991b1b' : value >= 30 ? '#dc2626' : value >= 14 ? '#f97316' : '#ca8a04';
                        return `<span style="color:${color}; font-weight:700;">+${value}</span>`;
                    }
                """,
            },
            {
                "headerName": "Первый срез",
                "field": "first_seen_snapshot",
                "sortable": True,
                "filter": True,
                "minWidth": 140,
                ":valueFormatter": """
                    params => {
                        if (!params.value) return '';
                        const d = new Date(params.value);
                        return d.toLocaleDateString('ru-RU');
                    }
                """,
            },
            {
                "headerName": "Последний срез",
                "field": "last_seen_snapshot",
                "sortable": True,
                "filter": True,
                "minWidth": 140,
                ":valueFormatter": """
                    params => {
                        if (!params.value) return '';
                        const d = new Date(params.value);
                        return d.toLocaleDateString('ru-RU');
                    }
                """,
            },
            {
                "headerName": "Последний перенос",
                "field": "last_shift_date",
                "sortable": True,
                "filter": True,
                "minWidth": 160,
                ":valueFormatter": """
                    params => {
                        if (!params.value) return '';
                        const d = new Date(params.value);
                        return d.toLocaleDateString('ru-RU');
                    }
                """,
            },
            {
                "headerName": "Риск",
                "field": "term_shift_risk_level",
                "sortable": True,
                "filter": True,
                "minWidth": 140,
                ":cellRenderer": """
                    params => {
                        const value = params.value || '';
                        const color = value === 'CRITICAL' ? '#991b1b'
                            : value === 'HIGH' ? '#dc2626'
                            : value === 'MEDIUM' ? '#f97316'
                            : '#ca8a04';
                        return `<span style="color:${color}; font-weight:700;">${value}</span>`;
                    }
                """,
            },
        ],
        "rowData": invoices.to_dict("records"),
        "defaultColDef": {"resizable": True, "sortable": True, "filter": True},
        "pagination": True,
        "paginationPageSize": 50,
    }).classes("w-full h-[620px] mb-6")

    def open_client_card_from_invoice_grid(event):
        args = event.args or {}
        data = args.get("data") or {}

        col_id = (
            args.get("colId")
            or (args.get("column") or {}).get("colId")
            or (args.get("colDef") or {}).get("field")
        )

        if col_id == "client_name" and data.get("client_id"):
            ui.navigate.to(
                f"/client/{data['client_id']}?from=executive-term-shifts"
            )


    grid_invoices.on(
        "cellClicked",
        open_client_card_from_invoice_grid,
    )