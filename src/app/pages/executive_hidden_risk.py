from pathlib import Path
import os

import pandas as pd
from dotenv import load_dotenv
from nicegui import ui
from sqlalchemy import create_engine, text

from src.app.components.navigation import top_navigation
from src.app.components.kpi_cards import money, percent
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


@ui.page("/executive/hidden-risk")
def executive_hidden_risk_page():
    ui.label("Скрытый риск").classes("text-3xl font-bold mb-2")
    ui.label(
        "Клиенты с формально непросроченной задолженностью, но с подозрительно длинными отсрочками"
    ).classes("text-gray-500 mb-4")

    top_navigation()

    ui.button(
        "← Вернуться к Сводке",
        on_click=lambda: ui.navigate.to("/executive"),
    ).props("flat color=primary").classes("mb-4")

    df = query_df("""
        SELECT *
        FROM core.v_executive_hidden_risk_clients
        ORDER BY
            green_120_plus_debt DESC,
            green_90_plus_debt DESC,
            max_payment_term_days DESC
    """)

    if df.empty:
        ui.label("Скрытых рисков не обнаружено.").classes("text-green-700 text-lg")
        return

    df["stars_int"] = df["stars"].round().fillna(0).astype(int)

    total_green = float(df["total_green_debt"].sum())
    total_60 = float(df["green_60_plus_debt"].sum())
    total_90 = float(df["green_90_plus_debt"].sum())
    total_120 = float(df["green_120_plus_debt"].sum())
    max_term = int(df["max_payment_term_days"].max())
    client_count = int(df["client_id"].nunique())
    low_rating_count = int((df["stars_int"] <= 3).sum())

    with ui.row().classes("gap-4 mb-6"):
        compact_kpi("Клиентов риска", str(client_count))
        compact_kpi("Низкий рейтинг", str(low_rating_count), "≤ 3★")
        compact_kpi("60+ непросрочено", money(total_60))
        compact_kpi("90+ непросрочено", money(total_90))
        compact_kpi("120+ непросрочено", money(total_120))
        compact_kpi("Макс. отсрочка", f"{max_term} дней")

    with ui.card().classes("w-full p-4 mb-3"):
        ui.label("Клиенты со скрытым риском").classes("text-xl font-bold mb-1")
        ui.label(
            "Основной фокус — сочетание длинной отсрочки, суммы долга и слабого рейтинга клиента."
        ).classes("text-sm text-gray-500")

    grid = ui.aggrid({
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
                "headerName": "Весь зеленый долг",
                "field": "total_green_debt",
                "sortable": True,
                "filter": "agNumberColumnFilter",
                "type": "rightAligned",
                "minWidth": 170,
                ":valueFormatter": "params => params.value == null ? '' : Math.round(params.value).toLocaleString('ru-RU')",
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
                ":cellRenderer": """
                    params => {
                        const value = params.value || 0;
                        const color = value > 0 ? '#f97316' : '#6b7280';
                        return `<span style="color:${color}; font-weight:600;">${Math.round(value).toLocaleString('ru-RU')}</span>`;
                    }
                """,
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
                        return `<span style="color:${color}; font-weight:700;">${Math.round(value).toLocaleString('ru-RU')}</span>`;
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
                "headerName": "% 90+",
                "field": "green_90_plus_share_pct",
                "sortable": True,
                "filter": "agNumberColumnFilter",
                "type": "rightAligned",
                "minWidth": 120,
                ":cellRenderer": """
                    params => {
                        const value = params.value || 0;
                        const color = value > 50 ? '#dc2626' : value > 20 ? '#f97316' : '#ca8a04';
                        return `<span style="color:${color}; font-weight:700;">${value.toFixed(1)}%</span>`;
                    }
                """,
            },
            {
                "headerName": "% 120+",
                "field": "green_120_plus_share_pct",
                "sortable": True,
                "filter": "agNumberColumnFilter",
                "type": "rightAligned",
                "minWidth": 120,
                ":cellRenderer": """
                    params => {
                        const value = params.value || 0;
                        const color = value > 0 ? '#991b1b' : '#6b7280';
                        return `<span style="color:${color}; font-weight:700;">${value.toFixed(1)}%</span>`;
                    }
                """,
            },
            {
                "headerName": "Макс. отсрочка",
                "field": "max_payment_term_days",
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
            {
                "headerName": "Уровень риска",
                "field": "hidden_risk_level",
                "sortable": True,
                "filter": True,
                "minWidth": 150,
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
            {"headerName": "Накладных", "field": "invoice_count", "sortable": True, "filter": "agNumberColumnFilter", "type": "rightAligned", "minWidth": 120},
        ],
        "rowData": df.to_dict("records"),
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
                f"/client/{data['client_id']}?from=executive-hidden-risk"
            )

    grid.on("cellClicked", open_client_card_from_grid)