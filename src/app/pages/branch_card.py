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
    build_credit_quality_exposure_chart,
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


def compact_quality_kpi(title: str, value: str, subtitle: str = ""):
    with ui.card().classes("w-48 h-28 p-3"):
        with ui.column().classes("w-full h-full items-center justify-between text-center"):
            ui.label(title).classes("text-sm text-gray-500 h-5 flex items-center justify-center")
            ui.label(value).classes("text-xl font-bold h-8 flex items-center justify-center")
            ui.label(subtitle).classes("text-xs text-gray-500 h-6 flex items-center justify-center")


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
            ui.label(indicator["label"]).classes(f"text-sm font-medium {label_class}")
            ui.label(indicator.get("detail", "")).classes("text-xs text-gray-500")


@ui.page("/branch/{branch_name}")
def branch_card_page(branch_name: str, request: Request):
    origin = request.query_params.get("from", "/")
    back_target = origin if origin.startswith("/") else "/"

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

        WHERE i.client_group = :branch_name
        ORDER BY i.client_name, i.due_date
    """, {"branch_name": branch_name})

    ui.label(f"Карточка филиала: {branch_name}").classes("text-3xl font-bold mb-2")
    top_navigation()

    if invoices.empty:
        ui.label("Нет данных по этому филиалу.").classes("text-lg text-red-700")
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

        WHERE p.client_group = :branch_name

        ORDER BY
            p.estimated_payment_date DESC,
            p.paid_amount_detected DESC

        LIMIT 30
    """, {"branch_name": branch_name})

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
        FROM core.v_branch_daily_history
        WHERE client_group = :branch_name
        ORDER BY report_generated_date
    """, {"branch_name": branch_name})

    branch_rating_df = query_df("""
        SELECT *
        FROM core.v_branch_rating_dynamics
        WHERE client_group = :branch_name
    """, {"branch_name": branch_name})

    credit_quality_exposure = query_df("""
        SELECT
            credit_quality_stars,
            COUNT(*) AS client_count,
            SUM(total_debt) AS total_debt,
            SUM(overdue_debt) AS overdue_debt
        FROM core.v_client_credit_quality_rating
        WHERE client_group = :branch_name
        GROUP BY credit_quality_stars
        ORDER BY credit_quality_stars NULLS LAST
    """, {"branch_name": branch_name})

    with ui.row().classes("mb-4"):
        ui.button("← Назад", on_click=lambda: ui.navigate.to(back_target)).props("flat color=primary")

    total_debt = invoices["invoice_amount"].sum()
    due_today = invoices["due_today_amount"].sum()
    due_soon_only = invoices["due_soon_only_amount"].sum()
    overdue_debt = invoices["overdue_amount"].sum()
    overdue_share_pct = overdue_debt / total_debt * 100 if total_debt else 0
    client_count = invoices["client_id"].nunique()

    if not branch_rating_df.empty:
        branch_rating = branch_rating_df.iloc[0]
        green_90_plus_debt = float(branch_rating.get("green_90_plus_debt", 0) or 0)
        green_120_plus_debt = float(branch_rating.get("green_120_plus_debt", 0) or 0)
        green_90_plus_share = float(branch_rating.get("green_90_plus_share_pct", 0) or 0)
        green_120_plus_share = float(branch_rating.get("green_120_plus_share_pct", 0) or 0)
    else:
        green_90_plus_debt = 0
        green_120_plus_debt = 0
        green_90_plus_share = 0
        green_120_plus_share = 0

    with ui.row().classes("gap-4 mb-6"):
        kpi_card("Общий долг", money(total_debt))
        kpi_card("К оплате сегодня", money(due_today))
        kpi_card("К оплате в ближайшие дни", money(due_soon_only))
        kpi_card("Просрочено", money(overdue_debt), f"{percent(overdue_share_pct)} от общего долга")
        kpi_card("90+ непросрочено", money(green_90_plus_debt), f"{percent(green_90_plus_share)} от портфеля филиала")
        kpi_card("120+ непросрочено", money(green_120_plus_debt), f"{percent(green_120_plus_share)} от портфеля филиала")
        kpi_card("Клиентов", str(int(client_count)))

    if not branch_rating_df.empty:
        render_portfolio_rating_strip(branch_rating_df.iloc[0])

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
                ui.label("Интерпретация периода").classes("text-sm text-gray-500 mb-3")

                with ui.row().classes("gap-3 mb-4"):
                    indicator_card(debt_trend)
                    indicator_card(overdue_behavior)
                    indicator_card(volatility)

                with ui.card().classes("w-full p-4 mb-6"):
                    ui.label("История задолженности").classes("text-sm text-gray-500 mb-3")
                    history_chart = build_client_debt_history_chart(history_filtered)
                    ui.plotly(history_chart).classes("w-full")

                with ui.card().classes("w-full p-4 mb-6"):
                    ui.label("Структура задолженности по дням").classes("text-sm text-gray-500 mb-3")
                    structure_chart = build_client_debt_structure_chart(history_filtered)
                    ui.plotly(structure_chart).classes("w-full")

        selected_period.on_value_change(lambda _: render_history_charts())
        render_history_charts()

    # === Качество клиентов ===

    if not credit_quality_exposure.empty:
        quality_df = credit_quality_exposure.copy()
        quality_df["credit_quality_stars"] = quality_df["credit_quality_stars"].fillna(0).astype(int)

        def quality_count(stars: list[int]) -> int:
            return int(
                quality_df[
                    quality_df["credit_quality_stars"].isin(stars)
                ]["client_count"].sum()
            )

        def quality_debt(stars: list[int]) -> float:
            return float(
                quality_df[
                    quality_df["credit_quality_stars"].isin(stars)
                ]["total_debt"].sum()
            )

        with ui.card().classes("w-full p-4 mb-6"):
            ui.label("Качество клиентов").classes("text-xl font-bold mb-1")
            ui.label(
                "Распределение задолженности по Credit Quality Rating "
                "с учетом просрочки, длинных отсрочек и переносов сроков."
            ).classes("text-sm text-gray-500 mb-3")

            with ui.row().classes("gap-3 mb-4"):
                compact_quality_kpi(
                    "5★",
                    str(quality_count([5])),
                    f"{money(quality_debt([5]))} руб",
                )
                compact_quality_kpi(
                    "4★",
                    str(quality_count([4])),
                    f"{money(quality_debt([4]))} руб",
                )
                compact_quality_kpi(
                    "3★",
                    str(quality_count([3])),
                    f"{money(quality_debt([3]))} руб",
                )
                compact_quality_kpi(
                    "1–2★",
                    str(quality_count([1, 2])),
                    f"{money(quality_debt([1, 2]))} руб",
                )

            ui.plotly(
                build_credit_quality_exposure_chart(
                    credit_quality_exposure
                )
            ).classes("w-full")

    # === Контрагенты ===

    clients = (
        invoices
        .groupby(["client_id", "client_name", "parent_org_id", "stars"], as_index=False)
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

    def prepare_client_rows():
        df = clients.copy()
        df["total_debt_fmt"] = df["total_debt"].apply(money)
        df["due_today_fmt"] = df["due_today"].apply(money)
        df["due_soon_only_fmt"] = df["due_soon_only"].apply(money)
        df["overdue_debt_fmt"] = df["overdue_debt"].apply(money)
        df["overdue_share_fmt"] = df["overdue_share_pct"].apply(percent)
        df["rating_html"] = df["stars"].apply(
            lambda value: rating_stars_html(int(value)) if pd.notna(value) else "—"
        )
        return df.to_dict("records")

    ui.label("Контрагенты").classes("text-xl mt-6")

    clients_table = ui.table(
        columns=[
            {"name": "client_name", "label": "Наименование", "field": "client_name", "sortable": True, "align": "left"},
            {"name": "parent_org_id", "label": "Вышестоящая", "field": "parent_org_id", "sortable": True},
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
        "body-cell-client_name",
        """
        <q-td :props="props" class="text-left">
            <q-btn flat dense color="primary"
                   :label="props.row.client_id + ' · ' + props.row.client_name"
                   @click="$parent.$emit('client_click', props.row.client_id)" />
        </q-td>
        """,
    )

    clients_table.add_slot(
        "body-cell-parent_org_id",
        """
        <q-td :props="props">
            <q-btn flat dense color="primary"
                   :label="props.row.parent_org_id"
                   @click="$parent.$emit('parent_org_click', props.row.parent_org_id)" />
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

    # === Накладные в работе ===

    def prepare_invoice_rows():
        df = invoices.copy()
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

    ui.label("Накладные в работе").classes("text-xl mt-6")

    invoice_table = ui.table(
        columns=[
            {"name": "client_name", "label": "Наименование", "field": "client_name", "sortable": True, "align": "left"},
            {"name": "parent_org_id", "label": "Вышестоящая", "field": "parent_org_id", "sortable": True},
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

                <template v-if="col.name === 'client_name'">
                    <q-btn
                        flat
                        dense
                        color="primary"
                        :label="props.row.client_id + ' · ' + props.row.client_name"
                        @click="$parent.$emit('client_click', props.row.client_id)"
                    />
                </template>

                <template v-else-if="col.name === 'parent_org_id'">
                    <q-btn
                        flat
                        dense
                        color="primary"
                        :label="props.row.parent_org_id"
                        @click="$parent.$emit('parent_org_click', props.row.parent_org_id)"
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

    # === Последние оплаченные накладные ===

    if not paid_invoices.empty:
        ui.label("Последние оплаченные накладные").classes("text-xl font-bold mt-6 mb-1")
        ui.label(
            "Расчетная дата оплаты восстановлена по исчезновению накладной из открытой дебиторки "
            "или по снижению открытого остатка между срезами."
        ).classes("text-sm text-gray-500 mb-3")

        def prepare_paid_rows():
            df = paid_invoices.copy()
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
                {"name": "client_name", "label": "Наименование", "field": "client_name", "sortable": True, "align": "left"},
                {"name": "parent_org_id", "label": "Вышестоящая", "field": "parent_org_id", "sortable": True},
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

                    <template v-if="col.name === 'client_name'">
                        <q-btn
                            flat
                            dense
                            color="primary"
                            :label="props.row.client_id + ' · ' + props.row.client_name"
                            @click="$parent.$emit('client_click', props.row.client_id)"
                        />
                    </template>

                    <template v-else-if="col.name === 'parent_org_id'">
                        <q-btn
                            flat
                            dense
                            color="primary"
                            :label="props.row.parent_org_id"
                            @click="$parent.$emit('parent_org_click', props.row.parent_org_id)"
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

    def open_client(event):
        ui.navigate.to(
            f"/client/{event.args}?from=branch&branch_name={quote(branch_name)}"
        )

    def open_parent_org(event):
        ui.navigate.to(
            f"/parent-org/{event.args}?from=branch&branch_name={quote(branch_name)}"
        )

    clients_table.on("client_click", open_client)
    clients_table.on("parent_org_click", open_parent_org)
    invoice_table.on("client_click", open_client)
    invoice_table.on("parent_org_click", open_parent_org)

    if not paid_invoices.empty:
        paid_table.on("client_click", open_client)
        paid_table.on("parent_org_click", open_parent_org)
