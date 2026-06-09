from pathlib import Path
import os

import pandas as pd
from dotenv import load_dotenv
from nicegui import ui
from sqlalchemy import create_engine, text
from fastapi import Request

from src.app.components.rating_stars import rating_stars_html
from src.app.components.charts import (
    build_client_debt_history_chart,
    build_client_debt_structure_chart,
)
from src.app.components.kpi_cards import (
    money,
    percent,
    kpi_card,
    compact_kpi_card,
)
from src.app.components.behavioral_indicators import (
    get_debt_trend_indicator,
    get_overdue_behavior_indicator,
    get_volatility_indicator,
)
from src.app.components.rating_migration_strip import (
    render_rating_migration_strip,
)
from urllib.parse import quote

PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env")

engine = create_engine(
    f"postgresql+psycopg2://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@"
    f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)


def query_df(sql: str, params: dict = None) -> pd.DataFrame:
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn, params=params)


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


def date_fmt(value) -> str:
    if pd.isna(value):
        return ""
    return pd.to_datetime(value).strftime("%d.%m.%Y")


def money_precise(value) -> str:
    if pd.isna(value):
        return "0,00"
    return f"{float(value):,.2f}".replace(",", " ").replace(".", ",")


@ui.page("/client/{client_id}")
def client_card_page(client_id: str, request: Request):

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
    }

    if origin == "parent-org" and parent_org_back_id:
        back_target = f"/parent-org/{parent_org_back_id}"
    elif origin == "branch" and branch_back_name:
        back_target = f"/branch/{quote(branch_back_name)}"
    else:
        back_target = back_routes.get(origin, "/")

    df = query_df("""
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
    """, {"client_id": client_id})

    if df.empty:
        ui.label(f"Карточка клиента: {client_id}").classes("text-3xl font-bold mb-4")
        ui.label("Нет данных по клиенту")
        return

    # === Paid / closed invoice events ===

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

        WHERE p.client_id = :client_id

        ORDER BY
            p.estimated_payment_date DESC,
            p.paid_amount_detected DESC

        LIMIT 20
    """, {"client_id": client_id})

    # === Payment term baseline by analytics ===

    payment_terms = df[
        df["payment_term_days"].notna()
    ][["analytics_type", "payment_term_days"]].copy()

    payment_terms["analytics_type"] = payment_terms["analytics_type"].fillna("—")
    payment_terms["payment_term_days"] = payment_terms["payment_term_days"].astype(int)

    if not payment_terms.empty:
        baseline_payment_term = int(payment_terms["payment_term_days"].mode().iloc[0])

        baseline_by_analytics = (
            payment_terms
            .groupby("analytics_type")["payment_term_days"]
            .agg(lambda s: int(s.mode().iloc[0]))
            .to_dict()
        )
    else:
        baseline_payment_term = None
        baseline_by_analytics = {}

    def get_baseline_payment_term(row) -> int | None:
        analytics_type = row.get("analytics_type")

        if pd.isna(analytics_type):
            analytics_type = "—"

        return baseline_by_analytics.get(
            str(analytics_type),
            baseline_payment_term,
        )

    # === Historical data ===

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
        FROM core.v_client_daily_history
        WHERE client_id = :client_id
        ORDER BY report_generated_date
    """, {"client_id": client_id})

    rating_migration = query_df("""
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
    """, {"client_id": client_id})

    client_name = df["client_name"].iloc[0]
    client_group = df["client_group"].iloc[0]
    parent_org_id = df["parent_org_id"].iloc[0]

    ui.label(f"Карточка клиента: {client_name}").classes("text-3xl font-bold mb-1")

    with ui.row().classes("items-center gap-1 text-sm text-gray-500 mb-4"):
        ui.label(f"Клиент ID: {client_id} · Вышестоящая организация:")

        ui.button(
            str(parent_org_id),
            on_click=lambda: ui.navigate.to(
                f"/parent-org/{parent_org_id}?from=client&client_id={client_id}"
            )
        ).props("flat dense color=primary").classes("p-0 min-h-0")

        ui.label(f"· Филиал: {client_group}")

    with ui.row().classes("mb-4"):
        ui.button(
            "← Назад",
            on_click=lambda: ui.navigate.to(back_target)
        ).props("flat color=primary")

    total_debt = df["invoice_amount"].sum()

    overdue_debt = df[df["is_overdue_real"]]["invoice_amount"].sum()

    overdue_pct = (
        overdue_debt / total_debt * 100
        if total_debt else 0
    )

    max_days = int(df["days_overdue_real"].max())

    # === Rating ===

    stars_raw = df["stars"].iloc[0]

    if pd.notna(stars_raw):
        stars = int(stars_raw)
        rating_text = rating_stars_html(stars)
    else:
        rating_text = "—"

    rating_label = (
        df["rating_display_label"].iloc[0]
        if pd.notna(df["rating_display_label"].iloc[0])
        else "Нет рейтинга"
    )

    confidence_level = (
        df["confidence_level"].iloc[0]
        if pd.notna(df["confidence_level"].iloc[0])
        else ""
    )

    rating_subtitle = f"{rating_label} · {confidence_level}"

    with ui.row().classes("gap-4 mb-6"):
        kpi_card("Общий долг", money(total_debt))
        kpi_card("Просрочено", money(overdue_debt))
        kpi_card("% просрочки", percent(overdue_pct))
        kpi_card("Макс. дней", str(max_days))
        kpi_card("Рейтинг", rating_text, rating_subtitle)

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

    if not history_df.empty:

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

            debt_trend = get_debt_trend_indicator(history_filtered)

            overdue_behavior = get_overdue_behavior_indicator(
                history_filtered
            )
            volatility = get_volatility_indicator(history_filtered)

            charts_container.clear()

            with charts_container:

                rating_migration_selected = get_rating_migration_for_selected_period()

                if not rating_migration_selected.empty:
                    render_rating_migration_strip(
                        rating_migration_selected.iloc[0]
                    )

                ui.label("Интерпретация периода").classes(
                    "text-sm text-gray-500 mb-3"
                )

                with ui.row().classes("gap-3 mb-4"):
                    with ui.card().classes("px-4 py-2"):
                        with ui.row().classes("items-center gap-2"):
                            ui.label(debt_trend["icon"]).classes("text-lg")
                            ui.label(debt_trend["label"]).classes(
                                f"text-sm font-medium text-{debt_trend['color']}-600"
                            )
                            ui.label(debt_trend.get("detail", "")).classes(
                                "text-xs text-gray-500"
                            )
                    with ui.card().classes("px-4 py-2"):
                        with ui.row().classes("items-center gap-2"):
                            ui.label(overdue_behavior["icon"]).classes("text-lg")

                            ui.label(
                                overdue_behavior["label"]
                            ).classes(
                                f"text-sm font-medium text-{overdue_behavior['color']}-600"
                            )

                            ui.label(
                                overdue_behavior.get("detail", "")
                            ).classes(
                                "text-xs text-gray-500"
                            )
                    with ui.card().classes("px-4 py-2"):
                        with ui.row().classes("items-center gap-2"):
                            ui.label(volatility["icon"]).classes("text-lg")

                            ui.label(
                                volatility["label"]
                            ).classes(
                                f"text-sm font-medium text-{volatility['color']}-600"
                            )

                            ui.label(
                                volatility.get("detail", "")
                            ).classes(
                                "text-xs text-gray-500"
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
                    compact_kpi_card(
                        "Макс. дней",
                        str(history_kpi["max_days_overdue"]),
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

    # === Active invoices table ===

    filter_toggle = ui.toggle(
        options=["Все", "Только просроченные"],
        value="Все"
    ).classes("mb-4")

    def prepare_rows():

        dff = df.copy()

        if filter_toggle.value == "Только просроченные":
            dff = dff[dff["is_overdue_real"] == True]

        dff["invoice_date_fmt"] = dff["invoice_date"].apply(date_fmt)
        dff["due_date_fmt"] = dff["due_date"].apply(date_fmt)
        dff["invoice_amount_fmt"] = dff["invoice_amount"].apply(money_precise)

        dff["payment_term_days_fmt"] = dff["payment_term_days"].apply(
            lambda value: "" if pd.isna(value) else str(int(value))
        )

        dff["payment_term_baseline_days"] = dff.apply(
            get_baseline_payment_term,
            axis=1,
        )

        dff["is_long_payment_term"] = dff["payment_term_days"].apply(
            lambda value: False if pd.isna(value) else int(value) >= 45
        )

        dff["is_above_baseline_payment_term"] = dff.apply(
            lambda row: (
                False
                if pd.isna(row["payment_term_days"])
                or row["payment_term_baseline_days"] is None
                else int(row["payment_term_days"]) >= int(row["payment_term_baseline_days"]) + 2
            ),
            axis=1,
        )

        dff["payment_term_alert_level"] = dff.apply(
            lambda row: (
                "critical"
                if row["is_long_payment_term"]
                else "warning"
                if row["is_above_baseline_payment_term"]
                else "normal"
            ),
            axis=1,
        )

        dff["term_shift_count"] = dff["term_shift_count"].fillna(0).astype(int)
        dff["term_shift_delta_days"] = dff["term_shift_delta_days"].fillna(0).astype(int)

        dff["term_shift_fmt"] = dff.apply(
            lambda row: (
                f"{int(row['term_shift_count'])} / +{int(row['term_shift_delta_days'])}"
                if int(row["term_shift_count"]) > 0
                else "—"
            ),
            axis=1,
        )

        dff["has_term_shift"] = dff["term_shift_count"] > 0

        dff["is_overdue_fmt"] = dff["is_overdue_real"].map({
            True: "Да",
            False: "Нет"
        })

        dff["aging_bucket"] = dff.apply(
            aging_bucket,
            axis=1
        )

        return dff.to_dict("records")

    table = ui.table(
        columns=[
            {"name": "invoice_date", "label": "Дата накладной", "field": "invoice_date_fmt"},
            {"name": "order_number", "label": "Номер заказа", "field": "order_number"},
            {"name": "print_invoice_number", "label": "Печ. номер накладной", "field": "print_invoice_number"},
            {"name": "analytics_type", "label": "Аналитика", "field": "analytics_type"},
            {"name": "due_date", "label": "Оплатить до", "field": "due_date_fmt"},
            {"name": "payment_term_days", "label": "Отсрочка, дней", "field": "payment_term_days_fmt", "align": "right"},
            {"name": "term_shift_fmt", "label": "Переносы", "field": "term_shift_fmt", "align": "center"},
            {"name": "invoice_amount_fmt", "label": "Сумма", "field": "invoice_amount_fmt", "align": "right"},
            {"name": "days_overdue_real", "label": "Просрочка (дни)", "field": "days_overdue_real", "align": "right"},
            {"name": "aging_bucket", "label": "Срок просрочки", "field": "aging_bucket", "align": "center"},
            {"name": "is_overdue_fmt", "label": "Просрочено", "field": "is_overdue_fmt", "align": "center"},
        ],
        rows=prepare_rows(),
    ).classes("w-full mb-6")

    table.add_slot(
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
                <template v-if="col.name === 'payment_term_days'">
                    <q-badge
                        :color="
                            props.row.payment_term_alert_level === 'critical'
                                ? 'red'
                                : props.row.payment_term_alert_level === 'warning'
                                    ? 'orange'
                                    : 'grey'
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

                <template v-else>
                    {{ col.value }}
                </template>
            </q-td>
        </q-tr>
        """
    )

    def refresh():
        table.rows = prepare_rows()
        table.update()

    filter_toggle.on_value_change(lambda _: refresh())

    # === Recently paid invoices table ===

    if not paid_invoices.empty:

        ui.label("Последние оплаченные накладные").classes("text-xl font-bold mt-6 mb-1")
        ui.label(
            "Расчетная дата оплаты восстановлена по исчезновению накладной из открытой дебиторки "
            "или по снижению открытого остатка между срезами."
        ).classes("text-sm text-gray-500 mb-3")

        def prepare_paid_rows():

            dff = paid_invoices.copy()

            dff["invoice_date_fmt"] = dff["invoice_date"].apply(date_fmt)
            dff["due_date_fmt"] = dff["due_date"].apply(date_fmt)
            dff["estimated_payment_date_fmt"] = dff["estimated_payment_date"].apply(date_fmt)

            dff["paid_amount_fmt"] = dff["paid_amount_detected"].apply(money_precise)
            dff["amount_before_payment_fmt"] = dff["amount_before_payment"].apply(money_precise)
            dff["amount_after_payment_fmt"] = dff["amount_after_payment"].apply(money_precise)

            dff["payment_term_days_fmt"] = dff["payment_term_days"].apply(
                lambda value: "" if pd.isna(value) else str(int(value))
            )

            dff["actual_payment_term_days_fmt"] = dff["actual_payment_term_days"].apply(
                lambda value: "" if pd.isna(value) else str(int(value))
            )

            dff["days_vs_due_date"] = dff["days_vs_due_date"].fillna(0).astype(int)
            dff["term_shift_count"] = dff["term_shift_count"].fillna(0).astype(int)
            dff["term_shift_delta_days"] = dff["term_shift_delta_days"].fillna(0).astype(int)

            dff["term_shift_fmt"] = dff.apply(
                lambda row: (
                    f"{int(row['term_shift_count'])} / +{int(row['term_shift_delta_days'])}"
                    if int(row["term_shift_count"]) > 0
                    else "—"
                ),
                axis=1,
            )

            dff["has_term_shift"] = dff["term_shift_count"] > 0

            dff["payment_delay_fmt"] = dff["days_vs_due_date"].apply(
                lambda value: (
                    "В срок"
                    if int(value) <= 0
                    else f"+{int(value)}"
                )
            )

            dff["payment_delay_level"] = dff["days_vs_due_date"].apply(
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

            dff["payment_event_type_label"] = dff["payment_event_type"].map({
                "FULL": "Полная",
                "PARTIAL": "Частичная",
            }).fillna(dff["payment_event_type"])

            return dff.to_dict("records")

        paid_table = ui.table(
            columns=[
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

                    <template v-if="col.name === 'payment_delay'">
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
            """
        )