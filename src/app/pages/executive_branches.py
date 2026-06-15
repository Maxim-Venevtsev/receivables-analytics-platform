from pathlib import Path
import os
from urllib.parse import quote

import pandas as pd
from dotenv import load_dotenv
from nicegui import ui
from sqlalchemy import create_engine, text

from src.app.components.navigation import top_navigation
from src.app.components.kpi_cards import money, percent
from src.app.components.branch_table import render_branch_table


PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env")

engine = create_engine(
    f"postgresql+psycopg2://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@"
    f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)


EXECUTIVE_BRANCH_COLUMNS = [
    "client_group",
    "rating",
    "total_debt",
    "overdue_debt",
    "overdue_share_pct",
    "green_60_plus_debt",
    "green_90_plus_debt",
    "green_120_plus_debt",
    "shifted_amount",
    "term_shift_count",
    "repeated_shift_invoice_count",
    "max_current_payment_term_days",
]


def query_df(sql: str, params: dict | None = None) -> pd.DataFrame:
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn, params=params)


def compact_kpi(title: str, value: str, subtitle: str = ""):
    with ui.card().classes("w-60 h-32 p-4"):
        with ui.column().classes("w-full h-full items-center justify-between text-center"):
            ui.label(title).classes("text-sm text-gray-500 h-6 flex items-center justify-center")
            ui.label(value).classes("text-2xl font-bold h-10 flex items-center justify-center")
            ui.label(subtitle).classes("text-sm text-gray-500 h-8 flex items-center justify-center")


@ui.page("/executive/branches")
def executive_branches_page():
    ui.label("Состояние филиалов").classes("text-3xl font-bold mb-2")
    ui.label(
        "Сравнение филиалов по просрочке, переносам сроков и рейтингу портфеля"
    ).classes("text-gray-500 mb-4")

    top_navigation()

    ui.button(
        "← Вернуться к Сводке",
        on_click=lambda: ui.navigate.to("/executive"),
    ).props("flat color=primary").classes("mb-4")

    branch_health = query_df("""
        SELECT *
        FROM core.v_executive_branch_health
        ORDER BY overdue_share_pct DESC, green_90_plus_share_pct DESC
    """)

    long_green_by_branch = query_df("""
        SELECT
            client_group,
            SUM(green_45_plus_debt) AS green_45_plus_debt_calc,
            SUM(green_60_plus_debt) AS green_60_plus_debt_calc,
            SUM(green_90_plus_debt) AS green_90_plus_debt_calc,
            SUM(green_120_plus_debt) AS green_120_plus_debt_calc
        FROM core.v_executive_long_green_clients
        GROUP BY client_group
    """)

    term_shifts_by_branch = query_df("""
        SELECT
            i.client_group,

            SUM(
                CASE
                    WHEN COALESCE(ts.term_shift_count, 0) > 0
                    THEN i.invoice_amount
                    ELSE 0
                END
            ) AS shifted_amount,

            COUNT(*) FILTER (
                WHERE COALESCE(ts.term_shift_count, 0) > 0
            ) AS shifted_invoice_count,

            SUM(COALESCE(ts.term_shift_count, 0)) AS term_shift_count,

            SUM(
                CASE
                    WHEN COALESCE(ts.term_shift_count, 0) >= 2
                    THEN i.invoice_amount
                    ELSE 0
                END
            ) AS repeated_shift_amount,

            COUNT(*) FILTER (
                WHERE COALESCE(ts.term_shift_count, 0) >= 2
            ) AS repeated_shift_invoice_count,

            MAX(COALESCE(ts.current_term_delta_days, 0)) AS max_current_term_delta_days,

            MAX(
                COALESCE(
                    ts.current_payment_term_days,
                    i.payment_term_days,
                    0
                )
            ) AS max_current_payment_term_days

        FROM core.v_invoice_detail i

        LEFT JOIN core.v_term_shift_invoice_summary ts
            ON i.client_id = ts.client_id
           AND i.print_invoice_number = ts.print_invoice_number
           AND i.order_number = ts.order_number
           AND i.invoice_date = ts.invoice_date

        GROUP BY i.client_group
    """)

    if branch_health.empty:
        ui.label("Нет данных по филиалам.").classes("text-green-700 text-lg")
        return

    df = branch_health.merge(
        long_green_by_branch,
        on="client_group",
        how="left",
    )

    df = df.merge(
        term_shifts_by_branch,
        on="client_group",
        how="left",
        suffixes=("", "_shift_calc"),
    )

    for src_col, target_col in [
        ("green_45_plus_debt_calc", "green_45_plus_debt"),
        ("green_60_plus_debt_calc", "green_60_plus_debt"),
        ("green_90_plus_debt_calc", "green_90_plus_debt"),
        ("green_120_plus_debt_calc", "green_120_plus_debt"),
    ]:
        if src_col in df.columns:
            df[target_col] = df[src_col].fillna(0)
        elif target_col not in df.columns:
            df[target_col] = 0
        else:
            df[target_col] = df[target_col].fillna(0)

    for col in [
        "shifted_amount",
        "shifted_invoice_count",
        "term_shift_count",
        "repeated_shift_amount",
        "repeated_shift_invoice_count",
        "max_current_term_delta_days",
        "max_current_payment_term_days",
    ]:
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    if "total_debt" not in df.columns:
        df["total_debt"] = 0

    df["total_debt"] = pd.to_numeric(
        df["total_debt"],
        errors="coerce",
    ).fillna(0)

    df = df[df["total_debt"] >= 1].copy()

    if df.empty:
        ui.label("Нет филиалов с задолженностью от 1 рубля.").classes("text-green-700 text-lg")
        return

    for col in [
        "overdue_debt",
        "overdue_share_pct",
        "green_60_plus_debt",
        "green_90_plus_debt",
        "green_120_plus_debt",
    ]:
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    total_debt = float(df["total_debt"].sum())
    overdue_debt = float(df["overdue_debt"].sum())
    branch_count = int(df["client_group"].nunique())
    branches_with_90 = int((df["green_90_plus_debt"] > 0).sum())
    branches_with_120 = int((df["green_120_plus_debt"] > 0).sum())

    worst_overdue = df.sort_values("overdue_share_pct", ascending=False).iloc[0]
    worst_long = df.sort_values("green_120_plus_debt", ascending=False).iloc[0]

    with ui.row().classes("gap-4 mb-6"):
        compact_kpi("Филиалов", str(branch_count))
        compact_kpi("Общий долг", money(total_debt))
        compact_kpi(
            "Просрочено",
            money(overdue_debt),
            percent(overdue_debt / total_debt * 100 if total_debt else 0),
        )
        compact_kpi("Филиалов с 90+", str(branches_with_90))
        compact_kpi("Филиалов с 120+", str(branches_with_120))
        compact_kpi(
            "Худший % просрочки",
            percent(worst_overdue["overdue_share_pct"]),
            str(worst_overdue["client_group"]),
        )
        compact_kpi(
            "Худший 120+",
            money(worst_long["green_120_plus_debt"]),
            str(worst_long["client_group"]),
        )

    branch_table = render_branch_table(
        df,
        title="Риск-профиль филиалов",
        subtitle=(
            "Филиалы с задолженностью от 1 рубля. "
            "В таблице показаны рейтинг, просрочка, длинный непросроченный долг, "
            "переносы сроков и максимальный текущий срок."
        ),
        mode="executive",
        rows_per_page=20,
        visible_columns=EXECUTIVE_BRANCH_COLUMNS,
    )

    if branch_table is not None:
        branch_table.on(
            "branch_click",
            lambda event: ui.navigate.to(
                f"/branch/{quote(str(event.args))}?from=/executive/branches"
            ),
        )

        branch_table.on(
            "branch_open",
            lambda event: ui.navigate.to(
                f"/branch/{quote(str(event.args))}?from=/executive/branches"
            ),
        )