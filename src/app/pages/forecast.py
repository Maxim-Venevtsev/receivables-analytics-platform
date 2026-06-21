from pathlib import Path
import os
from urllib.parse import quote

import pandas as pd
from dotenv import load_dotenv
from nicegui import ui
from sqlalchemy import create_engine, text

from src.app.components.navigation import top_navigation
from src.app.components.clients_table import render_clients_table
from src.app.components.branch_table import render_branch_table


PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env")

engine = create_engine(
    f"postgresql+psycopg2://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@"
    f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)


DUE_TODAY_CLIENT_COLUMNS = [
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


DUE_TODAY_BRANCH_COLUMNS = [
    "client_group",
    "rating",
    "total_debt",
    "due_today",
    "due_today_share_pct",
    "shifted_amount",
    "shifted_share_pct",
    "overdue_debt",
]


DUE_SOON_CLIENT_COLUMNS = [
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


DUE_SOON_BRANCH_COLUMNS = [
    "client_group",
    "rating",
    "total_debt",
    "due_soon_only",
    "due_soon_share_pct",
    "shifted_amount",
    "shifted_share_pct",
    "overdue_debt",
]


def query_df(sql: str, params: dict | None = None) -> pd.DataFrame:
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn, params=params)


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


def load_forecast_data(mode: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    is_today = mode == "today"

    target_condition = (
        "i.is_due_today"
        if is_today
        else "(i.is_due_in_3_days AND NOT i.is_due_today)"
    )

    target_amount_col = "due_today" if is_today else "due_soon_only"
    target_share_col = "due_today_share_pct" if is_today else "due_soon_share_pct"

    clients_df = query_df(f"""
        WITH target_invoices AS (
            SELECT
                i.client_id,
                COUNT(*) FILTER (
                    WHERE {target_condition}
                ) AS target_invoice_count
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
        WITH target_invoices AS (
            SELECT
                i.client_id,
                COUNT(*) FILTER (
                    WHERE {target_condition}
                ) AS target_invoice_count
            FROM core.v_invoice_detail i
            GROUP BY i.client_id
        ),

        client_summary AS (
            SELECT
                s.*,
                COALESCE(t.target_invoice_count, 0) AS target_invoice_count
            FROM core.v_client_operational_summary s
            LEFT JOIN target_invoices t
                ON s.client_id = t.client_id
        ),

        branch_agg AS (
            SELECT
                client_group,

                SUM(total_debt) AS total_debt,
                SUM(due_today) AS due_today,
                SUM(due_soon_only) AS due_soon_only,
                SUM(shifted_amount) AS shifted_amount,
                SUM(overdue_debt) AS overdue_debt,

                ROUND(
                    SUM(due_today)
                    / NULLIF(SUM(total_debt), 0)
                    * 100,
                    2
                ) AS due_today_share_pct,

                ROUND(
                    SUM(due_soon_only)
                    / NULLIF(SUM(total_debt), 0)
                    * 100,
                    2
                ) AS due_soon_share_pct,

                ROUND(
                    SUM(shifted_amount)
                    / NULLIF(SUM(total_debt), 0)
                    * 100,
                    2
                ) AS shifted_share_pct,

                ROUND(
                    SUM(overdue_debt)
                    / NULLIF(SUM(total_debt), 0)
                    * 100,
                    2
                ) AS overdue_share_pct,

                SUM(target_invoice_count) AS target_invoice_count,

                COUNT(*) FILTER (
                    WHERE {target_amount_col} > 0
                ) AS clients_to_control,

                CASE
                    WHEN SUM(total_debt) > 0
                    THEN
                        SUM(COALESCE(stars, 0)::numeric * total_debt)
                        / SUM(total_debt)
                    ELSE NULL::numeric
                END AS weighted_rating

            FROM client_summary

            GROUP BY client_group
        )

        SELECT
            client_group,
            ROUND(weighted_rating::numeric, 1) AS weighted_rating,

            total_debt,
            due_today,
            due_soon_only,
            due_today_share_pct,
            due_soon_share_pct,

            shifted_amount,
            shifted_share_pct,

            overdue_debt,
            overdue_share_pct,

            target_invoice_count,
            clients_to_control

        FROM branch_agg

        WHERE {target_amount_col} > 0

        ORDER BY
            {target_amount_col} DESC,
            shifted_amount DESC,
            total_debt DESC
    """)

    return clients_df, branches_df


def render_forecast_page(mode: str):
    is_today = mode == "today"

    page_title = "К оплате сегодня" if is_today else "К оплате в ближайшие три дня"
    target_label = "К оплате сегодня" if is_today else "К оплате в ближайшие три дня"
    target_amount_col = "due_today" if is_today else "due_soon_only"

    client_columns = (
        DUE_TODAY_CLIENT_COLUMNS
        if is_today
        else DUE_SOON_CLIENT_COLUMNS
    )

    branch_columns = (
        DUE_TODAY_BRANCH_COLUMNS
        if is_today
        else DUE_SOON_BRANCH_COLUMNS
    )

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

    numeric_cols = [
        "total_debt",
        "due_today",
        "due_soon_only",
        "due_today_share_pct",
        "due_soon_share_pct",
        "shifted_amount",
        "shifted_share_pct",
        "overdue_debt",
        "overdue_share_pct",
        "weighted_rating",
        "stars",
        "clients_to_control",
        "target_invoice_count",
    ]

    clients_df = normalize_numeric_columns(clients_df, numeric_cols)
    branches_df = normalize_numeric_columns(branches_df, numeric_cols)

    branches_df = branches_df[branches_df["total_debt"] >= 1].copy()

    selected_branches: list[str] = []

    def filtered_clients() -> pd.DataFrame:
        result = clients_df.copy()

        if selected_branches:
            result = result[result["client_group"].isin(selected_branches)]

        sort_cols = [
            col for col in [
                target_amount_col,
                "shifted_amount",
                "overdue_debt",
                "total_debt",
            ]
            if col in result.columns
        ]

        if sort_cols:
            result = result.sort_values(
                by=sort_cols,
                ascending=[False] * len(sort_cols),
            )

        return result

    def filtered_branches() -> pd.DataFrame:
        return branches_df.sort_values(
            by=[
                target_amount_col,
                "shifted_amount",
                "overdue_debt",
                "total_debt",
            ],
            ascending=[False, False, False, False],
        )

    def kpi_metrics() -> dict:
        bdf = branches_df.copy()
        cdf = clients_df.copy()

        if selected_branches:
            bdf = bdf[bdf["client_group"].isin(selected_branches)]
            cdf = cdf[cdf["client_group"].isin(selected_branches)]

        total_debt = float(bdf["total_debt"].sum())
        target_amount = float(bdf[target_amount_col].sum())
        shifted_amount = float(cdf["shifted_amount"].sum())

        return {
            "target_amount": target_amount,
            "target_share_pct": target_amount / total_debt * 100 if total_debt else 0,
            "client_count": int(cdf["client_id"].nunique()) if not cdf.empty else 0,
            "invoice_count": int(cdf["target_invoice_count"].sum()) if not cdf.empty else 0,
            "shifted_amount": shifted_amount,
        }

    k = kpi_metrics()

    with ui.row().classes("gap-4 mb-6"):
        target_label_value, target_label_subtitle = compact_kpi(
            target_label,
            money(k["target_amount"]),
            f"{percent(k['target_share_pct'])} портфеля",
            "text-orange-700" if is_today else "text-yellow-700",
        )

        client_count_value, client_count_subtitle = compact_kpi(
            "Клиентов к контролю",
            str(k["client_count"]),
        )

        invoice_count_value, invoice_count_subtitle = compact_kpi(
            "Накладных к контролю",
            str(k["invoice_count"]),
        )

        shifted_value, shifted_subtitle = compact_kpi(
            "Переносы",
            money(k["shifted_amount"]),
            "по контрагентам в выборке",
            "text-red-700",
        )

    with ui.row().classes("items-center gap-4 mb-2"):
        selected_branch_label = ui.label("Показаны все филиалы").classes("text-sm text-gray-500")
        reset_branch_button = ui.button("ВСЕ ФИЛИАЛЫ").props("flat color=primary")

    branch_table = render_branch_table(
        branches=filtered_branches(),
        title="Сводка по филиалам",
        subtitle=(
            "Агрегация платежей к контролю по филиалам. "
            "Нажатие на филиал ограничивает клиентскую таблицу выбранным филиалом."
        ),
        mode="operational",
        selected_branches=selected_branches,
        rows_per_page=20,
        visible_columns=branch_columns,
    )

    client_table = render_clients_table(
        clients=filtered_clients(),
        title="Контрагенты",
        subtitle=None,
        show_branch=True,
        show_search=True,
        from_route="due-today" if is_today else "due-soon",
        visible_columns=client_columns,
        default_sort_by=target_amount_col,
        default_sort_descending=True,
    )

    def update_kpi_cards():
        current = kpi_metrics()

        target_label_value.text = money(current["target_amount"])
        target_label_subtitle.text = f"{percent(current['target_share_pct'])} портфеля"

        client_count_value.text = str(current["client_count"])
        client_count_subtitle.text = ""

        invoice_count_value.text = str(current["invoice_count"])
        invoice_count_subtitle.text = ""

        shifted_value.text = money(current["shifted_amount"])
        shifted_subtitle.text = "по контрагентам в выборке"

        for label in [
            target_label_value,
            target_label_subtitle,
            client_count_value,
            client_count_subtitle,
            invoice_count_value,
            invoice_count_subtitle,
            shifted_value,
            shifted_subtitle,
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

        if not branch:
            return

        origin = "/due-today" if is_today else "/due-soon"
        ui.navigate.to(f"/branch/{quote(str(branch))}?from={origin}")

    def open_client(event):
        origin = "due-today" if is_today else "due-soon"
        ui.navigate.to(f"/client/{event.args}?from={origin}")

    def open_branch_from_client_table(event):
        origin = "/due-today" if is_today else "/due-soon"
        ui.navigate.to(f"/branch/{quote(str(event.args))}?from={origin}")

    if branch_table is not None:
        branch_table.on("branch_click", toggle_branch)
        branch_table.on("branch_open", open_branch_card)

    if client_table is not None:
        client_table.on("client_click", open_client)
        client_table.on("branch_click", open_branch_from_client_table)

    reset_branch_button.on_click(reset_branch_filter)


@ui.page("/due-today")
def due_today_page():
    render_forecast_page("today")


@ui.page("/due-soon")
def due_soon_page():
    render_forecast_page("soon")
