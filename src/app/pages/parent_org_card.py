from pathlib import Path
import os
from urllib.parse import quote

import pandas as pd
from dotenv import load_dotenv
from fastapi import Request
from nicegui import ui
from sqlalchemy import create_engine, text

from src.app.components.navigation import top_navigation
from src.app.components.rating_stars import rating_stars_html
from src.app.components.charts import (
    build_client_debt_history_chart,
    build_client_debt_structure_chart,
)
from src.app.components.behavioral_indicators import (
    get_debt_trend_indicator,
    get_overdue_behavior_indicator,
    get_volatility_indicator,
)
from src.app.components.rating_dynamics import (
    render_portfolio_rating_strip,
)

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


def date_fmt(value) -> str:
    if pd.isna(value):
        return ""
    return pd.to_datetime(value).strftime("%d.%m.%Y")


def kpi_card(title: str, value: str, subtitle: str | None = None):
    with ui.card().classes("w-64 h-36 p-4"):
        with ui.column().classes("w-full h-full items-center justify-between text-center"):
            ui.label(title).classes("text-sm text-gray-500 h-6 flex items-center justify-center")
            ui.label(value).classes("text-2xl font-bold h-10 flex items-center justify-center")
            ui.label(subtitle or "").classes("text-sm text-gray-500 h-8 flex items-center justify-center")


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


def indicator_card(indicator: dict):
    color_classes = {
        "green": "text-green-600",
        "orange": "text-orange-600",
        "red": "text-red-600",
        "blue": "text-blue-600",
        "gray": "text-gray-600",
    }

    label_class = color_classes.get(indicator.get("color"), "text-gray-600")

    with ui.card().classes("px-4 py-2"):
        with ui.row().classes("items-center gap-2"):
            ui.label(indicator["icon"]).classes("text-lg")
            ui.label(indicator["label"]).classes(
                f"text-sm font-medium {label_class}"
            )
            ui.label(indicator.get("detail", "")).classes(
                "text-xs text-gray-500"
            )


@ui.page("/parent-org/{parent_org_id}")
def parent_org_card_page(parent_org_id: str, request: Request):
    source_client_id = request.query_params.get("client_id")
    back_target = f"/client/{source_client_id}?from=dashboard" if source_client_id else "/"

    invoices = query_df("""
        SELECT
            i.parent_org_id,
            i.client_id,
            i.client_name,
            i.client_group,

            COALESCE(cq.credit_quality_stars, r.stars) AS stars,
            COALESCE(cq.credit_quality_display_label, r.rating_display_label) AS rating_display_label,
            COALESCE(cq.confidence_level, r.confidence_level) AS confidence_level,

            i.invoice_date,
            i.order_number,
            i.print_invoice_number,
            i.analytics_type,
            i.due_date,
            i.payment_term_days,
            i.invoice_amount,

            i.days_overdue_real,
            i.days_until_due_real,

            i.is_overdue_real,
            i.is_due_today,
            i.is_due_in_3_days,
            i.is_due_in_7_days,

            COALESCE(ts.term_shift_count, 0) AS term_shift_count,
            COALESCE(ts.current_term_delta_days, 0) AS term_shift_delta_days,
            ts.original_payment_term_days AS original_payment_term_days,
            ts.current_payment_term_days AS shifted_current_payment_term_days,

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

        LEFT JOIN core.v_client_credit_quality_rating cq
            ON i.client_id = cq.client_id

        WHERE i.parent_org_id = :parent_org_id
        ORDER BY i.client_group, i.client_name, i.due_date
    """, {"parent_org_id": parent_org_id})

    if invoices.empty:
        ui.label(f"Карточка вышестоящей: {parent_org_id}").classes("text-3xl font-bold mb-2")
        top_navigation()
        ui.label("Нет данных по этой вышестоящей организации.").classes("text-lg text-red-700")
        return

    paid_invoices = query_df("""
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

        FROM core.v_recent_paid_invoices p

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
    """, {"parent_org_id": parent_org_id})

    history_df = query_df("""
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
    """, {"parent_org_id": parent_org_id})

    portfolio_rating_df = query_df("""
        SELECT *
        FROM core.v_parent_org_rating_dynamics
        WHERE parent_org_id = :parent_org_id
    """, {"parent_org_id": parent_org_id})

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
            max_days_overdue=("days_overdue_real", "max"),
        )
    )

    summary["overdue_share_pct"] = (
        summary["overdue_debt"] / summary["total_debt"] * 100
    ).fillna(0)

    clients = (
        invoices
        .groupby(["parent_org_id", "client_group", "client_id", "client_name", "stars"], as_index=False)
        .agg(
            invoice_count=("invoice_amount", "count"),
            total_debt=("invoice_amount", "sum"),
            due_today=("due_today_amount", "sum"),
            due_soon_only=("due_soon_only_amount", "sum"),
            overdue_debt=("overdue_amount", "sum"),
            max_days_overdue=("days_overdue_real", "max"),
        )
    )

    clients["overdue_share_pct"] = (
        clients["overdue_debt"] / clients["total_debt"] * 100
    ).fillna(0)

    clients = clients.sort_values(
        by=["overdue_debt", "total_debt"],
        ascending=[False, False],
    )

    ui.label(f"Карточка вышестоящей: {parent_org_id}").classes("text-3xl font-bold mb-2")
    top_navigation()

    if summary.empty or invoices.empty:
        ui.label("Нет данных по этой вышестоящей организации.").classes("text-lg text-red-700")
        return

    with ui.row().classes("mb-4"):
        ui.button("← Назад", on_click=lambda: ui.navigate.to(back_target)).props("flat color=primary")

    s = summary.iloc[0]
    selected_branches: list[str] = []

    with ui.row().classes("gap-4 mb-6"):
        kpi_card("Общий долг", money(s.total_debt))
        kpi_card("К оплате сегодня", money(s.due_today))
        kpi_card("К оплате в ближайшие дни", money(s.due_soon_only))
        kpi_card("Просрочено", money(s.overdue_debt), f"{percent(s.overdue_share_pct)} от общего долга")
        kpi_card("Количество организаций", str(int(s.client_count)))

    if not portfolio_rating_df.empty:
        render_portfolio_rating_strip(portfolio_rating_df.iloc[0])

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

        def render_history_charts():
            history_filtered = get_history_filtered()

            debt_trend = get_debt_trend_indicator(history_filtered)
            overdue_behavior = get_overdue_behavior_indicator(history_filtered)
            volatility = get_volatility_indicator(history_filtered)

            charts_container.clear()

            with charts_container:
                ui.label("Интерпретация периода").classes(
                    "text-sm text-gray-500 mb-3"
                )

                with ui.row().classes("gap-3 mb-4"):
                    indicator_card(debt_trend)
                    indicator_card(overdue_behavior)
                    indicator_card(volatility)

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

        selected_period.on_value_change(lambda _: render_history_charts())
        render_history_charts()

    # === Контрагенты ===

    def prepare_client_rows():
        df = clients.copy()

        if selected_branches:
            df = df[df["client_group"].isin(selected_branches)]

        df["total_debt_fmt"] = df["total_debt"].apply(money)
        df["due_today_fmt"] = df["due_today"].apply(money)
        df["due_soon_only_fmt"] = df["due_soon_only"].apply(money)
        df["overdue_debt_fmt"] = df["overdue_debt"].apply(money)
        df["overdue_share_fmt"] = df["overdue_share_pct"].apply(percent)
        df["rating_html"] = df["stars"].apply(
            lambda value: rating_stars_html(int(value)) if pd.notna(value) else "—"
        )

        return df.to_dict("records")

    with ui.row().classes("items-center gap-4"):
        selected_branch_label = ui.label("Показаны все филиалы").classes("text-sm text-gray-500")
        ui.button("ВСЕ ФИЛИАЛЫ", on_click=lambda: reset_branch_filter()).props("flat color=primary")

    ui.label("Контрагенты").classes("text-xl mt-6")

    clients_table = ui.table(
        columns=[
            {"name": "client_group", "label": "Филиал", "field": "client_group", "sortable": True},
            {"name": "client_name", "label": "Наименование", "field": "client_name", "sortable": True, "align": "left"},
            {"name": "rating_html", "label": "Рейтинг", "field": "rating_html", "align": "center"},
            {"name": "total_debt", "label": "Весь долг", "field": "total_debt", "align": "right", "sortable": True},
            {"name": "due_today", "label": "К оплате сегодня", "field": "due_today", "align": "right", "sortable": True},
            {"name": "due_soon_only", "label": "К оплате в ближайшие дни", "field": "due_soon_only", "align": "right", "sortable": True},
            {"name": "overdue_debt", "label": "Просрочка", "field": "overdue_debt", "align": "right", "sortable": True},
            {"name": "overdue_share_pct", "label": "% просрочки", "field": "overdue_share_pct", "align": "right", "sortable": True},
        ],
        rows=prepare_client_rows(),
    ).classes("w-full")

    clients_table.add_slot(
        "body-cell-rating_html",
        """
        <q-td :props="props" class="text-center">
            <span v-html="props.row.rating_html"></span>
        </q-td>
        """,
    )

    clients_table.add_slot(
        "body-cell-client_group",
        """
        <q-td :props="props">
            <q-btn flat dense color="primary" :label="props.row.client_group"
                   @click="$parent.$emit('branch_open', props.row.client_group)" />
        </q-td>
        """,
    )

    clients_table.add_slot(
        "body-cell-client_name",
        """
        <q-td :props="props" class="text-left">
            <q-btn flat dense color="primary"
                   :label="props.row.client_id + ' · ' + props.row.client_name"
                   @click="$parent.$emit('client_click', props.row.client_id)" />
        </q-td>
        """,
    )

    for column_name, fmt_name in [
        ("total_debt", "total_debt_fmt"),
        ("due_today", "due_today_fmt"),
        ("due_soon_only", "due_soon_only_fmt"),
        ("overdue_debt", "overdue_debt_fmt"),
    ]:
        clients_table.add_slot(
            f"body-cell-{column_name}",
            f"""
            <q-td :props="props" class="text-right">
                {{{{ props.row.{fmt_name} }}}}
            </q-td>
            """,
        )

    clients_table.add_slot(
        "body-cell-overdue_share_pct",
        """
        <q-td :props="props">
            <q-badge
                :color="props.row.overdue_share_pct > 20 ? 'red' : props.row.overdue_share_pct > 0 ? 'orange' : 'green'"
                :label="props.row.overdue_share_fmt"
            />
        </q-td>
        """,
    )

    # === Накладные ===

    def prepare_invoice_rows():
        df = invoices.copy()

        if selected_branches:
            df = df[df["client_group"].isin(selected_branches)]

        df["invoice_date_fmt"] = df["invoice_date"].apply(date_fmt)
        df["due_date_fmt"] = df["due_date"].apply(date_fmt)
        df["invoice_amount_fmt"] = df["invoice_amount"].apply(money_precise)
        df["payment_term_days_fmt"] = df["payment_term_days"].apply(
            lambda value: "" if pd.isna(value) else str(int(value))
        )
        df["term_shift_count"] = df["term_shift_count"].fillna(0).astype(int)
        df["term_shift_delta_days"] = df["term_shift_delta_days"].fillna(0).astype(int)
        df["term_shift_fmt"] = df.apply(
            lambda row: (
                f"{int(row['term_shift_count'])} / +{int(row['term_shift_delta_days'])}"
                if int(row["term_shift_count"]) > 0
                else "—"
            ),
            axis=1,
        )
        df["has_term_shift"] = df["term_shift_count"] > 0
        df["is_overdue_fmt"] = df["is_overdue_real"].map({True: "Да", False: "Нет"})
        df["aging_bucket"] = df.apply(aging_bucket, axis=1)

        return df.to_dict("records")

    ui.label("Накладные").classes("text-xl mt-6")

    invoice_table = ui.table(
        columns=[
            {"name": "client_group", "label": "Филиал", "field": "client_group", "sortable": True},
            {"name": "client_name", "label": "Наименование", "field": "client_name", "sortable": True, "align": "left"},
            {"name": "invoice_date", "label": "Дата накладной", "field": "invoice_date_fmt", "sortable": True},
            {"name": "order_number", "label": "Номер заказа", "field": "order_number", "sortable": True},
            {"name": "print_invoice_number", "label": "Печ. номер", "field": "print_invoice_number", "sortable": True},
            {"name": "analytics_type", "label": "Аналитика", "field": "analytics_type", "sortable": True},
            {"name": "due_date", "label": "Оплатить до", "field": "due_date_fmt", "sortable": True},
            {"name": "payment_term_days", "label": "Отсрочка", "field": "payment_term_days_fmt", "align": "right"},
            {"name": "term_shift_fmt", "label": "Переносы", "field": "term_shift_fmt", "align": "center"},
            {"name": "invoice_amount_fmt", "label": "Сумма", "field": "invoice_amount_fmt", "align": "right"},
            {"name": "days_overdue_real", "label": "Просрочка (дни)", "field": "days_overdue_real", "align": "right", "sortable": True},
            {"name": "aging_bucket", "label": "Срок просрочки", "field": "aging_bucket", "align": "center"},
            {"name": "is_overdue_fmt", "label": "Просрочено", "field": "is_overdue_fmt", "align": "center"},
        ],
        rows=prepare_invoice_rows(),
    ).classes("w-full")

    invoice_table.add_slot(
        "body",
        """
        <q-tr :props="props"
            :class="
                props.row.is_overdue_real
                    ? 'bg-red-100'
                    : props.row.is_due_today
                        ? 'bg-orange-100'
                        : props.row.is_due_in_3_days
                            ? 'bg-yellow-100'
                            : ''
            ">
            <q-td v-for="col in props.cols" :key="col.name" :props="props">

                <template v-if="col.name === 'client_group'">
                    <q-btn
                        flat
                        dense
                        color="primary"
                        :label="props.row.client_group"
                        @click="$parent.$emit('branch_open', props.row.client_group)"
                    />
                </template>

                <template v-else-if="col.name === 'client_name'">
                    <q-btn
                        flat
                        dense
                        color="primary"
                        :label="props.row.client_id + ' · ' + props.row.client_name"
                        @click="$parent.$emit('client_click', props.row.client_id)"
                    />
                </template>

                <template v-else-if="col.name === 'payment_term_days'">
                    <q-badge
                        :color="parseInt(col.value || 0) >= 45 ? 'red' : 'grey'"
                        :label="col.value"
                    />
                </template>

                <template v-else-if="col.name === 'term_shift_fmt'">
                    <q-badge
                        v-if="props.row.has_term_shift"
                        color="red"
                        :label="col.value"
                    />
                    <span v-else class="text-grey-6">—</span>
                </template>

                <template v-else>
                    {{ col.value }}
                </template>
            </q-td>
        </q-tr>
        """,
    )

    # === Recently paid invoices table ===

    if not paid_invoices.empty:
        ui.label("Последние оплаченные накладные").classes("text-xl font-bold mt-6 mb-1")
        ui.label(
            "Расчетная дата оплаты восстановлена по исчезновению накладной из открытой дебиторки "
            "или по снижению открытого остатка между срезами."
        ).classes("text-sm text-gray-500 mb-3")

        def prepare_paid_rows():
            df = paid_invoices.copy()

            if selected_branches:
                df = df[df["client_group"].isin(selected_branches)]

            df["invoice_date_fmt"] = df["invoice_date"].apply(date_fmt)
            df["due_date_fmt"] = df["due_date"].apply(date_fmt)
            df["estimated_payment_date_fmt"] = df["estimated_payment_date"].apply(date_fmt)
            df["paid_amount_fmt"] = df["paid_amount_detected"].apply(money_precise)
            df["payment_term_days_fmt"] = df["payment_term_days"].apply(
                lambda value: "" if pd.isna(value) else str(int(value))
            )
            df["actual_payment_term_days_fmt"] = df["actual_payment_term_days"].apply(
                lambda value: "" if pd.isna(value) else str(int(value))
            )
            df["days_vs_due_date"] = df["days_vs_due_date"].fillna(0).astype(int)
            df["term_shift_count"] = df["term_shift_count"].fillna(0).astype(int)
            df["term_shift_delta_days"] = df["term_shift_delta_days"].fillna(0).astype(int)
            df["term_shift_fmt"] = df.apply(
                lambda row: (
                    f"{int(row['term_shift_count'])} / +{int(row['term_shift_delta_days'])}"
                    if int(row["term_shift_count"]) > 0
                    else "—"
                ),
                axis=1,
            )
            df["has_term_shift"] = df["term_shift_count"] > 0
            df["payment_delay_fmt"] = df["days_vs_due_date"].apply(
                lambda value: "В срок" if int(value) <= 0 else f"+{int(value)}"
            )
            df["payment_delay_level"] = df["days_vs_due_date"].apply(
                lambda value: (
                    "on_time"
                    if int(value) <= 0
                    else "small_delay"
                    if int(value) <= 3
                    else "delay"
                    if int(value) <= 14
                    else "late"
                )
            )
            df["payment_event_type_label"] = df["payment_event_type"].map({
                "FULL": "Полная",
                "PARTIAL": "Частичная",
            }).fillna(df["payment_event_type"])

            return df.to_dict("records")

        paid_table = ui.table(
            columns=[
                {"name": "client_group", "label": "Филиал", "field": "client_group", "sortable": True},
                {"name": "client_name", "label": "Наименование", "field": "client_name", "sortable": True, "align": "left"},
                {"name": "invoice_date", "label": "Дата накладной", "field": "invoice_date_fmt"},
                {"name": "print_invoice_number", "label": "Печ. номер", "field": "print_invoice_number"},
                {"name": "order_number", "label": "Номер заказа", "field": "order_number"},
                {"name": "analytics_type", "label": "Аналитика", "field": "analytics_type"},
                {"name": "payment_term_days", "label": "Отсрочка", "field": "payment_term_days_fmt", "align": "right"},
                {"name": "due_date", "label": "Оплатить до", "field": "due_date_fmt"},
                {"name": "estimated_payment_date", "label": "Расч. дата оплаты", "field": "estimated_payment_date_fmt"},
                {"name": "actual_payment_term_days", "label": "Факт, дней", "field": "actual_payment_term_days_fmt", "align": "right"},
                {"name": "payment_delay", "label": "Просрочка оплаты", "field": "payment_delay_fmt", "align": "center"},
                {"name": "term_shift_fmt", "label": "Переносы", "field": "term_shift_fmt", "align": "center"},
                {"name": "paid_amount", "label": "Оплачено", "field": "paid_amount_fmt", "align": "right"},
                {"name": "payment_event_type", "label": "Тип", "field": "payment_event_type_label", "align": "center"},
            ],
            rows=prepare_paid_rows(),
        ).classes("w-full")

        paid_table.add_slot(
            "body",
            """
            <q-tr :props="props">
                <q-td v-for="col in props.cols" :key="col.name" :props="props">

                    <template v-if="col.name === 'client_group'">
                        <q-btn
                            flat
                            dense
                            color="primary"
                            :label="props.row.client_group"
                            @click="$parent.$emit('branch_open', props.row.client_group)"
                        />
                    </template>

                    <template v-else-if="col.name === 'client_name'">
                        <q-btn
                            flat
                            dense
                            color="primary"
                            :label="props.row.client_id + ' · ' + props.row.client_name"
                            @click="$parent.$emit('client_click', props.row.client_id)"
                        />
                    </template>

                    <template v-else-if="col.name === 'payment_delay'">
                        <q-badge
                            :color="
                                props.row.payment_delay_level === 'on_time'
                                    ? 'green'
                                    : props.row.payment_delay_level === 'small_delay'
                                        ? 'orange'
                                        : props.row.payment_delay_level === 'delay'
                                            ? 'red'
                                            : 'dark'
                            "
                            :label="col.value"
                        />
                    </template>

                    <template v-else-if="col.name === 'term_shift_fmt'">
                        <q-badge
                            v-if="props.row.has_term_shift"
                            color="red"
                            :label="col.value"
                        />
                        <span v-else class="text-grey-6">—</span>
                    </template>

                    <template v-else-if="col.name === 'payment_event_type'">
                        <q-badge
                            :color="props.row.payment_event_type === 'FULL' ? 'green' : 'blue'"
                            :label="col.value"
                        />
                    </template>

                    <template v-else>
                        {{ col.value }}
                    </template>

                </q-td>
            </q-tr>
            """,
        )

    def apply_filters():
        selected_branch_label.text = (
            f"Фильтр: {', '.join(selected_branches)}"
            if selected_branches
            else "Показаны все филиалы"
        )
        selected_branch_label.update()

        clients_table.rows = prepare_client_rows()
        clients_table.update()

        invoice_table.rows = prepare_invoice_rows()
        invoice_table.update()

        if not paid_invoices.empty:
            paid_table.rows = prepare_paid_rows()
            paid_table.update()

    def reset_branch_filter():
        selected_branches.clear()
        apply_filters()

    def open_client(event):
        ui.navigate.to(
            f"/client/{event.args}?from=parent-org&parent_org_id={parent_org_id}"
        )

    def open_branch(event):
        ui.navigate.to(
            f"/branch/{quote(str(event.args))}"
        )

    clients_table.on("client_click", open_client)
    clients_table.on("branch_open", open_branch)
    invoice_table.on("client_click", open_client)
    invoice_table.on("branch_open", open_branch)

    if not paid_invoices.empty:
        paid_table.on("client_click", open_client)
        paid_table.on("branch_open", open_branch)
