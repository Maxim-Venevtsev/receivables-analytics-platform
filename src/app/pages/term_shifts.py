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


def query_df(sql: str) -> pd.DataFrame:
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn)


def money(value) -> str:
    if pd.isna(value):
        return "0"
    return f"{float(value):,.0f}".replace(",", " ")


def money_precise(value) -> str:
    if pd.isna(value):
        return "0,00"
    return f"{float(value):,.2f}".replace(",", " ").replace(".", ",")


def date_fmt(value) -> str:
    if pd.isna(value):
        return ""
    return pd.to_datetime(value).strftime("%d.%m.%Y")


def compact_kpi(title: str, value: str, subtitle: str = "", color_class: str = "text-gray-900"):
    with ui.card().classes("w-64 h-36 p-4"):
        with ui.column().classes("w-full h-full items-center justify-between text-center"):
            ui.label(title).classes("text-sm text-gray-500 h-6 flex items-center justify-center")
            ui.label(value).classes(f"text-2xl font-bold h-10 flex items-center justify-center {color_class}")
            ui.label(subtitle).classes("text-sm text-gray-500 h-8 flex items-center justify-center")


def table_page_props() -> str:
    return 'rows-per-page-options="[20, 50, 100]"'


def prepare_money_cols(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    result = df.copy()
    for col in cols:
        if col in result.columns:
            result[f"{col}_fmt"] = result[col].apply(money_precise)
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

    for col in ["shifted_amount", "shift_once_amount", "shift_repeated_amount"]:
        table.add_slot(
            f"body-cell-{col}",
            f"""
            <q-td :props="props" class="text-right" :style="props.row.is_dimmed ? 'opacity:0.45;' : ''">
                {{{{ props.row.{col}_fmt }}}}
            </q-td>
            """,
        )


def add_client_slots(table):
    table.add_slot(
        "body",
        """
        <q-tr
            :props="props"
            :class="{
                'bg-red-50': props.row.shift_repeated_amount > 0,
                'bg-yellow-50': props.row.shift_repeated_amount <= 0 && props.row.shift_once_amount > 0
            }"
        >
            <q-td v-for="col in props.cols" :key="col.name" :props="props">

                <template v-if="col.name === 'client'">
                    <a :href="props.row.client_url" class="text-blue-600 hover:underline font-medium">
                        {{ props.row.client_display }}
                    </a>
                </template>

                <template v-else-if="col.name === 'rating'">
                    <span v-html="props.row.rating_html"></span>
                </template>

                <template v-else-if="['shifted_amount', 'shift_once_amount', 'shift_repeated_amount'].includes(col.name)">
                    {{ props.row[col.name + '_fmt'] }}
                </template>

                <template v-else>
                    {{ col.value }}
                </template>

            </q-td>
        </q-tr>
        """,
    )


@ui.page("/term-shifts")
def term_shifts_page():
    ui.label("Переносы сроков").classes("text-3xl font-bold mb-2")
    ui.label(
        "Активные накладные, по которым срок оплаты был перенесен. "
        "Разовые и повторные переносы выделены отдельно."
    ).classes("text-gray-500 mb-4")

    top_navigation()

    invoices = query_df("""
        SELECT
            i.client_id,
            i.client_name,
            i.client_group,
            i.invoice_amount,

            ts.term_shift_count,
            ts.current_term_delta_days,
            ts.total_shift_days,
            ts.max_single_shift_days,
            ts.last_shift_date,

            COALESCE(cq.credit_quality_stars, r.stars) AS stars,
            COALESCE(cq.credit_quality_display_label, r.rating_display_label) AS rating_display_label

        FROM core.v_invoice_detail i
        JOIN core.v_term_shift_invoice_summary ts
            ON i.client_id = ts.client_id
           AND i.print_invoice_number = ts.print_invoice_number
           AND i.order_number = ts.order_number
           AND i.invoice_date = ts.invoice_date
        LEFT JOIN core.v_client_rating r
            ON i.client_id = r.client_id
        LEFT JOIN core.v_client_credit_quality_rating cq
            ON i.client_id = cq.client_id
        WHERE COALESCE(ts.term_shift_count, 0) > 0
          AND i.invoice_amount > 0
    """)

    if invoices.empty:
        ui.label("Активных накладных с переносами сроков нет.").classes("text-lg text-green-700")
        return

    clients = query_df("""
        SELECT *
        FROM core.v_client_operational_summary
        WHERE shifted_amount > 0
        ORDER BY
            repeated_shift_amount DESC,
            shifted_amount DESC,
            term_shift_count DESC,
            total_debt DESC
    """)

    branches = (
        invoices
        .groupby("client_group", as_index=False)
        .agg(
            shifted_amount=("invoice_amount", "sum"),
            shift_once_amount=("invoice_amount", lambda s: s[invoices.loc[s.index, "term_shift_count"] == 1].sum()),
            shift_repeated_amount=("invoice_amount", lambda s: s[invoices.loc[s.index, "term_shift_count"] >= 2].sum()),
            clients_to_control=("client_id", "nunique"),
            shifted_invoice_count=("invoice_amount", "count"),
            total_shift_events=("term_shift_count", "sum"),
        )
    )

    branch_rating = query_df("""
        SELECT client_group, weighted_rating
        FROM core.v_executive_branch_health
    """)

    branches = branches.merge(branch_rating, on="client_group", how="left")

    selected_branches: list[str] = []

    money_cols = ["shifted_amount", "shift_once_amount", "shift_repeated_amount"]

    clients = prepare_money_cols(clients, money_cols)
    branches = prepare_money_cols(branches, money_cols)

    clients["last_shift_date_fmt"] = clients["last_shift_date"].apply(date_fmt)
    branches["weighted_rating_fmt"] = branches["weighted_rating"].apply(
        lambda value: "—" if pd.isna(value) else f"{float(value):.2f}"
    )

    def filtered_clients() -> pd.DataFrame:
        result = clients.copy()

        if selected_branches:
            result = result[result["client_group"].isin(selected_branches)]
        
        return result.sort_values(
            by=["repeated_shift_amount", "shifted_amount", "term_shift_count", "total_debt"],
            ascending=[False, False, False, False],
        )

    def filtered_branches() -> pd.DataFrame:
        result = branches.copy()
        result["is_selected"] = result["client_group"].isin(selected_branches)
        result["is_dimmed"] = bool(selected_branches) & ~result["is_selected"]
        return result.sort_values(
            by=["shift_repeated_amount", "shifted_amount"],
            ascending=[False, False],
        )

    def kpi_metrics() -> dict:
        cdf = filtered_clients()
        return {
            "shifted_amount": float(cdf["shifted_amount"].sum()),
            "clients": int(cdf["client_id"].nunique()),
            "invoices": int(cdf["shifted_invoice_count"].sum()),
            "shift_repeated_amount": float(cdf["repeated_shift_amount"].sum()),
            "events": int(cdf["term_shift_count"].sum()),
        }

    k = kpi_metrics()

    with ui.row().classes("gap-4 mb-6"):
        compact_kpi("Перенесено", money(k["shifted_amount"]), f"{k['clients']} клиентов", "text-orange-700")
        compact_kpi("Накладных", str(k["invoices"]))
        compact_kpi("Событий переноса", str(k["events"]))
        compact_kpi("Повторные переносы", money(k["shift_repeated_amount"]), "2+ переносов", "text-red-700")

    ui.label("Сводка по филиалам").classes("text-xl font-bold mt-6 mb-1")
    ui.label(
        "Агрегация активных переносов по филиалам. "
        "Нажатие на филиал ограничивает клиентскую таблицу выбранным филиалом."
    ).classes("text-sm text-gray-500 mb-3")

    with ui.row().classes("items-center gap-4 mb-2"):
        selected_branch_label = ui.label("Показаны все филиалы").classes("text-sm text-gray-500")
        reset_branch_button = ui.button("ВСЕ ФИЛИАЛЫ").props("flat color=primary")

    branch_table = ui.table(
        columns=[
            {"name": "client_group", "label": "Филиал", "field": "client_group", "align": "left", "sortable": True},
            {"name": "rating", "label": "Рейтинг", "field": "weighted_rating", "align": "center", "sortable": True},
            {"name": "shifted_amount", "label": "Переносы", "field": "shifted_amount", "align": "right", "sortable": True},
            {"name": "shift_once_amount", "label": "Разовый перенос", "field": "shift_once_amount", "align": "right", "sortable": True},
            {"name": "shift_repeated_amount", "label": "Повторный перенос", "field": "shift_repeated_amount", "align": "right", "sortable": True},
            {"name": "clients_to_control", "label": "Клиентов", "field": "clients_to_control", "align": "right", "sortable": True},
            {"name": "shifted_invoice_count", "label": "Накладных", "field": "shifted_invoice_count", "align": "right", "sortable": True},
            {"name": "total_shift_events", "label": "Событий", "field": "total_shift_events", "align": "right", "sortable": True},
        ],
        rows=filtered_branches().to_dict("records"),
        pagination={"rowsPerPage": 20},
    ).classes("w-full mb-6")
    branch_table.props(table_page_props())
    add_branch_slots(branch_table)

    client_table = render_clients_table(
        clients=filtered_clients(),
        title="Контрагенты",
        subtitle=None,
        show_branch=True,
        show_search=True,
        from_route="term-shifts",
        visible_columns=[
            "client_group",
            "client",
            "rating",
            "total_debt",
            "shifted_amount",
            "repeated_shift_amount",
            "shifted_share_pct",
            "term_shift_count",
            "repeated_shift_invoice_count",
            "last_shift_date",
            "max_current_term_delta_days",
            "max_current_payment_term_days",
            "shifted_invoice_count",
        ],
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
        ui.navigate.to(f"/client/{event.args}?from=term-shifts")

    def open_branch(event):
        ui.navigate.to(f"/branch/{quote(str(event.args))}?from=/term-shifts")

    if client_table is not None:
        client_table.on("client_click", open_client)
        client_table.on("branch_click", open_branch)