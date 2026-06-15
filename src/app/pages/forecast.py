from pathlib import Path
import os
from urllib.parse import quote

import pandas as pd
from dotenv import load_dotenv
from nicegui import ui
from sqlalchemy import create_engine, text

from src.app.components.navigation import top_navigation
from src.app.components.rating_stars import rating_stars_html
from src.app.components.clients_table import render_clients_table


PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env")

engine = create_engine(
    f"postgresql+psycopg2://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@"
    f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)


def query_df(sql: str, params: dict | None = None) -> pd.DataFrame:
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn, params=params)


def money(value) -> str:
    if pd.isna(value):
        return "0"
    return f"{float(value):,.0f}".replace(",", " ")


def money_precise(value) -> str:
    if pd.isna(value):
        return "0,00"
    return f"{float(value):,.2f}".replace(",", " ").replace(".", ",")


def percent(value) -> str:
    if pd.isna(value):
        return "0%"
    return f"{float(value):.1f}%"


def compact_kpi(title: str, value: str, subtitle: str = "", color_class: str = "text-gray-900"):
    with ui.card().classes("w-64 h-36 p-4"):
        with ui.column().classes("w-full h-full items-center justify-between text-center"):
            ui.label(title).classes("text-sm text-gray-500 h-6 flex items-center justify-center")
            ui.label(value).classes(
                f"text-2xl font-bold h-10 flex items-center justify-center {color_class}"
            )
            ui.label(subtitle).classes("text-sm text-gray-500 h-8 flex items-center justify-center")


def table_page_props() -> str:
    return 'rows-per-page-options="[20, 50, 100]"'


def prepare_money_cols(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    result = df.copy()
    for col in cols:
        if col in result.columns:
            result[f"{col}_fmt"] = result[col].apply(money_precise)
    return result


def prepare_percent_cols(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    result = df.copy()
    for col in cols:
        if col in result.columns:
            result[f"{col}_fmt"] = result[col].apply(percent)
    return result


def add_branch_slots(table):
    table.add_slot(
        "body-cell-client_group",
        """
        <q-td :props="props" :style="props.row.is_dimmed ? 'opacity:0.45;' : ''">
            <q-btn
                dense
                :flat="!props.row.is_selected"
                :unelevated="props.row.is_selected"
                :outline="!props.row.is_selected"
                :color="props.row.is_selected ? 'primary' : 'grey-7'"
                :label="props.row.client_group"
                @click="$parent.$emit('branch_click', props.row.client_group)"
            />
        </q-td>
        """,
    )

    table.add_slot(
        "body-cell-rating",
        """
        <q-td :props="props" class="text-center" :style="props.row.is_dimmed ? 'opacity:0.45;' : ''">
            {{ props.row.weighted_rating_fmt }}
        </q-td>
        """,
    )

    for col in ["total_debt", "target_amount", "shifted_amount"]:
        table.add_slot(
            f"body-cell-{col}",
            f"""
            <q-td :props="props" class="text-right" :style="props.row.is_dimmed ? 'opacity:0.45;' : ''">
                {{{{ props.row.{col}_fmt }}}}
            </q-td>
            """,
        )

    table.add_slot(
        "body-cell-target_share_pct",
        """
        <q-td :props="props" class="text-right" :style="props.row.is_dimmed ? 'opacity:0.45;' : ''">
            <q-badge
                :color="props.row.target_share_pct > 20 ? 'red' : props.row.target_share_pct > 0 ? 'orange' : 'green'"
                :label="props.row.target_share_pct_fmt"
            />
        </q-td>
        """,
    )


def add_client_slots(table):
    table.add_slot(
        "body",
        """
        <q-tr :props="props">
            <q-td v-for="col in props.cols" :key="col.name" :props="props">

                <template v-if="col.name === 'client'">
                    <a :href="props.row.client_url" class="text-blue-600 hover:underline font-medium">
                        {{ props.row.client_display }}
                    </a>
                </template>

                <template v-else-if="col.name === 'rating'">
                    <span v-html="props.row.rating_html"></span>
                </template>

                <template v-else-if="['total_debt', 'target_amount', 'shifted_amount', 'overdue_debt'].includes(col.name)">
                    {{ props.row[col.name + '_fmt'] }}
                </template>

                <template v-else-if="col.name === 'target_share_pct'">
                    <q-badge
                        :color="props.row.target_share_pct > 20 ? 'red' : props.row.target_share_pct > 0 ? 'orange' : 'green'"
                        :label="props.row.target_share_pct_fmt"
                    />
                </template>

                <template v-else>
                    {{ col.value }}
                </template>

            </q-td>
        </q-tr>
        """,
    )


def load_forecast_data(mode: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    target_condition = (
        "i.is_due_today"
        if mode == "today"
        else "(i.is_due_in_3_days AND NOT i.is_due_today)"
    )

    target_amount_col = "due_today" if mode == "today" else "due_soon_only"

    clients_df = query_df(f"""
        WITH target_invoices AS (
            SELECT
                i.client_id,
                COUNT(*) FILTER (WHERE {target_condition}) AS target_invoice_count
            FROM core.v_invoice_detail i
            GROUP BY i.client_id
        )
        SELECT
            s.*,
            COALESCE(t.target_invoice_count, 0) AS target_invoice_count
        FROM core.v_client_operational_summary s
        LEFT JOIN target_invoices t
            ON s.client_id = t.client_id
        WHERE s.{target_amount_col} > 0
        ORDER BY
            s.{target_amount_col} DESC,
            s.shifted_amount DESC,
            s.total_debt DESC
    """)

    branches_df = query_df(f"""
        WITH branch_debt AS (
            SELECT
                i.client_group,

                SUM(i.invoice_amount) AS total_debt,

                SUM(CASE WHEN {target_condition} THEN i.invoice_amount ELSE 0 END) AS target_amount,

                SUM(
                    CASE
                        WHEN {target_condition}
                         AND COALESCE(ts.term_shift_count, 0) > 0
                        THEN i.invoice_amount
                        ELSE 0
                    END
                ) AS shifted_amount,

                COUNT(DISTINCT i.client_id) FILTER (WHERE {target_condition}) AS clients_to_control
            FROM core.v_invoice_detail i
            LEFT JOIN core.v_term_shift_invoice_summary ts
                ON i.client_id = ts.client_id
               AND i.print_invoice_number = ts.print_invoice_number
               AND i.order_number = ts.order_number
               AND i.invoice_date = ts.invoice_date
            GROUP BY i.client_group
        )
        SELECT
            b.client_group,
            bh.weighted_rating,

            b.total_debt,
            b.target_amount,
            b.shifted_amount,
            b.clients_to_control,

            ROUND(b.target_amount / NULLIF(b.total_debt, 0) * 100, 2) AS target_share_pct
        FROM branch_debt b
        LEFT JOIN core.v_executive_branch_health bh
            ON b.client_group = bh.client_group
        WHERE b.target_amount > 0
        ORDER BY b.target_amount DESC
    """)

    return clients_df, branches_df


def render_forecast_page(mode: str):
    is_today = mode == "today"

    page_title = "К оплате сегодня" if is_today else "К оплате в ближайшие три дня"
    target_label = "К оплате сегодня" if is_today else "К оплате в ближайшие три дня"

    ui.label(page_title).classes("text-3xl font-bold mb-2")
    ui.label(
        "Клиенты и филиалы с накладными, которые требуют контроля по сроку оплаты."
    ).classes("text-gray-500 mb-4")

    top_navigation()

    clients_df, branches_df = load_forecast_data(mode)

    if clients_df.empty:
        message = (
            "На сегодня нет платежей к контролю."
            if is_today
            else "На ближайшие три дня нет платежей к контролю."
        )
        ui.label(message).classes("text-lg text-green-700")
        return

    selected_branches: list[str] = []

    money_cols = ["total_debt", "target_amount", "shifted_amount", "overdue_debt"]
    percent_cols = ["target_share_pct"]

    for frame in [clients_df, branches_df]:
        for col in money_cols + percent_cols + ["weighted_rating", "clients_to_control", "target_invoice_count"]:
            if col in frame.columns:
                frame[col] = frame[col].fillna(0).astype(float)

    clients_df = prepare_money_cols(clients_df, money_cols)
    clients_df = prepare_percent_cols(clients_df, percent_cols)

    branches_df = prepare_money_cols(branches_df, ["total_debt", "target_amount", "shifted_amount"])
    branches_df = prepare_percent_cols(branches_df, percent_cols)

    branches_df["weighted_rating_fmt"] = branches_df["weighted_rating"].apply(
        lambda value: "—" if pd.isna(value) else f"{float(value):.2f}"
    )

    def filtered_clients() -> pd.DataFrame:
        result = clients_df.copy()

        if selected_branches:
            result = result[result["client_group"].isin(selected_branches)]

        value = (search_input.value or "").strip().lower() if "search_input" in locals() else ""

        if value:
            result = result[
                result["client_id"].astype(str).str.lower().str.contains(value, na=False)
                | result["client_name"].astype(str).str.lower().str.contains(value, na=False)
            ]

        sort_amount_col = "due_today" if is_today else "due_soon_only"

        return result.sort_values(
            by=[sort_amount_col, "shifted_amount", "total_debt"],
            ascending=[False, False, False],
        )

    def filtered_branches() -> pd.DataFrame:
        result = branches_df.copy()
        result["is_selected"] = result["client_group"].isin(selected_branches)
        result["is_dimmed"] = bool(selected_branches) & ~result["is_selected"]
        return result

    def kpi_metrics() -> dict:
        bdf = branches_df.copy()

        if selected_branches:
            bdf = bdf[bdf["client_group"].isin(selected_branches)]

        cdf = clients_df.copy()

        if selected_branches:
            cdf = cdf[cdf["client_group"].isin(selected_branches)]

        total_debt = float(bdf["total_debt"].sum())
        target_amount = float(bdf["target_amount"].sum())
        shifted_amount = float(bdf["shifted_amount"].sum())

        return {
            "target_amount": target_amount,
            "target_share_pct": target_amount / total_debt * 100 if total_debt else 0,
            "client_count": int(cdf["client_id"].nunique()),
            "invoice_count": int(cdf["target_invoice_count"].sum()),
            "shifted_amount": shifted_amount,
        }

    k = kpi_metrics()

    with ui.row().classes("gap-4 mb-6"):
        compact_kpi(
            target_label,
            money(k["target_amount"]),
            f"{percent(k['target_share_pct'])} портфеля",
            "text-orange-700" if is_today else "text-yellow-700",
        )
        compact_kpi("Клиентов к контролю", str(k["client_count"]))
        compact_kpi("Накладных к контролю", str(k["invoice_count"]))
        compact_kpi("Переносы", money(k["shifted_amount"]), "по накладным в выборке", "text-red-700")

    ui.label("Сводка по филиалам").classes("text-xl font-bold mt-6 mb-1")
    ui.label(
        "Агрегация платежей к контролю по филиалам. "
        "Нажатие на филиал ограничивает клиентскую таблицу выбранным филиалом."
    ).classes("text-sm text-gray-500 mb-3")

    with ui.row().classes("items-center gap-4 mb-2"):
        selected_branch_label = ui.label("Показаны все филиалы").classes("text-sm text-gray-500")
        reset_branch_button = ui.button("ВСЕ ФИЛИАЛЫ").props("flat color=primary")

    branch_table = ui.table(
        columns=[
            {"name": "client_group", "label": "Филиал", "field": "client_group", "align": "left", "sortable": True},
            {"name": "rating", "label": "Рейтинг", "field": "weighted_rating", "align": "center", "sortable": True},
            {"name": "total_debt", "label": "Весь долг", "field": "total_debt", "align": "right", "sortable": True},
            {"name": "target_amount", "label": target_label, "field": "target_amount", "align": "right", "sortable": True},
            {"name": "target_share_pct", "label": "%", "field": "target_share_pct", "align": "right", "sortable": True},
            {"name": "shifted_amount", "label": "Переносы", "field": "shifted_amount", "align": "right", "sortable": True},
            {"name": "clients_to_control", "label": "Клиентов к контролю", "field": "clients_to_control", "align": "right", "sortable": True},
        ],
        rows=filtered_branches().to_dict("records"),
        pagination={"rowsPerPage": 20},
    ).classes("w-full mb-6")
    branch_table.props(table_page_props())
    add_branch_slots(branch_table)

    visible_columns = (
        [
            "client_group",
            "client",
            "rating",
            "total_debt",
            "due_today",
            "due_today_share_pct",
            "shifted_amount",
            "shifted_share_pct",
            "overdue_debt",
        ]
        if is_today
        else [
            "client_group",
            "client",
            "rating",
            "total_debt",
            "due_soon_only",
            "due_soon_share_pct",
            "shifted_amount",
            "shifted_share_pct",
            "overdue_debt",
        ]
    )

    client_table = render_clients_table(
        clients=filtered_clients(),
        title="Контрагенты",
        subtitle=None,
        show_branch=True,
        show_search=True,
        from_route="due-today" if is_today else "due-soon",
        visible_columns=visible_columns,
    )

    def apply_filters():
        if selected_branches:
            selected_branch_label.text = f"Фильтр: {', '.join(selected_branches)}"
        else:
            selected_branch_label.text = "Показаны все филиалы"

        selected_branch_label.update()

        branch_table.rows = filtered_branches().to_dict("records")
        branch_table.update()

        if client_table is not None:
            client_table.refresh_clients(filtered_clients())

    def toggle_branch(event):
        branch = event.args

        if branch in selected_branches:
            selected_branches.remove(branch)
        else:
            selected_branches.append(branch)

        apply_filters()

    def reset_branch_filter():
        selected_branches.clear()
        apply_filters()

    branch_table.on("branch_click", toggle_branch)
    reset_branch_button.on_click(reset_branch_filter)

    def open_client(event):
        origin = "due-today" if is_today else "due-soon"
        ui.navigate.to(f"/client/{event.args}?from={origin}")

    def open_branch(event):
        origin = "/due-today" if is_today else "/due-soon"
        ui.navigate.to(f"/branch/{quote(str(event.args))}?from={origin}")

    if client_table is not None:
        client_table.on("client_click", open_client)
        client_table.on("branch_click", open_branch)


@ui.page("/due-today")
def due_today_page():
    render_forecast_page("today")


@ui.page("/due-soon")
def due_soon_page():
    render_forecast_page("soon")