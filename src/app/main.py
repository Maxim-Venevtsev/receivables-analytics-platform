from pathlib import Path
import os
from urllib.parse import quote

import pandas as pd
from dotenv import load_dotenv
from nicegui import ui
from sqlalchemy import create_engine, text

from src.app.pages.deltas import deltas_page
from src.app.pages.overdue import overdue_page
from src.app.pages.client_card import client_card_page
from src.app.pages.forecast import due_today_page
from src.app.pages.parent_org_card import parent_org_card_page
from src.app.pages.branch_card import branch_card_page
from src.app.pages.executive import executive_overview_page
from src.app.pages.executive_long_green import executive_long_green_page
from src.app.pages.executive_overdue import executive_overdue_page
from src.app.pages.executive_branches import executive_branches_page
from src.app.pages.executive_hidden_risk import executive_hidden_risk_page
from src.app.pages.executive_term_shifts import executive_term_shifts_page
from src.app.pages.executive_rating_migration import executive_rating_migration_page
from src.app.pages.payment_attention import payment_attention_page
from src.app.pages.term_shifts import term_shifts_page

from src.app.components.navigation import top_navigation
from src.app.components.rating_stars import rating_stars_html
from src.app.components.clients_table import render_clients_table


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


def money_precise(value) -> str:
    if pd.isna(value):
        return "0,00"
    return f"{float(value):,.2f}".replace(",", " ").replace(".", ",")


def percent(value) -> str:
    if pd.isna(value):
        return "0%"
    return f"{float(value):.1f}%"


def compact_kpi(
    title: str,
    value: str,
    subtitle: str = "",
    color_class: str = "text-gray-900",
    route: str | None = None,
):
    card_classes = "w-64 h-36 p-4"
    if route:
        card_classes += " cursor-pointer hover:shadow-lg"

    card = ui.card().classes(card_classes)

    if route:
        card.on("click", lambda: ui.navigate.to(route))

    with card:
        with ui.column().classes("w-full h-full items-center justify-between text-center"):
            title_label = ui.label(title).classes(
                "text-sm text-gray-500 h-6 flex items-center justify-center"
            )
            value_label = ui.label(value).classes(
                f"text-2xl font-bold h-10 flex items-center justify-center {color_class}"
            )
            subtitle_label = ui.label(subtitle).classes(
                "text-sm text-gray-500 h-8 flex items-center justify-center"
            )

    return value_label, subtitle_label


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

            <q-btn
                dense
                flat
                color="primary"
                icon="open_in_new"
                class="ml-2"
                @click.stop="$parent.$emit('branch_open', props.row.client_group)"
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

    for col in [
        "total_debt",
        "overdue_debt",
        "shifted_amount",
        "due_today",
        "due_soon_only",
        "payment_attention_amount",
    ]:
        table.add_slot(
            f"body-cell-{col}",
            f"""
            <q-td :props="props" class="text-right" :style="props.row.is_dimmed ? 'opacity:0.45;' : ''">
                {{{{ props.row.{col}_fmt }}}}
            </q-td>
            """,
        )

    for col in ["overdue_share_pct", "shifted_share_pct"]:
        table.add_slot(
            f"body-cell-{col}",
            f"""
            <q-td :props="props" class="text-right" :style="props.row.is_dimmed ? 'opacity:0.45;' : ''">
                <q-badge
                    :color="props.row.{col} > 20 ? 'red' : props.row.{col} > 0 ? 'orange' : 'green'"
                    :label="props.row.{col}_fmt"
                />
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
                'bg-red-1': props.row.operational_status === 'OVERDUE',
                'bg-orange-1': props.row.operational_status === 'DUE_TODAY',
                'bg-yellow-1': props.row.operational_status === 'DUE_SOON',
                'bg-blue-1': props.row.operational_status === 'PAYMENT_ATTENTION',
                'bg-brown-1': props.row.operational_status === 'TERM_SHIFT'
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

                <template v-else-if="[
                    'total_debt',
                    'overdue_debt',
                    'shifted_amount',
                    'due_today',
                    'due_soon_only',
                    'payment_attention_amount'
                ].includes(col.name)">
                    {{ props.row[col.name + '_fmt'] }}
                </template>

                <template v-else-if="['overdue_share_pct', 'shifted_share_pct'].includes(col.name)">
                    <q-badge
                        :color="props.row[col.name] > 20 ? 'red' : props.row[col.name] > 0 ? 'orange' : 'green'"
                        :label="props.row[col.name + '_fmt']"
                    />
                </template>

                <template v-else>
                    {{ col.value }}
                </template>

            </q-td>
        </q-tr>
        """,
    )


@ui.page("/")
def dashboard():
    ui.label("АВС — Дебиторка").classes("text-3xl font-bold mb-2")
    ui.label(
        "Операционный центр контроля дебиторской задолженности."
    ).classes("text-gray-500 mb-4")

    top_navigation()

    kpi = query_df("""
        SELECT *
        FROM core.v_dashboard_operational_kpi
    """).iloc[0]

    branches = query_df("""
        SELECT *
        FROM core.v_dashboard_operational_branches
        ORDER BY overdue_debt DESC, shifted_amount DESC, payment_attention_amount DESC
    """)

    clients = query_df("""
        SELECT *
        FROM core.v_client_operational_summary
        ORDER BY
            operational_sort_order,
            overdue_debt DESC,
            due_today DESC,
            due_soon_only DESC,
            payment_attention_amount DESC,
            shifted_amount DESC
    """)

    if clients.empty:
        ui.label("Нет клиентов, требующих операционного контроля.").classes("text-lg text-green-700")
        return

    selected_branches: list[str] = []

    money_cols = [
        "total_debt",
        "overdue_debt",
        "shifted_amount",
        "due_today",
        "due_soon_only",
        "payment_attention_amount",
    ]

    percent_cols = [
        "overdue_share_pct",
        "shifted_share_pct",
    ]

    for frame in [branches, clients]:
        for col in money_cols + percent_cols + ["weighted_rating", "stars"]:
            if col in frame.columns:
                frame[col] = frame[col].fillna(0).astype(float)

    branches = prepare_money_cols(branches, money_cols)
    branches = prepare_percent_cols(branches, percent_cols)

    clients = prepare_money_cols(clients, money_cols)
    clients = prepare_percent_cols(clients, percent_cols)

    branches["weighted_rating_fmt"] = branches["weighted_rating"].apply(
        lambda value: "—" if pd.isna(value) else f"{float(value):.2f}"
    )

    def filtered_clients() -> pd.DataFrame:
        result = clients.copy()

        if selected_branches:
            result = result[result["client_group"].isin(selected_branches)]

        
        return result.sort_values(
            by=[
                "operational_sort_order",
                "overdue_debt",
                "due_today",
                "due_soon_only",
                "payment_attention_amount",
                "shifted_amount",
            ],
            ascending=[True, False, False, False, False, False],
        )

    def filtered_branches() -> pd.DataFrame:
        result = branches.copy()
        result["is_selected"] = result["client_group"].isin(selected_branches)
        result["is_dimmed"] = bool(selected_branches) & ~result["is_selected"]
        return result.sort_values(
            by=["overdue_debt", "shifted_amount", "payment_attention_amount"],
            ascending=[False, False, False],
        )

    def get_metrics() -> dict:
        if selected_branches:
            bdf = branches[branches["client_group"].isin(selected_branches)].copy()
            cdf = clients[clients["client_group"].isin(selected_branches)].copy()

            total_debt = float(bdf["total_debt"].sum())
            overdue_debt = float(bdf["overdue_debt"].sum())
            shifted_amount = float(bdf["shifted_amount"].sum())
            due_today = float(bdf["due_today"].sum())
            due_soon_only = float(bdf["due_soon_only"].sum())
            payment_attention_amount = float(bdf["payment_attention_amount"].sum())

            overdue_clients = int((cdf["overdue_debt"] > 0).sum())
            shifted_clients = int((cdf["shifted_amount"] > 0).sum())
            due_today_clients = int((cdf["due_today"] > 0).sum())
            due_soon_clients = int((cdf["due_soon_only"] > 0).sum())
            payment_attention_clients = int((cdf["payment_attention_amount"] > 0).sum())

        else:
            total_debt = float(kpi["total_debt"])
            overdue_debt = float(kpi["overdue_debt"])
            shifted_amount = float(kpi["shifted_amount"])
            due_today = float(kpi["due_today"])
            due_soon_only = float(kpi["due_soon_only"])
            payment_attention_amount = float(kpi["payment_attention_amount"])

            overdue_clients = int(kpi["overdue_clients"])
            shifted_clients = int(kpi["shifted_clients"])
            due_today_clients = int(kpi["due_today_clients"])
            due_soon_clients = int(kpi["due_soon_clients"])
            payment_attention_clients = int(kpi["payment_attention_clients"])

        return {
            "total_debt": total_debt,
            "overdue_debt": overdue_debt,
            "overdue_clients": overdue_clients,
            "shifted_amount": shifted_amount,
            "shifted_clients": shifted_clients,
            "due_today": due_today,
            "due_today_clients": due_today_clients,
            "due_soon_only": due_soon_only,
            "due_soon_clients": due_soon_clients,
            "payment_attention_amount": payment_attention_amount,
            "payment_attention_clients": payment_attention_clients,
            "overdue_share_pct": overdue_debt / total_debt * 100 if total_debt else 0,
            "shifted_share_pct": shifted_amount / total_debt * 100 if total_debt else 0,
        }

    metrics = get_metrics()

    with ui.row().classes("gap-4 mb-6"):
        total_debt_label, total_debt_subtitle = compact_kpi(
            "Общая задолженность",
            money(metrics["total_debt"]),
        )

        overdue_label, overdue_subtitle = compact_kpi(
            "Просрочено",
            money(metrics["overdue_debt"]),
            f"{metrics['overdue_clients']} клиентов",
            "text-red-700",
            "/overdue",
        )

        shifted_label, shifted_subtitle = compact_kpi(
            "Переносы",
            money(metrics["shifted_amount"]),
            f"{metrics['shifted_clients']} клиентов",
            "text-orange-700",
            "/term-shifts",
        )

        due_today_label, due_today_subtitle = compact_kpi(
            "К оплате сегодня",
            money(metrics["due_today"]),
            f"{metrics['due_today_clients']} клиентов",
            "text-orange-700",
            "/due-today",
        )

        due_soon_label, due_soon_subtitle = compact_kpi(
            "Ближайшие 3 дня",
            money(metrics["due_soon_only"]),
            f"{metrics['due_soon_clients']} клиентов",
            "text-yellow-700",
            "/due-soon",
        )

        attention_label, attention_subtitle = compact_kpi(
            "Ожидание оплаты",
            money(metrics["payment_attention_amount"]),
            f"{metrics['payment_attention_clients']} клиентов",
            "text-blue-700",
            "/payment-attention",
        )

    ui.label("Сводка по филиалам").classes("text-xl font-bold mt-6 mb-1")
    ui.label(
        "Агрегация операционных сигналов по филиалам. "
        "Нажатие на филиал ограничивает клиентскую сводку выбранным филиалом."
    ).classes("text-sm text-gray-500 mb-3")

    with ui.row().classes("items-center gap-4 mb-2"):
        selected_branch_label = ui.label("Показаны все филиалы").classes("text-sm text-gray-500")
        reset_branch_button = ui.button("ВСЕ ФИЛИАЛЫ").props("flat color=primary")

    branch_table = ui.table(
        columns=[
            {"name": "client_group", "label": "Филиал", "field": "client_group", "align": "left", "sortable": True},
            {"name": "rating", "label": "Рейтинг", "field": "weighted_rating", "align": "center", "sortable": True},
            {"name": "total_debt", "label": "Весь долг", "field": "total_debt", "align": "right", "sortable": True},
            {"name": "overdue_debt", "label": "Просрочено", "field": "overdue_debt", "align": "right", "sortable": True},
            {"name": "overdue_share_pct", "label": "%", "field": "overdue_share_pct", "align": "right", "sortable": True},
            {"name": "shifted_amount", "label": "Переносы", "field": "shifted_amount", "align": "right", "sortable": True},
            {"name": "shifted_share_pct", "label": "%", "field": "shifted_share_pct", "align": "right", "sortable": True},
            {"name": "due_today", "label": "К оплате сегодня", "field": "due_today", "align": "right", "sortable": True},
            {"name": "due_soon_only", "label": "Ближайшие 3 дня", "field": "due_soon_only", "align": "right", "sortable": True},
            {"name": "payment_attention_amount", "label": "Ожидание оплаты", "field": "payment_attention_amount", "align": "right", "sortable": True},
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
        from_route="dashboard",
        visible_columns=[
            "client_group",
            "client",
            "rating",
            "total_debt",
            "overdue_debt",
            "overdue_share_pct",
            "due_today",
            "due_soon_only",
            "normal_window_amount",
            "payment_attention_amount",
            "shifted_amount",
        ],
    )

    def update_kpi_cards():
        current = get_metrics()

        total_debt_label.text = money(current["total_debt"])

        overdue_label.text = money(current["overdue_debt"])
        overdue_subtitle.text = f"{current['overdue_clients']} клиентов"

        shifted_label.text = money(current["shifted_amount"])
        shifted_subtitle.text = f"{current['shifted_clients']} клиентов"

        due_today_label.text = money(current["due_today"])
        due_today_subtitle.text = f"{current['due_today_clients']} клиентов"

        due_soon_label.text = money(current["due_soon_only"])
        due_soon_subtitle.text = f"{current['due_soon_clients']} клиентов"

        attention_label.text = money(current["payment_attention_amount"])
        attention_subtitle.text = f"{current['payment_attention_clients']} клиентов"

        for label in [
            total_debt_label,
            overdue_label,
            overdue_subtitle,
            shifted_label,
            shifted_subtitle,
            due_today_label,
            due_today_subtitle,
            due_soon_label,
            due_soon_subtitle,
            attention_label,
            attention_subtitle,
        ]:
            label.update()

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

        update_kpi_cards()

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

    def open_branch_card(event):
        branch = event.args
        if branch:
            ui.navigate.to(f"/branch/{quote(str(branch))}?from=dashboard")

    branch_table.on("branch_open", open_branch_card)

    reset_branch_button.on_click(reset_branch_filter)
    
    def open_client(event):
        ui.navigate.to(f"/client/{event.args}?from=dashboard")

    def open_branch(event):
        ui.navigate.to(f"/branch/{quote(str(event.args))}?from=/")

    if client_table is not None:
        client_table.on("client_click", open_client)
        client_table.on("branch_click", open_branch)


ui.run()