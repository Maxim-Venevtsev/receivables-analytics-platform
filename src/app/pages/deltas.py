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


def signed_money(value) -> str:
    if pd.isna(value):
        return "0"
    number = float(value)
    sign = "+" if number > 0 else ""
    return f"{sign}{number:,.0f}".replace(",", " ")


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


@ui.page("/deltas")
def deltas_page():
    ui.label("Динамика дебиторки").classes("text-3xl font-bold mb-2")

    with ui.row().classes("mb-4"):
        ui.button("📊 Dashboard", on_click=lambda: ui.navigate.to("/")).props("flat color=primary")
        ui.button("📈 Динамика", on_click=lambda: ui.navigate.to("/deltas")).props("flat color=primary")
        ui.button("🔴 Просрочено", on_click=lambda: ui.navigate.to("/overdue")).props("flat color=negative")

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
            report_generated_date,
            client_id,
            client_name,
            client_group,
            previous_total_debt,
            total_debt,
            total_debt_delta,
            debt_change_status
        FROM core.v_client_deltas
        WHERE previous_total_debt IS NOT NULL
        ORDER BY report_generated_date DESC, ABS(total_debt_delta) DESC
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

    def prepare_branch_rows():
        df = normalize_numeric_columns(branches)

        if selected_branches:
            df = df[df["client_group"].isin(selected_branches)]

        df["total_debt_fmt"] = df["total_debt"].apply(money)
        df["overdue_debt_fmt"] = df["overdue_debt"].apply(money)
        df["overdue_share_fmt"] = df["overdue_share_pct"].apply(percent)

        return df.to_dict("records")

    def prepare_delta_rows(search_text: str = ""):
        df = normalize_numeric_columns(deltas)

        if selected_branches:
            df = df[df["client_group"].isin(selected_branches)]

        search_text = (search_text or "").strip().lower()
        if search_text:
            df = df[
                df["client_id"].astype(str).str.lower().str.contains(search_text, na=False)
                | df["client_name"].astype(str).str.lower().str.contains(search_text, na=False)
            ]

        return df.to_dict("records")

    # KPI
    df_kpi = normalize_numeric_columns(deltas)
    increased_count = int((df_kpi["total_debt_delta"] > 0).sum())
    decreased_count = int((df_kpi["total_debt_delta"] < 0).sum())
    unchanged_count = int((df_kpi["total_debt_delta"] == 0).sum())

    total_increase = df_kpi.loc[df_kpi["total_debt_delta"] > 0, "total_debt_delta"].sum()
    total_decrease = df_kpi.loc[df_kpi["total_debt_delta"] < 0, "total_debt_delta"].sum()

    with ui.row().classes("gap-4"):
        kpi_card("Долг вырос", money(total_increase), f"{increased_count} клиентов")
        kpi_card("Долг снизился", money(abs(total_decrease)), f"{decreased_count} клиентов")
        kpi_card("Без изменений", str(unchanged_count), "клиентов")
        kpi_card("Строк в анализе", str(len(df_kpi)), "изменения по клиентам")

    ui.separator().classes("my-4")

    # Branch filter block
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

    ui.label("Изменения по клиентам").classes("text-xl mt-6")

    with ui.row().classes("items-center gap-4 mb-2"):
        search_input = ui.input(
            label="Поиск клиента по ID или названию",
            placeholder="Например: Регинас или 2755",
        ).props("clearable").classes("w-96")

    delta_grid = ui.aggrid({
        "columnDefs": [
            {
                "headerName": "Дата",
                "field": "report_generated_date",
                "sortable": True,
                "filter": True,
                "minWidth": 130,
            },
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

        delta_grid.options["rowData"] = prepare_delta_rows(search_input.value)
        delta_grid.update()

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
        col_def = args.get("colDef") or {}

        if col_def.get("field") == "client_name" and data.get("client_id"):
            ui.navigate.to(f"/client/{data['client_id']}")

    branch_table.on("branch_click", select_branch_from_table)
    delta_grid.on("cellClicked", open_client_card_from_grid)
    search_input.on_value_change(lambda _: apply_filters())