from pathlib import Path
import os
from urllib.parse import quote

import pandas as pd
from dotenv import load_dotenv
from nicegui import ui
from sqlalchemy import create_engine, text

from src.app.components.navigation import top_navigation
from src.app.components.kpi_cards import money
from src.app.components.clients_table import render_clients_table
from src.app.components.branch_table import render_branch_table


PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env")

engine = create_engine(
    f"postgresql+psycopg2://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@"
    f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)


TERM_SHIFT_CLIENT_COLUMNS = [
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
]


TERM_SHIFT_BRANCH_COLUMNS = [
    "client_group",
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
]


def query_df(sql: str) -> pd.DataFrame:
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn)


def compact_kpi(
    title: str,
    value: str,
    subtitle: str = "",
    color_class: str = "text-gray-900",
):
    value_label = None
    subtitle_label = None

    with ui.card().classes("w-64 h-36 p-4"):
        with ui.column().classes("w-full h-full items-center justify-between text-center"):
            ui.label(title).classes("text-sm text-gray-500 h-6 flex items-center justify-center")
            value_label = ui.label(value).classes(
                f"text-2xl font-bold h-10 flex items-center justify-center {color_class}"
            )
            subtitle_label = ui.label(subtitle).classes(
                "text-sm text-gray-500 h-8 flex items-center justify-center"
            )

    return value_label, subtitle_label


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


@ui.page("/term-shifts")
def term_shifts_page():
    ui.label("Переносы сроков").classes("text-3xl font-bold mb-2")
    ui.label(
        "Активные накладные, по которым срок оплаты был перенесен. "
        "Разовые и повторные переносы выделены отдельно."
    ).classes("text-gray-500 mb-4")

    top_navigation()

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

    if clients.empty:
        ui.label("Активных накладных с переносами сроков нет.").classes("text-lg text-green-700")
        return

    branches = query_df("""
        WITH branch_agg AS (
            SELECT
                client_group,

                SUM(total_debt) AS total_debt,
                SUM(shifted_amount) AS shifted_amount,
                SUM(repeated_shift_amount) AS repeated_shift_amount,

                ROUND(
                    SUM(shifted_amount)
                    / NULLIF(SUM(total_debt), 0)
                    * 100,
                    2
                ) AS shifted_share_pct,

                SUM(term_shift_count) AS term_shift_count,
                SUM(repeated_shift_invoice_count) AS repeated_shift_invoice_count,
                SUM(shifted_invoice_count) AS shifted_invoice_count,

                MAX(last_shift_date) AS last_shift_date,
                MAX(max_current_term_delta_days) AS max_current_term_delta_days,
                MAX(max_current_payment_term_days) AS max_current_payment_term_days,

                CASE
                    WHEN SUM(total_debt) > 0
                    THEN
                        SUM(COALESCE(stars, 0)::numeric * total_debt)
                        / SUM(total_debt)
                    ELSE NULL::numeric
                END AS weighted_rating

            FROM core.v_client_operational_summary

            GROUP BY client_group
        )

        SELECT
            client_group,
            ROUND(weighted_rating::numeric, 1) AS weighted_rating,

            total_debt,
            shifted_amount,
            repeated_shift_amount,
            shifted_share_pct,

            term_shift_count,
            repeated_shift_invoice_count,
            last_shift_date,
            max_current_term_delta_days,
            max_current_payment_term_days,
            shifted_invoice_count

        FROM branch_agg

        WHERE shifted_amount > 0

        ORDER BY
            repeated_shift_amount DESC,
            shifted_amount DESC,
            term_shift_count DESC,
            total_debt DESC
    """)

    numeric_cols = [
        "total_debt",
        "shifted_amount",
        "repeated_shift_amount",
        "shifted_share_pct",
        "term_shift_count",
        "repeated_shift_invoice_count",
        "shifted_invoice_count",
        "max_current_term_delta_days",
        "max_current_payment_term_days",
        "weighted_rating",
        "stars",
    ]

    clients = normalize_numeric_columns(clients, numeric_cols)
    branches = normalize_numeric_columns(branches, numeric_cols)

    branches = branches[branches["total_debt"] >= 1].copy()

    selected_branches: list[str] = []

    def filtered_clients() -> pd.DataFrame:
        result = clients.copy()

        if selected_branches:
            result = result[result["client_group"].isin(selected_branches)]

        return result.sort_values(
            by=[
                "repeated_shift_amount",
                "shifted_amount",
                "term_shift_count",
                "total_debt",
            ],
            ascending=[False, False, False, False],
        )

    def filtered_branches() -> pd.DataFrame:
        return branches.sort_values(
            by=[
                "repeated_shift_amount",
                "shifted_amount",
                "term_shift_count",
                "total_debt",
            ],
            ascending=[False, False, False, False],
        )

    def kpi_metrics() -> dict:
        cdf = filtered_clients()

        return {
            "shifted_amount": float(cdf["shifted_amount"].sum()),
            "clients": int(cdf["client_id"].nunique()) if not cdf.empty else 0,
            "invoices": int(cdf["shifted_invoice_count"].sum()) if not cdf.empty else 0,
            "shift_repeated_amount": float(cdf["repeated_shift_amount"].sum()),
            "events": int(cdf["term_shift_count"].sum()) if not cdf.empty else 0,
        }

    k = kpi_metrics()

    with ui.row().classes("gap-4 mb-6"):
        shifted_value, shifted_subtitle = compact_kpi(
            "Перенесено",
            money(k["shifted_amount"]),
            f"{k['clients']} клиентов",
            "text-orange-700",
        )

        invoices_value, invoices_subtitle = compact_kpi(
            "Накладных",
            str(k["invoices"]),
        )

        events_value, events_subtitle = compact_kpi(
            "Событий переноса",
            str(k["events"]),
        )

        repeated_value, repeated_subtitle = compact_kpi(
            "Повторные переносы",
            money(k["shift_repeated_amount"]),
            "2+ переносов",
            "text-red-700",
        )

    with ui.row().classes("items-center gap-4 mb-2"):
        selected_branch_label = ui.label("Показаны все филиалы").classes("text-sm text-gray-500")
        reset_branch_button = ui.button("ВСЕ ФИЛИАЛЫ").props("flat color=primary")

    branch_table = render_branch_table(
        branches=filtered_branches(),
        title="Сводка по филиалам",
        subtitle=(
            "Агрегация активных переносов по филиалам. "
            "Нажатие на филиал ограничивает клиентскую таблицу выбранным филиалом."
        ),
        mode="operational",
        selected_branches=selected_branches,
        rows_per_page=20,
        visible_columns=TERM_SHIFT_BRANCH_COLUMNS,
    )

    client_table = render_clients_table(
        clients=filtered_clients(),
        title="Контрагенты",
        subtitle=None,
        show_branch=True,
        show_search=True,
        from_route="term-shifts",
        visible_columns=TERM_SHIFT_CLIENT_COLUMNS,
    )

    def update_kpi_cards():
        current = kpi_metrics()

        shifted_value.text = money(current["shifted_amount"])
        shifted_subtitle.text = f"{current['clients']} клиентов"

        invoices_value.text = str(current["invoices"])
        invoices_subtitle.text = ""

        events_value.text = str(current["events"])
        events_subtitle.text = ""

        repeated_value.text = money(current["shift_repeated_amount"])
        repeated_subtitle.text = "2+ переносов"

        for label in [
            shifted_value,
            shifted_subtitle,
            invoices_value,
            invoices_subtitle,
            events_value,
            events_subtitle,
            repeated_value,
            repeated_subtitle,
        ]:
            label.update()

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
            ui.navigate.to(f"/branch/{quote(str(branch))}?from=/term-shifts")

    def open_client(event):
        ui.navigate.to(f"/client/{event.args}?from=term-shifts")

    def open_branch_from_client_table(event):
        ui.navigate.to(f"/branch/{quote(str(event.args))}?from=/term-shifts")

    if branch_table is not None:
        branch_table.on("branch_click", toggle_branch)
        branch_table.on("branch_open", open_branch_card)

    if client_table is not None:
        client_table.on("client_click", open_client)
        client_table.on("branch_click", open_branch_from_client_table)

    reset_branch_button.on_click(reset_branch_filter)