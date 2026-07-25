from pathlib import Path
import os

import pandas as pd
from dotenv import load_dotenv
from nicegui import ui
from sqlalchemy import create_engine
from fastapi import Request

from src.app.components.navigation import top_navigation
from src.app.services.database import read_dataframe
from src.app.services.performance import page_build
from src.app.services.settings import get_page_response_timeout
from src.app.components.rating_stars import rating_stars_html
from src.app.components.charts import (
    build_client_debt_history_chart,
    build_client_debt_structure_chart,
)
from src.app.components.kpi_cards import (
    money,
    percent,
    compact_kpi_card,
)
from src.app.components.rating_migration_strip import (
    render_rating_migration_strip,
)
from src.app.components.credit_quality_strip import (
    render_credit_quality_strip,
)
from src.app.components.payment_behavior_strip import (
    render_payment_behavior_strip,
    get_payment_behavior_metrics,
)
from src.app.components.receivables_kpi_strip import render_receivables_kpi_strip
from src.app.components.work_invoices_table import render_work_invoices_table
from src.app.components.paid_invoices_table import render_paid_invoices_table
from urllib.parse import quote

PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env")

engine = create_engine(
    f"postgresql+psycopg2://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@"
    f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)


async def query_df(sql: str, params: dict = None, *, operation: str) -> pd.DataFrame:
    return await read_dataframe(engine, sql, operation=operation, params=params)


async def query_optional_df(
    sql: str,
    params: dict = None,
    *,
    operation: str,
) -> pd.DataFrame:
    try:
        return await query_df(sql, params=params, operation=operation)
    except Exception:
        return pd.DataFrame()


def date_fmt(value) -> str:
    if pd.isna(value):
        return "—"
    return pd.to_datetime(value).strftime("%d.%m.%Y")


async def get_historical_client_identity(client_id: str) -> pd.DataFrame:
    return await query_optional_df("""
        WITH client_daily AS (
            SELECT
                report_generated_date,
                client_id,
                MAX(client_name) AS client_name,
                MAX(client_group) AS client_group,
                MAX(parent_org_id) AS parent_org_id,
                SUM(invoice_amount) AS total_debt
            FROM core.receivables_snapshot_fact
            WHERE client_id = :client_id
            GROUP BY
                report_generated_date,
                client_id
        ),
        client_bounds AS (
            SELECT
                MIN(report_generated_date) AS first_seen,
                MAX(report_generated_date) AS last_seen
            FROM client_daily
        )
        SELECT
            d.client_id,
            d.client_name,
            d.client_group,
            d.parent_org_id,
            b.first_seen,
            b.last_seen,
            d.total_debt AS last_debt_amount
        FROM client_daily d
        CROSS JOIN client_bounds b
        WHERE d.report_generated_date = b.last_seen
        LIMIT 1
    """, {"client_id": client_id}, operation="client_card_historical_identity")


def aging_bucket(row) -> str:
    if row["is_overdue_real"]:
        days = int(row["days_overdue_real"])

        if days <= 7:
            return "1–7 дней"

        if days <= 30:
            return "8–30 дней"

        return "31+ дней"

    if row["is_due_today"]:
        return "К оплате сегодня"

    if row["is_due_in_3_days"]:
        return "К оплате в ближайшие дни"

    return "Не просрочено"


def render_history_section(history_df: pd.DataFrame, rating_migration: pd.DataFrame):
    if history_df.empty:
        return

    selected_period = ui.toggle(
        options=["28", "90", "180", "Все"],
        value="28",
    ).props("outline").classes("mb-4")

    charts_container = ui.column().classes("w-full")

    def get_selected_period_label() -> str:
        if selected_period.value == "Все":
            return "Все"
        return f"{selected_period.value} дней"

    def get_rating_migration_for_selected_period() -> pd.DataFrame:
        if rating_migration.empty:
            return rating_migration

        return rating_migration[
            rating_migration["period_label"] == get_selected_period_label()
        ]

    def get_history_filtered() -> pd.DataFrame:

        result = history_df.copy()

        if selected_period.value != "Все":

            days = int(selected_period.value)

            max_date = result["report_generated_date"].max()

            result = result[
                result["report_generated_date"]
                >= max_date - pd.Timedelta(days=days)
            ]

        return result

    def get_history_kpi(history_filtered: pd.DataFrame) -> dict:
        history_days = int(history_filtered["report_generated_date"].nunique())
        overdue_days = int((history_filtered["overdue_debt"] > 0).sum())

        avg_overdue_share = (
            float(history_filtered["overdue_share_pct"].mean())
            if not history_filtered.empty
            else 0
        )

        max_days_overdue = (
            int(history_filtered["max_days_overdue"].max())
            if not history_filtered.empty
            else 0
        )

        return {
            "history_days": history_days,
            "overdue_days": overdue_days,
            "avg_overdue_share": avg_overdue_share,
            "max_days_overdue": max_days_overdue,
        }

    def render_history_charts():

        history_filtered = get_history_filtered()

        history_kpi = get_history_kpi(history_filtered)

        charts_container.clear()

        with charts_container:

            rating_migration_selected = get_rating_migration_for_selected_period()

            if not rating_migration_selected.empty:
                render_rating_migration_strip(
                    rating_migration_selected.iloc[0]
                )

            ui.label("Ключевые показатели за период").classes(
                "text-sm text-gray-500 mb-3"
            )

            with ui.row().classes("gap-4 mb-6"):
                compact_kpi_card(
                    "Дней в истории",
                    str(history_kpi["history_days"]),
                )
                compact_kpi_card(
                    "Дней с просрочкой",
                    str(history_kpi["overdue_days"]),
                )
                compact_kpi_card(
                    "Средняя просрочка",
                    percent(history_kpi["avg_overdue_share"]),
                )

            with ui.card().classes("w-full p-4 mb-6"):

                ui.label(
                    "История задолженности"
                ).classes(
                    "text-sm text-gray-500 mb-3"
                )

                history_chart = build_client_debt_history_chart(
                    history_filtered
                )

                ui.plotly(history_chart).classes("w-full")

            with ui.card().classes("w-full p-4 mb-6"):

                ui.label(
                    "Структура задолженности по дням"
                ).classes(
                    "text-sm text-gray-500 mb-3"
                )

                structure_chart = build_client_debt_structure_chart(
                    history_filtered
                )

                ui.plotly(structure_chart).classes("w-full")

    selected_period.on_value_change(
        lambda _: render_history_charts()
    )

    render_history_charts()


@ui.page(
    "/client/{client_id}",
    response_timeout=get_page_response_timeout(),
)
@page_build("client_card", "/client/{client_id}")
async def client_card_page(client_id: str, request: Request):

    origin = request.query_params.get("from", "dashboard")

    parent_org_back_id = request.query_params.get("parent_org_id")
    branch_back_name = request.query_params.get("branch_name")

    back_routes = {
        "dashboard": "/",
        "executive": "/executive",
        "deltas": "/deltas",
        "overdue": "/overdue",
        "due-today": "/due-today",
        "due-soon": "/due-soon",
        "executive-long-green": "/executive/long-green",
        "executive-overdue": "/executive/overdue",
        "executive-hidden-risk": "/executive/hidden-risk",
        "executive-branches": "/executive/branches",
        "executive-term-shifts": "/executive/term-shifts",
        "executive-rating-migration": "/executive/rating-migration",
        "payment-attention": "/payment-attention",
        "term-shifts": "/term-shifts",
    }

    if origin == "parent-org" and parent_org_back_id:
        back_target = f"/parent-org/{parent_org_back_id}"
    elif origin == "branch" and branch_back_name:
        back_target = f"/branch/{quote(branch_back_name)}"
    else:
        back_target = back_routes.get(origin, "/")

    df = await query_df("""
        SELECT
            i.parent_org_id,
            i.client_id,
            i.client_name,
            i.client_group,
            i.invoice_date,
            i.order_number,
            i.print_invoice_number,
            i.analytics_type,
            i.due_date,
            i.payment_term_days,
            i.invoice_amount,
            i.days_overdue_real,
            i.is_overdue_real,
            i.is_due_today,
            i.is_due_in_3_days,

            COALESCE(ts.term_shift_count, 0) AS term_shift_count,
            COALESCE(ts.current_term_delta_days, 0) AS term_shift_delta_days,

            CASE
                WHEN COALESCE(ts.term_shift_count, 0) > 0
                THEN i.invoice_amount
                ELSE 0
            END AS shifted_amount,

            ts.original_payment_term_days AS original_payment_term_days,
            ts.current_payment_term_days AS shifted_current_payment_term_days,

            r.stars,
            r.rating_display_label,
            r.confidence_level

        FROM core.v_invoice_detail i

        LEFT JOIN core.v_term_shift_invoice_summary ts
            ON i.client_id = ts.client_id
           AND i.print_invoice_number = ts.print_invoice_number
           AND i.order_number = ts.order_number
           AND i.invoice_date = ts.invoice_date

        LEFT JOIN core.v_client_rating r
            ON i.client_id = r.client_id

        WHERE i.client_id = :client_id

        ORDER BY i.invoice_date DESC
    """, {"client_id": client_id}, operation="client_card_invoices")

    if df.empty:
        historical_client = await get_historical_client_identity(client_id)

        if historical_client.empty:
            ui.label(f"Карточка клиента: {client_id}").classes("text-3xl font-bold mb-4")
            ui.label("Нет данных по клиенту")
            return

        history_df = await query_optional_df("""
            SELECT
                report_generated_date,
                total_debt,
                normal_debt,
                due_soon_only,
                due_today,
                overdue_debt,
                overdue_share_pct,
                max_days_overdue
            FROM core.v_client_daily_history
            WHERE client_id = :client_id
            ORDER BY report_generated_date
        """, {"client_id": client_id}, operation="client_card_historical_history")

        rating_migration = await query_optional_df("""
            SELECT
                period_label,
                period_days,
                sort_order,
                start_snapshot_date,
                end_snapshot_date,
                client_id,
                client_name,
                parent_org_id,
                client_group,
                start_stars,
                end_stars,
                start_rating_label,
                end_rating_label,
                start_confidence_level,
                end_confidence_level,
                rating_delta,
                migration_status,
                migration_label,
                rating_change_label
            FROM core.v_executive_rating_migration_clients
            WHERE client_id = :client_id
        """, {"client_id": client_id}, operation="client_card_historical_migration")

        paid_invoices = await query_optional_df("""
            SELECT
                p.client_id,
                p.client_name,
                p.client_group,
                p.parent_org_id,

                p.print_invoice_number,
                p.order_number,
                p.invoice_date,
                p.due_date,
                p.analytics_type,
                p.payment_term_days,

                p.original_invoice_amount,
                p.amount_before_payment,
                p.amount_after_payment,
                p.paid_amount_detected,

                p.last_seen_snapshot,
                p.estimated_payment_date,
                p.payment_event_type,

                p.actual_payment_term_days,
                p.days_vs_due_date,
                p.payment_behavior_bucket,

                COALESCE(ts.term_shift_count, 0) AS term_shift_count,
                COALESCE(ts.current_term_delta_days, 0) AS term_shift_delta_days

            FROM core.v_recent_paid_invoices_behavior p

            LEFT JOIN core.v_term_shift_invoice_summary ts
                ON p.client_id = ts.client_id
               AND p.print_invoice_number = ts.print_invoice_number
               AND p.order_number = ts.order_number
               AND p.invoice_date = ts.invoice_date

            WHERE p.client_id = :client_id

            ORDER BY
                p.estimated_payment_date DESC,
                p.paid_amount_detected DESC

            LIMIT 20
        """, {"client_id": client_id}, operation="client_card_historical_paid")

        client = historical_client.iloc[0]
        client_name = client.get("client_name") or "—"
        client_group = client.get("client_group")
        parent_org_id = client.get("parent_org_id")
        payment_behavior_metrics = get_payment_behavior_metrics(paid_invoices)

        with ui.row().classes("w-full items-center gap-4 mb-1"):
            ui.label(f"Карточка клиента: {client_name}").classes("text-3xl font-bold")

        with ui.row().classes("items-center gap-1 text-sm text-gray-500 mb-4"):
            ui.label(f"Клиент ID: {client_id}")

            if pd.notna(parent_org_id):
                ui.label("· Вышестоящая организация:")
                ui.button(
                    str(parent_org_id),
                    on_click=lambda: ui.navigate.to(
                        f"/parent-org/{parent_org_id}?from=client&client_id={client_id}"
                    )
                ).props("flat dense color=primary").classes("p-0 min-h-0")

            if pd.notna(client_group):
                ui.label("· Филиал:")
                ui.button(
                    str(client_group),
                    on_click=lambda: ui.navigate.to(
                        f"/branch/{quote(str(client_group))}"
                        f"?from=/client/{client_id}"
                    )
                ).props("flat dense color=primary").classes("p-0 min-h-0")

        top_navigation()

        with ui.row().classes("mb-4"):
            ui.button(
                "← Назад",
                on_click=lambda: ui.navigate.to(back_target)
            ).props("flat color=primary")

        ui.label(
            "Текущей открытой задолженности нет. Клиент отсутствует в последнем срезе, "
            "но найден в истории."
        ).classes("text-sm text-gray-600 mb-4")

        with ui.row().classes("gap-4 mb-6"):
            compact_kpi_card("Текущая задолженность", money(0))
            compact_kpi_card("Последний срез", date_fmt(client.get("last_seen")))
            compact_kpi_card("Последняя сумма", money(client.get("last_debt_amount")))
            compact_kpi_card("Первый срез", date_fmt(client.get("first_seen")))

        render_history_section(history_df, rating_migration)

        render_paid_invoices_table(
            paid_invoices=paid_invoices,
            payment_behavior_metrics=payment_behavior_metrics,
            show_branch=False,
            show_client=False,
            title="Последние оплаченные накладные",
        )

        return
    
    if "shifted_amount" not in df.columns:
        df["shifted_amount"] = df.apply(
            lambda row: (
                row["invoice_amount"]
                if int(row.get("term_shift_count", 0) or 0) > 0
                else 0
            ),
            axis=1,
        )

    # === Paid / closed invoice events ===

    paid_invoices = await query_df("""
        SELECT
            p.client_id,
            p.client_name,
            p.client_group,
            p.parent_org_id,

            p.print_invoice_number,
            p.order_number,
            p.invoice_date,
            p.due_date,
            p.analytics_type,
            p.payment_term_days,

            p.original_invoice_amount,
            p.amount_before_payment,
            p.amount_after_payment,
            p.paid_amount_detected,

            p.last_seen_snapshot,
            p.estimated_payment_date,
            p.payment_event_type,

            p.actual_payment_term_days,
            p.days_vs_due_date,
            p.payment_behavior_bucket,

            COALESCE(ts.term_shift_count, 0) AS term_shift_count,
            COALESCE(ts.current_term_delta_days, 0) AS term_shift_delta_days

        FROM core.v_recent_paid_invoices_behavior p

        LEFT JOIN core.v_term_shift_invoice_summary ts
            ON p.client_id = ts.client_id
           AND p.print_invoice_number = ts.print_invoice_number
           AND p.order_number = ts.order_number
           AND p.invoice_date = ts.invoice_date

        WHERE p.client_id = :client_id

        ORDER BY
            p.estimated_payment_date DESC,
            p.paid_amount_detected DESC

        LIMIT 20
    """, {"client_id": client_id}, operation="client_card_paid_invoices")


    # === Historical data ===

    history_df = await query_df("""
        SELECT
            report_generated_date,
            total_debt,
            normal_debt,
            due_soon_only,
            due_today,
            overdue_debt,
            overdue_share_pct,
            max_days_overdue
        FROM core.v_client_daily_history
        WHERE client_id = :client_id
        ORDER BY report_generated_date
    """, {"client_id": client_id}, operation="client_card_history")

    rating_migration = await query_df("""
        SELECT
            period_label,
            period_days,
            sort_order,
            start_snapshot_date,
            end_snapshot_date,
            client_id,
            client_name,
            parent_org_id,
            client_group,
            start_stars,
            end_stars,
            start_rating_label,
            end_rating_label,
            start_confidence_level,
            end_confidence_level,
            rating_delta,
            migration_status,
            migration_label,
            rating_change_label
        FROM core.v_executive_rating_migration_clients
        WHERE client_id = :client_id
    """, {"client_id": client_id}, operation="client_card_rating_migration")

    credit_quality = await query_df("""
        SELECT *
        FROM core.v_client_credit_quality_rating
        WHERE client_id = :client_id
    """, {"client_id": client_id}, operation="client_card_credit_quality")

    payment_behavior_metrics = get_payment_behavior_metrics(paid_invoices)

    if not history_df.empty:
        active_invoice_as_of_date = history_df["report_generated_date"].max()
    else:
        active_invoice_as_of_date = pd.Timestamp.today().normalize()

    client_name = df["client_name"].iloc[0]
    client_group = df["client_group"].iloc[0]
    parent_org_id = df["parent_org_id"].iloc[0]

    total_debt = df["invoice_amount"].sum()

    overdue_debt = df[df["is_overdue_real"]]["invoice_amount"].sum()

    overdue_pct = (
        overdue_debt / total_debt * 100
        if total_debt else 0
    )

    due_today = df[df["is_due_today"]]["invoice_amount"].sum()

    due_today_pct = (
        due_today / total_debt * 100
        if total_debt else 0
    )

    due_soon_only = df[
        (df["is_due_in_3_days"])
        & (~df["is_due_today"])
    ]["invoice_amount"].sum()

    due_soon_pct = (
        due_soon_only / total_debt * 100
        if total_debt else 0
    )

    shifted_amount = df["shifted_amount"].sum()

    shifted_pct = (
        shifted_amount / total_debt * 100
        if total_debt else 0
    )

    max_days = int(df["days_overdue_real"].max())

    # === Rating ===

    if not credit_quality.empty:
        cq = credit_quality.iloc[0]
        cq_stars = int(cq["credit_quality_stars"])
        rating_text = rating_stars_html(cq_stars)
    else:
        rating_text = "—"

    with ui.row().classes("w-full items-center gap-4 mb-1"):
        ui.label(f"Карточка клиента: {client_name}").classes("text-3xl font-bold")
        ui.html(rating_text).classes("text-xl")

    with ui.row().classes("items-center gap-1 text-sm text-gray-500 mb-4"):
        ui.label(f"Клиент ID: {client_id} · Вышестоящая организация:")

        ui.button(
            str(parent_org_id),
            on_click=lambda: ui.navigate.to(
                f"/parent-org/{parent_org_id}?from=client&client_id={client_id}"
            )
        ).props("flat dense color=primary").classes("p-0 min-h-0")

        ui.label("· Филиал:")

        ui.button(
            str(client_group),
            on_click=lambda: ui.navigate.to(
                f"/branch/{quote(str(client_group))}"
                f"?from=/client/{client_id}"
            )
        ).props("flat dense color=primary").classes("p-0 min-h-0")

    top_navigation()

    with ui.row().classes("mb-4"):
        ui.button(
            "← Назад",
            on_click=lambda: ui.navigate.to(back_target)
        ).props("flat color=primary")

    render_receivables_kpi_strip(
        total_debt=money(total_debt),
        overdue_debt=money(overdue_debt),
        overdue_share=percent(overdue_pct),
        due_today=money(due_today),
        due_today_share=percent(due_today_pct),
        due_soon=money(due_soon_only),
        due_soon_share=percent(due_soon_pct),
        shifted_amount=money(shifted_amount),
        shifted_share=percent(shifted_pct),
    )

    if not credit_quality.empty:
        render_credit_quality_strip(
            credit_quality.iloc[0]
        )
    
    if not paid_invoices.empty:
        render_payment_behavior_strip(
            paid_invoices
        )

    # Rating migration strip is rendered together with the selected
    # historical period below, because it depends on the active window.

    # === Aging buckets ===

    aging_df = df.copy()

    aging_df["aging_bucket"] = aging_df.apply(
        aging_bucket,
        axis=1
    )

    bucket_order = [
        "Не просрочено",
        "К оплате в ближайшие дни",
        "К оплате сегодня",
        "1–7 дней",
        "8–30 дней",
        "31+ дней",
    ]

    bucket_colors = {
        "Не просрочено": "#22c55e",
        "К оплате в ближайшие дни": "#fde68a",
        "К оплате сегодня": "#f59e0b",
        "1–7 дней": "#fb923c",
        "8–30 дней": "#f97316",
        "31+ дней": "#ef4444",
    }

    aging_summary = (
        aging_df.groupby("aging_bucket", as_index=False)["invoice_amount"]
        .sum()
        .rename(columns={"invoice_amount": "amount"})
    )

    aging_summary = (
        pd.DataFrame({"aging_bucket": bucket_order})
        .merge(aging_summary, on="aging_bucket", how="left")
        .fillna({"amount": 0})
    )

    aging_summary["share"] = (
        aging_summary["amount"] / total_debt * 100
        if total_debt else 0
    )

    aging_summary["amount_fmt"] = aging_summary["amount"].apply(money)
    aging_summary["share_fmt"] = aging_summary["share"].apply(percent)

    with ui.card().classes("w-full p-4 mb-6"):

        ui.label("Распределение задолженности по срокам").classes(
            "text-sm text-gray-500 mb-3"
        )

        for _, row in aging_summary.iterrows():

            bucket = row["aging_bucket"]
            amount_fmt = row["amount_fmt"]
            share_fmt = row["share_fmt"]

            width = (
                max(float(row["share"]), 1)
                if float(row["amount"]) > 0 else 0
            )

            color = bucket_colors[bucket]

            with ui.row().classes("w-full items-center gap-4 mb-2"):

                ui.label(bucket).classes("w-32 text-sm")

                with ui.element(
                    "div"
                ).classes(
                    "flex-1 bg-gray-100 rounded-full h-5 overflow-hidden"
                ):

                    ui.element("div").classes(
                        "h-5 rounded-full"
                    ).style(
                        f"width: {width}%; background-color: {color};"
                    )

                ui.label(
                    f"{amount_fmt} · {share_fmt}"
                ).classes(
                    "w-40 text-right text-sm text-gray-600"
                )

    # === Historical analytics ===

    render_history_section(history_df, rating_migration)

    # === Active invoices table ===

    render_work_invoices_table(
        invoices=df,
        show_branch=False,
        show_client=False,
        title="Накладные в работе",
        behavior_metrics=payment_behavior_metrics,
        as_of_date=active_invoice_as_of_date,
    )

    # === Recently paid invoices table ===

    render_paid_invoices_table(
        paid_invoices=paid_invoices,
        payment_behavior_metrics=payment_behavior_metrics,
        show_branch=False,
        show_client=False,
        title="Последние оплаченные накладные",
    )
