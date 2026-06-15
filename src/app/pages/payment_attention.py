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


PAYMENT_ATTENTION_CLIENT_COLUMNS = [
    "client_group",
    "client",
    "rating",
    "total_debt",
    "contract_payment_term_days",
    "usual_payment_window",
    "normal_window_amount",
    "payment_attention_amount",
    "shifted_amount",
    "repeated_shift_amount",
    "invoice_count",
]


PAYMENT_ATTENTION_BRANCH_COLUMNS = [
    "client_group",
    "rating",
    "total_debt",
    "normal_window_amount",
    "payment_attention_amount",
    "shifted_amount",
    "repeated_shift_amount",
    "invoice_count",
]


def query_df(sql: str, params: dict | None = None) -> pd.DataFrame:
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn, params=params)


def compact_kpi(
    title: str,
    value: str,
    subtitle: str = "",
    color_class: str = "text-gray-900",
):
    value_label = None
    subtitle_label = None

    with ui.card().classes("w-60 h-32 p-4"):
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


@ui.page("/payment-attention")
def payment_attention_page():
    ui.label("Ожидание оплаты").classes("text-3xl font-bold mb-2")

    ui.label(
        "Клиенты с непросроченными накладными, которые уже вошли в обычное платежное окно, "
        "вышли из него или имеют переносы срока оплаты."
    ).classes("text-subtitle1 text-grey-7 mb-4")

    top_navigation()

    clients_df = query_df("""
        SELECT *
        FROM core.v_client_operational_summary
        WHERE
            payment_attention_amount > 0
            OR normal_window_amount > 0
            OR shifted_amount > 0
            OR repeated_shift_amount > 0
        ORDER BY
            payment_attention_amount DESC,
            repeated_shift_amount DESC,
            shifted_amount DESC,
            normal_window_amount DESC,
            total_debt DESC
    """)

    branches_df = query_df("""
        WITH branch_agg AS (
            SELECT
                client_group,

                SUM(total_debt) AS total_debt,
                SUM(normal_window_amount) AS normal_window_amount,
                SUM(payment_attention_amount) AS payment_attention_amount,
                SUM(shifted_amount) AS shifted_amount,
                SUM(repeated_shift_amount) AS repeated_shift_amount,
                SUM(invoice_count) AS invoice_count,

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
            normal_window_amount,
            payment_attention_amount,
            shifted_amount,
            repeated_shift_amount,
            invoice_count

        FROM branch_agg

        WHERE
            normal_window_amount > 0
            OR payment_attention_amount > 0
            OR shifted_amount > 0
            OR repeated_shift_amount > 0

        ORDER BY
            payment_attention_amount DESC,
            repeated_shift_amount DESC,
            shifted_amount DESC,
            normal_window_amount DESC,
            total_debt DESC
    """)

    if clients_df.empty:
        ui.label("Нет данных для отображения").classes("text-grey-6")
        return

    numeric_cols = [
        "total_debt",
        "normal_window_amount",
        "payment_attention_amount",
        "shifted_amount",
        "repeated_shift_amount",
        "invoice_count",
        "weighted_rating",
        "stars",
    ]

    clients_df = normalize_numeric_columns(clients_df, numeric_cols)
    branches_df = normalize_numeric_columns(branches_df, numeric_cols)

    branches_df = branches_df[branches_df["total_debt"] >= 1].copy()

    selected_branches: list[str] = []

    def filtered_clients() -> pd.DataFrame:
        result = clients_df.copy()

        if selected_branches:
            result = result[result["client_group"].isin(selected_branches)]

        return result.sort_values(
            by=[
                "payment_attention_amount",
                "repeated_shift_amount",
                "shifted_amount",
                "normal_window_amount",
                "total_debt",
            ],
            ascending=[False, False, False, False, False],
        )

    def filtered_branches() -> pd.DataFrame:
        return branches_df.sort_values(
            by=[
                "payment_attention_amount",
                "repeated_shift_amount",
                "shifted_amount",
                "normal_window_amount",
                "total_debt",
            ],
            ascending=[False, False, False, False, False],
        )

    def current_metrics() -> dict:
        df = filtered_clients()

        return {
            "in_window": float(df["normal_window_amount"].sum()),
            "out_window": float(df["payment_attention_amount"].sum()),
            "shift_once": float(df["shifted_amount"].sum()),
            "shift_repeated": float(df["repeated_shift_amount"].sum()),
            "clients_to_control": int(
                (
                    (df["payment_attention_amount"] > 0)
                    | (df["shifted_amount"] > 0)
                    | (df["repeated_shift_amount"] > 0)
                ).sum()
            ),
            "in_window_clients": int((df["normal_window_amount"] > 0).sum()),
            "out_window_clients": int((df["payment_attention_amount"] > 0).sum()),
            "shift_once_clients": int((df["shifted_amount"] > 0).sum()),
            "shift_repeated_clients": int((df["repeated_shift_amount"] > 0).sum()),
        }

    metrics = current_metrics()

    with ui.row().classes("gap-3 mb-8"):
        in_window_value, in_window_subtitle = compact_kpi(
            "В обычном окне",
            money(metrics["in_window"]),
            f"{metrics['in_window_clients']} клиентов",
        )

        out_window_value, out_window_subtitle = compact_kpi(
            "Вышли из окна",
            money(metrics["out_window"]),
            f"{metrics['out_window_clients']} клиентов",
            "text-orange-700",
        )

        shift_once_value, shift_once_subtitle = compact_kpi(
            "Разовый перенос",
            money(metrics["shift_once"]),
            f"{metrics['shift_once_clients']} клиентов",
            "text-amber-700",
        )

        shift_repeated_value, shift_repeated_subtitle = compact_kpi(
            "Повторный перенос",
            money(metrics["shift_repeated"]),
            f"{metrics['shift_repeated_clients']} клиентов",
            "text-red-700",
        )

        clients_to_control_value, clients_to_control_subtitle = compact_kpi(
            "Клиентов к контролю",
            str(metrics["clients_to_control"]),
        )

    ui.separator().classes("mb-6")

    with ui.row().classes("items-center gap-4 mb-2"):
        selected_branch_label = ui.label("Показаны все филиалы").classes(
            "text-sm text-gray-500"
        )
        reset_branch_button = ui.button("ВСЕ ФИЛИАЛЫ").props("flat color=primary")

    branch_table = render_branch_table(
        branches=filtered_branches(),
        title="Сводка по филиалам",
        subtitle=(
            "Агрегация ожидания оплаты по филиалам. "
            "Нажатие на филиал ограничивает клиентскую сводку выбранным филиалом."
        ),
        mode="operational",
        selected_branches=selected_branches,
        rows_per_page=20,
        visible_columns=PAYMENT_ATTENTION_BRANCH_COLUMNS,
    )

    client_table = render_clients_table(
        clients=filtered_clients(),
        title="Контрагенты",
        subtitle=None,
        show_branch=True,
        show_search=True,
        from_route="payment-attention",
        visible_columns=PAYMENT_ATTENTION_CLIENT_COLUMNS,
    )

    def update_kpi_cards():
        current = current_metrics()

        in_window_value.text = money(current["in_window"])
        in_window_subtitle.text = f"{current['in_window_clients']} клиентов"

        out_window_value.text = money(current["out_window"])
        out_window_subtitle.text = f"{current['out_window_clients']} клиентов"

        shift_once_value.text = money(current["shift_once"])
        shift_once_subtitle.text = f"{current['shift_once_clients']} клиентов"

        shift_repeated_value.text = money(current["shift_repeated"])
        shift_repeated_subtitle.text = f"{current['shift_repeated_clients']} клиентов"

        clients_to_control_value.text = str(current["clients_to_control"])
        clients_to_control_subtitle.text = ""

        for label in [
            in_window_value,
            in_window_subtitle,
            out_window_value,
            out_window_subtitle,
            shift_once_value,
            shift_once_subtitle,
            shift_repeated_value,
            shift_repeated_subtitle,
            clients_to_control_value,
            clients_to_control_subtitle,
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
            ui.navigate.to(f"/branch/{quote(str(branch))}?from=/payment-attention")

    def open_client(event):
        ui.navigate.to(f"/client/{event.args}?from=payment-attention")

    def open_branch_from_client_table(event):
        ui.navigate.to(f"/branch/{quote(str(event.args))}?from=/payment-attention")

    if branch_table is not None:
        branch_table.on("branch_click", toggle_branch)
        branch_table.on("branch_open", open_branch_card)

    if client_table is not None:
        client_table.on("client_click", open_client)
        client_table.on("branch_click", open_branch_from_client_table)

    reset_branch_button.on_click(reset_branch_filter)