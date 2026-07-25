from pathlib import Path
import os

import pandas as pd
from dotenv import load_dotenv
from fastapi import Request
from nicegui import ui
from sqlalchemy import create_engine

from src.app.components.navigation import top_navigation
from src.app.services.database import read_dataframe
from src.app.services.performance import page_build
from src.app.services.settings import get_page_response_timeout
from src.app.components.rating_stars import rating_stars_html
from src.app.components.charts import (
    build_client_debt_history_chart,
    build_client_debt_structure_chart,
)
from src.app.components.kpi_cards import compact_kpi_card
from src.app.components.receivables_kpi_strip import render_receivables_kpi_strip
from src.app.components.credit_quality_strip import render_credit_quality_strip
from src.app.components.portfolio_payment_behavior_strip import (
    render_portfolio_payment_behavior_strip,
)
from src.app.components.portfolio_rating_period_strip import (
    render_portfolio_rating_period_strip,
)
from src.app.components.work_invoices_table import (
    render_work_invoices_table,
)
from src.app.components.paid_invoices_table import (
    render_paid_invoices_table,
)
from src.app.components.clients_table import render_clients_table
from src.app.components.portfolio_payment_behavior_strip import (
    get_portfolio_payment_behavior_metrics,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env")

engine = create_engine(
    f"postgresql+psycopg2://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@"
    f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)


async def query_df(sql: str, params: dict | None = None, *, operation: str) -> pd.DataFrame:
    return await read_dataframe(engine, sql, operation=operation, params=params)


def money(value) -> str:
    if pd.isna(value):
        return "0"
    return f"{float(value):,.0f}".replace(",", " ")


def percent(value) -> str:
    if pd.isna(value):
        return "0%"
    return f"{float(value):.1f}%"


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


    with ui.card().classes("px-4 py-2"):
        with ui.row().classes("items-center gap-2"):
            ui.label(indicator["icon"]).classes("text-lg")
            ui.label(indicator["label"]).classes(
                f"text-sm font-medium {label_class}"
            )
            ui.label(indicator.get("detail", "")).classes(
                "text-xs text-gray-500"
            )


@ui.page(
    "/parent-org/{parent_org_id}",
    response_timeout=get_page_response_timeout(),
)
@page_build("parent_org_card", "/parent-org/{parent_org_id}")
async def parent_org_card_page(parent_org_id: str, request: Request):
    source_client_id = request.query_params.get("client_id")
    back_target = f"/client/{source_client_id}?from=dashboard" if source_client_id else "/"

    invoices = await query_df("""
        SELECT
            i.parent_org_id,
            i.client_id,
            i.client_name,
            i.client_group,

            r.stars,
            r.rating_display_label,
            r.confidence_level,

            i.invoice_date,
            i.due_date,
            i.invoice_amount,
            i.order_number,
            i.print_invoice_number,
            i.analytics_type,
            i.payment_term_days,

            i.days_overdue_real,
            i.days_until_due_real,

            i.is_overdue_real,
            i.is_due_today,
            i.is_due_in_3_days,
            i.is_due_in_7_days,

            COALESCE(ts.term_shift_count, 0) AS term_shift_count,
            COALESCE(ts.current_term_delta_days, 0) AS term_shift_delta_days,

            CASE
                WHEN COALESCE(ts.term_shift_count, 0) > 0
                THEN i.invoice_amount
                ELSE 0
            END AS shifted_amount,

            CASE WHEN i.is_overdue_real THEN i.invoice_amount ELSE 0 END AS overdue_amount,
            CASE WHEN i.is_due_today THEN i.invoice_amount ELSE 0 END AS due_today_amount,
            CASE
                WHEN i.is_due_in_3_days AND NOT i.is_due_today
                THEN i.invoice_amount
                ELSE 0
            END AS due_soon_only_amount
            FROM core.v_invoice_detail i

            LEFT JOIN core.v_term_shift_invoice_summary ts
                ON i.client_id = ts.client_id
                AND i.print_invoice_number = ts.print_invoice_number
                AND i.order_number = ts.order_number
                AND i.invoice_date = ts.invoice_date

            LEFT JOIN core.v_client_rating r
                ON i.client_id = r.client_id
            WHERE i.parent_org_id = :parent_org_id
        ORDER BY i.client_group, i.client_name, i.due_date
    """, {"parent_org_id": parent_org_id}, operation="parent_org_card_invoices")

    if invoices.empty:
        ui.label(f"Карточка вышестоящей: {parent_org_id}").classes("text-3xl font-bold mb-2")
        top_navigation()
        ui.label("Нет данных по этой вышестоящей организации.").classes("text-lg text-red-700")
        return

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

        WHERE p.parent_org_id = :parent_org_id

        ORDER BY
            p.estimated_payment_date DESC,
            p.paid_amount_detected DESC

        LIMIT 30
    """, {"parent_org_id": parent_org_id}, operation="parent_org_card_paid_invoices")

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
        FROM core.v_parent_org_daily_history
        WHERE parent_org_id = :parent_org_id
        ORDER BY report_generated_date
    """, {"parent_org_id": parent_org_id}, operation="parent_org_card_history")

    rating_migration = await query_df("""
        WITH current_client_debt AS (
            SELECT
                client_id,
                SUM(invoice_amount) AS current_total_debt
            FROM core.v_invoice_detail
            WHERE parent_org_id = :parent_org_id
            GROUP BY client_id
        )
        SELECT
            m.*,
            COALESCE(d.current_total_debt, 0) AS current_total_debt
        FROM core.v_executive_rating_migration_clients m
        LEFT JOIN current_client_debt d
            ON m.client_id = d.client_id
        WHERE m.parent_org_id = :parent_org_id
    """, {"parent_org_id": parent_org_id}, operation="parent_org_card_rating_migration")

    credit_quality_clients = await query_df("""
        SELECT *
        FROM core.v_client_credit_quality_rating
        WHERE parent_org_id = :parent_org_id
    """, {"parent_org_id": parent_org_id}, operation="parent_org_card_credit_quality")

    summary = (
        invoices
        .groupby("parent_org_id", as_index=False)
        .agg(
            client_count=("client_id", "nunique"),
            invoice_count=("invoice_amount", "count"),
            total_debt=("invoice_amount", "sum"),
            due_today=("due_today_amount", "sum"),
            due_soon_only=("due_soon_only_amount", "sum"),
            overdue_debt=("overdue_amount", "sum"),
            shifted_amount=("shifted_amount", "sum"),
            max_days_overdue=("days_overdue_real", "max"),
        )
    )

    summary["overdue_share_pct"] = (
        summary["overdue_debt"] / summary["total_debt"] * 100
    ).fillna(0)

    clients = await query_df("""
        SELECT *
        FROM core.v_client_operational_summary
        WHERE parent_org_id = :parent_org_id
        ORDER BY
            operational_sort_order,
            overdue_debt DESC,
            due_today DESC,
            due_soon_only DESC,
            payment_attention_amount DESC,
            shifted_amount DESC,
            total_debt DESC
    """, {"parent_org_id": parent_org_id}, operation="parent_org_card_clients")

    if summary.empty or invoices.empty:
        ui.label("Нет данных по этой вышестоящей организации.").classes("text-lg text-red-700")
        return

    s = summary.iloc[0]

    s_overdue_share_pct = (s.overdue_debt / s.total_debt * 100) if s.total_debt else 0
    s_due_today_share_pct = (s.due_today / s.total_debt * 100) if s.total_debt else 0
    s_due_soon_share_pct = (s.due_soon_only / s.total_debt * 100) if s.total_debt else 0
    s_shifted_share_pct = (s.shifted_amount / s.total_debt * 100) if s.total_debt else 0

    if not credit_quality_clients.empty:
        cq_header_df = credit_quality_clients.copy()

        cq_values = pd.to_numeric(
            cq_header_df["credit_quality_stars"],
            errors="coerce",
        )

        cq_weights = pd.to_numeric(
            cq_header_df["total_debt"],
            errors="coerce",
        ).fillna(0)

        cq_mask = cq_values.notna() & (cq_weights > 0)

        portfolio_rating_value = (
            float((cq_values[cq_mask] * cq_weights[cq_mask]).sum() / cq_weights[cq_mask].sum())
            if cq_mask.any()
            else 0
        )
    else:
        portfolio_rating_value = 0

    portfolio_stars = max(1, min(5, int(round(portfolio_rating_value)))) if portfolio_rating_value else None

    with ui.row().classes("w-full items-center gap-4 mb-1"):
        ui.label(f"Карточка вышестоящей: {parent_org_id}").classes("text-3xl font-bold")
        if portfolio_stars:
            ui.html(rating_stars_html(portfolio_stars)).classes("text-xl")
            ui.label(f"({portfolio_rating_value:.1f})").classes("text-lg font-bold text-gray-600")

    ui.label(
        f"Вышестоящая организация ID: {parent_org_id} · клиентов: {int(s.client_count)}"
    ).classes("text-sm text-gray-500 mb-4")

    top_navigation()

    with ui.row().classes("mb-4"):
        ui.button("← Назад", on_click=lambda: ui.navigate.to(back_target)).props("flat color=primary")

    render_receivables_kpi_strip(
        total_debt=money(s.total_debt),
        overdue_debt=money(s.overdue_debt),
        overdue_share=percent(s_overdue_share_pct),
        due_today=money(s.due_today),
        due_today_share=percent(s_due_today_share_pct),
        due_soon=money(s.due_soon_only),
        due_soon_share=percent(s_due_soon_share_pct),
        shifted_amount=money(s.shifted_amount),
        shifted_share=percent(s_shifted_share_pct),
    )

    def _weighted_average(source_df: pd.DataFrame, value_col: str, weight_col: str = "total_debt") -> float:
        if source_df.empty or value_col not in source_df.columns:
            return 0
        values = pd.to_numeric(source_df[value_col], errors="coerce")
        weights = (
            pd.to_numeric(source_df[weight_col], errors="coerce").fillna(0)
            if weight_col in source_df.columns
            else pd.Series([1] * len(source_df), index=source_df.index)
        )
        mask = values.notna() & (weights > 0)
        if not mask.any():
            mask = values.notna()
            weights = pd.Series([1] * len(source_df), index=source_df.index)
        if not mask.any():
            return 0
        return float((values[mask] * weights[mask]).sum() / weights[mask].sum())

    if not credit_quality_clients.empty:
        cq_df = credit_quality_clients.copy()

        def _num_col(name: str) -> pd.Series:
            if name not in cq_df.columns:
                return pd.Series([0] * len(cq_df), index=cq_df.index, dtype="float64")
            return pd.to_numeric(cq_df[name], errors="coerce").fillna(0)

        total_cq_debt = float(_num_col("total_debt").sum())
        severity_penalty = float(_num_col("severity_penalty").max())

        severity_level_order = {"NONE": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
        severity_level = "NONE"
        if "severity_level" in cq_df.columns:
            severity_level = max(
                cq_df["severity_level"].fillna("NONE").astype(str),
                key=lambda value: severity_level_order.get(value, 0),
            )

        reasons: list[str] = []
        if "severity_reasons" in cq_df.columns:
            for value in cq_df["severity_reasons"].dropna():
                if isinstance(value, str):
                    items = value.strip("{}").split(",")
                elif isinstance(value, (list, tuple)):
                    items = value
                else:
                    items = []
                for item in items:
                    cleaned = str(item).strip().strip('"')
                    if cleaned and cleaned not in reasons:
                        reasons.append(cleaned)

        green_90_debt = float(_num_col("green_90_plus_debt").sum())
        green_120_debt = float(_num_col("green_120_plus_debt").sum())

        base_stars_value = _weighted_average(cq_df, "base_stars")
        cq_stars_value = _weighted_average(cq_df, "credit_quality_stars")

        cq_summary = pd.Series({
            "base_stars": max(1, min(5, int(round(base_stars_value or 1)))),
            "credit_quality_stars": max(1, min(5, int(round(cq_stars_value or 1)))),
            "severity_level": severity_level,
            "severity_penalty": severity_penalty,
            "severity_reasons": reasons,
            "total_debt": total_cq_debt,
            "weighted_avg_payment_term_days": _weighted_average(cq_df, "weighted_avg_payment_term_days"),
            "max_payment_term_days": int(_num_col("max_payment_term_days").max()),
            "term_shift_count": int(_num_col("term_shift_count").sum()),
            "repeated_shift_invoice_count": int(_num_col("repeated_shift_invoice_count").sum()),
            "green_90_plus_share_pct": green_90_debt / total_cq_debt * 100 if total_cq_debt else 0,
            "green_120_plus_debt": green_120_debt,
        })

        render_credit_quality_strip(cq_summary)

    if not paid_invoices.empty:
        render_portfolio_payment_behavior_strip(paid_invoices)

    # === Aging ===

    aging_df = invoices.copy()
    aging_df["aging_bucket"] = aging_df.apply(aging_bucket, axis=1)

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

    total_debt = float(s.total_debt)
    aging_summary["share"] = aging_summary["amount"] / total_debt * 100 if total_debt else 0
    aging_summary["amount_fmt"] = aging_summary["amount"].apply(money)
    aging_summary["share_fmt"] = aging_summary["share"].apply(percent)

    with ui.card().classes("w-full p-4 mb-6"):
        ui.label("Распределение задолженности по срокам").classes("text-sm text-gray-500 mb-3")

        for _, row in aging_summary.iterrows():
            bucket = row["aging_bucket"]
            width = max(float(row["share"]), 1) if float(row["amount"]) > 0 else 0

            with ui.row().classes("w-full items-center gap-4 mb-2"):
                ui.label(bucket).classes("w-40 text-sm")

                with ui.element("div").classes("flex-1 bg-gray-100 rounded-full h-5 overflow-hidden"):
                    ui.element("div").classes("h-5 rounded-full").style(
                        f"width: {width}%; background-color: {bucket_colors[bucket]};"
                    )

                ui.label(f"{row['amount_fmt']} · {row['share_fmt']}").classes(
                    "w-40 text-right text-sm text-gray-600"
                )

    # === Historical analytics ===

    if not history_df.empty:

        selected_period = ui.toggle(
            options=["28", "90", "180", "Все"],
            value="28",
        ).props("outline").classes("mb-4")

        charts_container = ui.column().classes("w-full")

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

        def get_selected_period_label() -> str:
            if selected_period.value == "Все":
                return "Все"
            return f"{selected_period.value} дней"

        def get_history_kpi(history_filtered: pd.DataFrame) -> dict:
            history_days = int(history_filtered["report_generated_date"].nunique())
            overdue_days = int((history_filtered["overdue_debt"] > 0).sum())
            avg_overdue_share = (
                float(history_filtered["overdue_share_pct"].mean())
                if not history_filtered.empty
                else 0
            )
            return {
                "history_days": history_days,
                "overdue_days": overdue_days,
                "avg_overdue_share": avg_overdue_share,
            }

        def render_history_charts():
            history_filtered = get_history_filtered()
            history_kpi = get_history_kpi(history_filtered)

            charts_container.clear()

            with charts_container:
                period_label = get_selected_period_label()
                migration_period_df = (
                    rating_migration[
                        rating_migration["period_label"] == period_label
                    ]
                    if not rating_migration.empty and "period_label" in rating_migration.columns
                    else pd.DataFrame()
                )

                render_portfolio_rating_period_strip(
                    migration_period_df,
                    period_label=period_label,
                    fallback_rating=portfolio_rating_value,
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
                    ui.label("История задолженности").classes(
                        "text-sm text-gray-500 mb-3"
                    )

                    history_chart = build_client_debt_history_chart(history_filtered)
                    ui.plotly(history_chart).classes("w-full")

                with ui.card().classes("w-full p-4 mb-6"):
                    ui.label("Структура задолженности по дням").classes(
                        "text-sm text-gray-500 mb-3"
                    )

                    structure_chart = build_client_debt_structure_chart(history_filtered)
                    ui.plotly(structure_chart).classes("w-full")

        selected_period.on_value_change(
            lambda _: render_history_charts()
        )

        render_history_charts()

    # === Контрагенты ===

    clients_table = render_clients_table(
        clients=clients,
        title="Контрагенты",
        subtitle=None,
        show_branch=True,
        show_search=False,
        from_route="parent-org",
        visible_columns=[
            "client_group",
            "client",
            "rating",
            "total_debt",
            "due_today",
            "due_soon_only",
            "normal_window_amount",
            "payment_attention_amount",
            "overdue_debt",
            "overdue_share_pct",
            "shifted_amount",
            "shifted_share_pct",
        ],
    )
    # === Накладные в работе ===

    portfolio_behavior_metrics = get_portfolio_payment_behavior_metrics(
        paid_invoices
    )
    
    invoice_table = render_work_invoices_table(
        invoices=invoices,
        title="Накладные в работе",
        show_branch=True,
        show_client=True,
        behavior_metrics=portfolio_behavior_metrics,
        as_of_date=pd.Timestamp.today().normalize(),
    )

    # === Последние оплаченные накладные ===

    paid_table = render_paid_invoices_table(
        paid_invoices=paid_invoices,
        payment_behavior_metrics=portfolio_behavior_metrics,
        show_branch=True,
        show_client=True,
        title="Последние оплаченные накладные",
    )

    def open_client(event):
        ui.navigate.to(
            f"/client/{event.args}?from=parent-org&parent_org_id={parent_org_id}"
        )

    def open_branch(event):
        ui.navigate.to(
            f"/branch/{event.args}?from=/parent-org/{parent_org_id}"
        )

    if clients_table is not None:
        clients_table.on("branch_click", open_branch)
        clients_table.on("client_click", open_client)

    if invoice_table is not None:
        invoice_table.on("branch_click", open_branch)
        invoice_table.on("client_click", open_client)

    if paid_table is not None:
        paid_table.on("branch_click", open_branch)
        paid_table.on("client_click", open_client)
