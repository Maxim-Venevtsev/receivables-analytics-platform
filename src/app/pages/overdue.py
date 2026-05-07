from pathlib import Path
import os

import pandas as pd
from dotenv import load_dotenv
from nicegui import ui
from sqlalchemy import create_engine, text
from src.app.components.navigation import top_navigation


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


@ui.page("/overdue")
def overdue_page():
    ui.label("Просроченная дебиторка").classes("text-3xl font-bold mb-2")

    top_navigation()

    df = query_df("""
        SELECT
            client_id,
            client_name,
            client_group,
            total_debt,
            overdue_debt,
            ROUND(overdue_debt / NULLIF(total_debt, 0) * 100, 2) AS overdue_share_pct,
            max_days_overdue,
            risk_category,
            recommended_action
        FROM core.v_client_priority
        WHERE overdue_debt > 0
        ORDER BY overdue_debt DESC
    """)

    if df.empty:
        ui.label("Просроченной задолженности нет.").classes("text-lg text-green-700")
        return

    branches = (
        df.groupby("client_group", as_index=False)
        .agg(
            total_debt=("total_debt", "sum"),
            overdue_debt=("overdue_debt", "sum"),
        )
    )
    branches["overdue_share_pct"] = branches["overdue_debt"] / branches["total_debt"] * 100

    selected_branches: list[str] = []

    def normalize_numeric_columns(source_df: pd.DataFrame) -> pd.DataFrame:
        result = source_df.copy()
        for col in ["total_debt", "overdue_debt", "overdue_share_pct", "max_days_overdue"]:
            if col in result.columns:
                result[col] = result[col].astype(float)
        return result

    def prepare_branch_rows():
        branch_df = normalize_numeric_columns(branches)

        if selected_branches:
            branch_df = branch_df[branch_df["client_group"].isin(selected_branches)]

        branch_df["total_debt_fmt"] = branch_df["total_debt"].apply(money)
        branch_df["overdue_debt_fmt"] = branch_df["overdue_debt"].apply(money)
        branch_df["overdue_share_fmt"] = branch_df["overdue_share_pct"].apply(percent)

        return branch_df.to_dict("records")

    def prepare_overdue_rows():
        overdue_df = normalize_numeric_columns(df)

        if selected_branches:
            overdue_df = overdue_df[overdue_df["client_group"].isin(selected_branches)]

        overdue_df["risk_fmt"] = overdue_df["risk_category"].apply(risk_badge)
        overdue_df["risk_order"] = overdue_df["risk_category"].apply(risk_order)

        return overdue_df.to_dict("records")

    total_overdue = df["overdue_debt"].sum()
    total_debt = df["total_debt"].sum()
    overdue_clients = df["client_id"].nunique()
    max_days = int(df["max_days_overdue"].max())

    with ui.row().classes("gap-4"):
        kpi_card("Просрочено", money(total_overdue))
        kpi_card("Клиентов с просрочкой", str(overdue_clients))
        kpi_card("% просрочки", percent(total_overdue / total_debt * 100 if total_debt else 0))
        kpi_card("Макс. дней просрочки", str(max_days))

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
            {"name": "overdue_debt", "label": "Просрочено", "field": "overdue_debt", "align": "right", "sortable": True},
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
                :color="props.row.overdue_share_pct > 50 ? 'red' : props.row.overdue_share_pct > 20 ? 'orange' : 'blue'"
                :label="props.row.overdue_share_fmt"
            />
        </q-td>
        """,
    )

    ui.label("Проблемные клиенты").classes("text-xl mt-6")

    overdue_grid = ui.aggrid({
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
                "headerName": "Просрочено",
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
                "headerName": "% просрочки",
                "field": "overdue_share_pct",
                "sortable": True,
                "filter": "agNumberColumnFilter",
                "type": "rightAligned",
                "minWidth": 140,
                ":cellRenderer": """
                    params => {
                        const value = params.value || 0;
                        const color = value > 50 ? '#dc2626' : value > 20 ? '#f59e0b' : '#2563eb';
                        return `<span style="color:${color}; font-weight:600;">${value.toFixed(1)}%</span>`;
                    }
                """,
            },
            {
                "headerName": "Макс. дней",
                "field": "max_days_overdue",
                "sortable": True,
                "filter": "agNumberColumnFilter",
                "type": "rightAligned",
                "minWidth": 120,
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
        "rowData": prepare_overdue_rows(),
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

        overdue_grid.options["rowData"] = prepare_overdue_rows()
        overdue_grid.update()

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
            ui.navigate.to(f"/client/{data['client_id']}?from=overdue")

    branch_table.on("branch_click", select_branch_from_table)
    overdue_grid.on("cellClicked", open_client_card_from_grid)