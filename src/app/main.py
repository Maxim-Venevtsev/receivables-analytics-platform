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
from src.app.components.clients_table import render_clients_table
from src.app.components.branch_table import render_branch_table


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

engine = create_engine(
    f"postgresql+psycopg2://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@"
    f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)


DASHBOARD_CLIENT_COLUMNS = [
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
]


DASHBOARD_BRANCH_COLUMNS = [
    "client_group",
    "rating",
    "total_debt",
    "overdue_debt",
    "overdue_share_pct",
    "due_today",
    "due_soon_only",
    "normal_window_amount",
    "payment_attention_amount",
    "shifted_amount",
]


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


def render_debt_structure_bar(metrics: dict):
    total_debt = float(metrics.get("total_debt", 0) or 0)
    overdue_debt = float(metrics.get("overdue_debt", 0) or 0)
    due_today = float(metrics.get("due_today", 0) or 0)
    due_soon_only = float(metrics.get("due_soon_only", 0) or 0)

    normal_debt = max(
        total_debt - overdue_debt - due_today - due_soon_only,
        0,
    )

    buckets = [
        {
            "label": "В обычном режиме",
            "amount": normal_debt,
            "color": "#22c55e",
        },
        {
            "label": "Ближайшие 3 дня",
            "amount": due_soon_only,
            "color": "#facc15",
        },
        {
            "label": "К оплате сегодня",
            "amount": due_today,
            "color": "#f97316",
        },
        {
            "label": "Просрочено",
            "amount": overdue_debt,
            "color": "#dc2626",
        },
    ]

    with ui.card().classes("w-full p-4 mb-6"):
        ui.label("Структура задолженности").classes("text-xl font-bold mb-1")
        ui.label(
            "Операционная структура текущего долга: нормальная задолженность, "
            "ближайшие сроки оплаты, платежи сегодня и просрочка."
        ).classes("text-sm text-gray-500 mb-4")

        with ui.element("div").classes("w-full h-8 rounded-full overflow-hidden flex bg-gray-100"):
            for bucket in buckets:
                amount = float(bucket["amount"] or 0)
                share = amount / total_debt * 100 if total_debt else 0

                if amount <= 0:
                    continue

                ui.element("div").style(
                    f"width: {share}%; background-color: {bucket['color']};"
                ).classes("h-8")

        with ui.row().classes("gap-4 mt-4 flex-wrap"):
            for bucket in buckets:
                amount = float(bucket["amount"] or 0)
                share = amount / total_debt * 100 if total_debt else 0

                with ui.row().classes("items-center gap-2"):
                    ui.element("div").style(
                        "width: 12px; height: 12px; "
                        f"border-radius: 9999px; background-color: {bucket['color']};"
                    )
                    ui.label(
                        f"{bucket['label']}: {money(amount)} · {percent(share)}"
                    ).classes("text-sm text-gray-700")


def normalize_numeric_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    result = df.copy()

    for col in columns:
        if col not in result.columns:
            result[col] = 0

        result[col] = pd.to_numeric(
            result[col],
            errors="coerce",
        ).fillna(0)

    return result


@ui.page("/")
def dashboard():
    ui.label("АРС — Дебиторка").classes("text-3xl font-bold mb-2")
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

    numeric_cols = [
        "total_debt",
        "overdue_debt",
        "overdue_share_pct",
        "shifted_amount",
        "shifted_share_pct",
        "due_today",
        "due_soon_only",
        "normal_window_amount",
        "payment_attention_amount",
        "weighted_rating",
        "stars",
    ]

    branches = normalize_numeric_columns(branches, numeric_cols)
    clients = normalize_numeric_columns(clients, numeric_cols)

    branches = branches[branches["total_debt"] >= 1].copy()

    selected_branches: list[str] = []

    def filtered_clients() -> pd.DataFrame:
        result = clients.copy()

        if selected_branches:
            result = result[result["client_group"].isin(selected_branches)]

        sort_cols = [
            col for col in [
                "operational_sort_order",
                "overdue_debt",
                "due_today",
                "due_soon_only",
                "payment_attention_amount",
                "shifted_amount",
            ]
            if col in result.columns
        ]

        if sort_cols:
            ascending = [True] + [False] * (len(sort_cols) - 1)
            result = result.sort_values(
                by=sort_cols,
                ascending=ascending,
            )

        return result

    def filtered_branches() -> pd.DataFrame:
        return branches.sort_values(
            by=[
                "overdue_debt",
                "shifted_amount",
                "payment_attention_amount",
                "total_debt",
            ],
            ascending=[False, False, False, False],
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

    debt_structure_container = ui.column().classes("w-full")

    def render_current_debt_structure():
        debt_structure_container.clear()

        with debt_structure_container:
            render_debt_structure_bar(get_metrics())

    render_current_debt_structure()

    with ui.row().classes("items-center gap-4 mb-2"):
        selected_branch_label = ui.label("Показаны все филиалы").classes("text-sm text-gray-500")
        reset_branch_button = ui.button("ВСЕ ФИЛИАЛЫ").props("flat color=primary")

    branch_table = render_branch_table(
        branches=filtered_branches(),
        title="Сводка по филиалам",
        subtitle=(
            "Агрегация операционных сигналов по филиалам. "
            "Нажатие на филиал ограничивает клиентскую сводку выбранным филиалом."
        ),
        mode="operational",
        selected_branches=selected_branches,
        rows_per_page=20,
        visible_columns=DASHBOARD_BRANCH_COLUMNS,
    )

    client_table = render_clients_table(
        clients=filtered_clients(),
        title="Контрагенты",
        subtitle=None,
        show_branch=True,
        show_search=True,
        from_route="dashboard",
        visible_columns=DASHBOARD_CLIENT_COLUMNS,
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

        render_current_debt_structure()

    def apply_filters():
        if selected_branches:
            selected_branch_label.text = f"Фильтр: {', '.join(selected_branches)}"
        else:
            selected_branch_label.text = "Показаны все филиалы"

        selected_branch_label.update()

        if branch_table is not None:
            branch_table.refresh_branches(
                filtered_branches(),
                selected_branches=selected_branches,
            )

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

    def open_branch_card(event):
        branch = event.args

        if branch:
            ui.navigate.to(f"/branch/{quote(str(branch))}?from=dashboard")

    def open_client(event):
        ui.navigate.to(f"/client/{event.args}?from=dashboard")

    def open_branch_from_client_table(event):
        ui.navigate.to(f"/branch/{quote(str(event.args))}?from=/")

    if branch_table is not None:
        branch_table.on("branch_click", toggle_branch)
        branch_table.on("branch_open", open_branch_card)

    if client_table is not None:
        client_table.on("client_click", open_client)
        client_table.on("branch_click", open_branch_from_client_table)

    reset_branch_button.on_click(reset_branch_filter)


ui.run()