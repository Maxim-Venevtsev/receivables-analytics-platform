from pathlib import Path
import os

import pandas as pd
from dotenv import load_dotenv
from nicegui import ui
from sqlalchemy import create_engine, text
from fastapi import Request


PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env")

engine = create_engine(
    f"postgresql+psycopg2://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@"
    f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)


def query_df(sql: str, params: dict = None) -> pd.DataFrame:
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn, params=params)


def money(value):
    return f"{float(value):,.0f}".replace(",", " ")


def percent(value):
    return f"{value:.1f}%"


def kpi_card(title: str, value: str, subtitle: str | None = None):
    with ui.card().classes("w-64 h-36 p-4"):
        with ui.column().classes("w-full h-full items-center justify-between text-center"):
            ui.label(title).classes("text-sm text-gray-500")
            ui.html(value).classes("text-2xl font-bold")
            ui.label(subtitle or "").classes("text-sm text-gray-500")


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


@ui.page("/client/{client_id}")
def client_card_page(client_id: str, request: Request):

    origin = request.query_params.get("from", "dashboard")

    back_routes = {
        "dashboard": "/",
        "deltas": "/deltas",
        "overdue": "/overdue",
        "due-today": "/due-today",
        "due-soon": "/due-soon",
    }

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
            i.invoice_amount,
            i.days_overdue_real,
            i.is_overdue_real,
            i.is_due_today,
            i.is_due_in_3_days,

            r.stars,
            r.rating_display_label,
            r.confidence_level

        FROM core.v_invoice_detail i

        LEFT JOIN core.v_client_rating r
            ON i.client_id = r.client_id

        WHERE i.client_id = :client_id

        ORDER BY i.invoice_date DESC
    """, {"client_id": client_id})

    if df.empty:
        ui.label(f"Карточка клиента: {client_id}").classes("text-3xl font-bold mb-4")
        ui.label("Нет данных по клиенту")
        return

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

        star_colors = {
            5: "#fbbf24",  # gold
            4: "#f59e0b",  # warm yellow
            3: "#eab308",  # neutral yellow
            2: "#f97316",  # orange
            1: "#ea580c",  # red-orange
        }

        active_color = star_colors.get(stars, "#9ca3af")
        inactive_color = "#d1d5db"

        colored_stars = ""

        for i in range(1, 6):

            if i <= stars:
                colored_stars += (
                    f'<span style="color:{active_color};">★</span>'
                )
            else:
                colored_stars += (
                    f'<span style="color:{inactive_color};">☆</span>'
                )

        rating_text = colored_stars

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

    # === Table ===

    filter_toggle = ui.toggle(
        options=["Все", "Только просроченные"],
        value="Все"
    ).classes("mb-4")

    def prepare_rows():

        dff = df.copy()

        if filter_toggle.value == "Только просроченные":
            dff = dff[dff["is_overdue_real"] == True]

        dff["invoice_amount_fmt"] = dff["invoice_amount"].apply(money)

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
            {"name": "invoice_date", "label": "Дата накладной", "field": "invoice_date"},
            {"name": "order_number", "label": "Номер заказа", "field": "order_number"},
            {"name": "print_invoice_number", "label": "Печ. номер накладной", "field": "print_invoice_number"},
            {"name": "analytics_type", "label": "Аналитика", "field": "analytics_type"},
            {"name": "due_date", "label": "Оплатить до", "field": "due_date"},
            {"name": "invoice_amount_fmt", "label": "Сумма", "field": "invoice_amount_fmt", "align": "right"},
            {"name": "days_overdue_real", "label": "Просрочка (дни)", "field": "days_overdue_real", "align": "right"},
            {"name": "aging_bucket", "label": "Срок просрочки", "field": "aging_bucket", "align": "center"},
            {"name": "is_overdue_fmt", "label": "Просрочено", "field": "is_overdue_fmt", "align": "center"},
        ],
        rows=prepare_rows(),
    ).classes("w-full")

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
                {{ col.value }}
            </q-td>
        </q-tr>
        """
    )

    def refresh():
        table.rows = prepare_rows()
        table.update()

    filter_toggle.on_value_change(lambda _: refresh())