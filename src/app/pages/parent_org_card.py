from pathlib import Path
import os

import pandas as pd
from dotenv import load_dotenv
from fastapi import Request
from nicegui import ui
from sqlalchemy import create_engine, text

from src.app.components.navigation import top_navigation


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


def percent(value) -> str:
    if pd.isna(value):
        return "0%"
    return f"{float(value):.1f}%"


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


@ui.page("/parent-org/{parent_org_id}")
def parent_org_card_page(parent_org_id: str, request: Request):
    source_client_id = request.query_params.get("client_id")

    back_target = (
        f"/client/{source_client_id}?from=dashboard"
        if source_client_id
        else "/"
    )

    df = query_df("""
        SELECT
            parent_org_id,
            client_id,
            client_name,
            client_group,
            invoice_date,
            due_date,
            invoice_amount,
            days_overdue_real,
            is_overdue_real,
            is_due_today,
            is_due_in_3_days
        FROM core.receivables_snapshot_fact
        WHERE parent_org_id = :parent_org_id
        ORDER BY client_group, client_name, due_date
    """, {"parent_org_id": parent_org_id})

    if df.empty:
        ui.label(f"Карточка вышестоящей: {parent_org_id}").classes("text-3xl font-bold mb-2")
        top_navigation()
        ui.label("Нет данных по этой вышестоящей организации.").classes("text-lg text-red-700")
        return

    for col in ["invoice_amount", "days_overdue_real"]:
        df[col] = df[col].astype(float)

    df["due_today_amount"] = df.apply(
        lambda row: row["invoice_amount"] if row["is_due_today"] else 0,
        axis=1,
    )

    df["due_soon_only_amount"] = df.apply(
        lambda row: row["invoice_amount"]
        if row["is_due_in_3_days"] and not row["is_due_today"]
        else 0,
        axis=1,
    )

    df["overdue_amount"] = df.apply(
        lambda row: row["invoice_amount"] if row["is_overdue_real"] else 0,
        axis=1,
    )

    selected_branches: list[str] = []

    ui.label(f"Карточка вышестоящей: {parent_org_id}").classes("text-3xl font-bold mb-2")
    top_navigation()

    with ui.row().classes("mb-4"):
        ui.button("← Назад", on_click=lambda: ui.navigate.to(back_target)).props("flat color=primary")

    def filtered_df() -> pd.DataFrame:
        result = df.copy()
        if selected_branches:
            result = result[result["client_group"].isin(selected_branches)]
        return result

    total_debt = df["invoice_amount"].sum()
    due_today = df["due_today_amount"].sum()
    due_soon = df["due_soon_only_amount"].sum()
    overdue_debt = df["overdue_amount"].sum()
    org_count = df["client_id"].nunique()
    overdue_pct = overdue_debt / total_debt * 100 if total_debt else 0

    with ui.row().classes("gap-4 mb-6"):
        kpi_card("Общий долг", money(total_debt))
        kpi_card("К оплате сегодня", money(due_today))
        kpi_card("К оплате в ближайшие дни", money(due_soon))
        kpi_card("Просрочено", money(overdue_debt), f"{percent(overdue_pct)} от общего долга")
        kpi_card("Количество организаций", str(org_count))

    # === Aging / payment timing distribution ===

    aging_df = df.copy()
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
            amount_fmt = row["amount_fmt"]
            share_fmt = row["share_fmt"]
            width = max(float(row["share"]), 1) if float(row["amount"]) > 0 else 0
            color = bucket_colors[bucket]

            with ui.row().classes("w-full items-center gap-4 mb-2"):
                ui.label(bucket).classes("w-40 text-sm")

                with ui.element("div").classes("flex-1 bg-gray-100 rounded-full h-5 overflow-hidden"):
                    ui.element("div").classes("h-5 rounded-full").style(
                        f"width: {width}%; background-color: {color};"
                    )

                ui.label(f"{amount_fmt} · {share_fmt}").classes("w-40 text-right text-sm text-gray-600")

    # === Контрагенты ===

    contractors = (
        df.groupby(["client_group", "client_id", "client_name"], as_index=False)
        .agg(
            total_debt=("invoice_amount", "sum"),
            due_today=("due_today_amount", "sum"),
            due_soon_only=("due_soon_only_amount", "sum"),
            overdue_debt=("overdue_amount", "sum"),
        )
    )

    contractors["overdue_share_pct"] = (
        contractors["overdue_debt"] / contractors["total_debt"] * 100
    ).fillna(0)

    def prepare_contractor_rows():
        result = contractors.copy()

        if selected_branches:
            result = result[result["client_group"].isin(selected_branches)]

        result["total_debt_fmt"] = result["total_debt"].apply(money)
        result["due_today_fmt"] = result["due_today"].apply(money)
        result["due_soon_only_fmt"] = result["due_soon_only"].apply(money)
        result["overdue_debt_fmt"] = result["overdue_debt"].apply(money)
        result["overdue_share_fmt"] = result["overdue_share_pct"].apply(percent)
        result["rating_placeholder"] = "—"

        return result.to_dict("records")

    with ui.row().classes("items-center gap-4"):
        selected_branch_label = ui.label("Показаны все филиалы").classes("text-sm text-gray-500")
        ui.button("ВСЕ ФИЛИАЛЫ", on_click=lambda: reset_branch_filter()).props("flat color=primary")

    ui.label("Контрагенты").classes("text-xl mt-6")

    contractor_table = ui.table(
        columns=[
            {"name": "client_group", "label": "Филиал", "field": "client_group", "sortable": True},
            {"name": "client_id", "label": "Код клиента", "field": "client_id", "sortable": True},
            {"name": "client_name", "label": "Наименование", "field": "client_name", "sortable": True},
            {"name": "total_debt", "label": "Весь долг", "field": "total_debt", "align": "right", "sortable": True},
            {"name": "due_today", "label": "К оплате сегодня", "field": "due_today", "align": "right", "sortable": True},
            {"name": "due_soon_only", "label": "К оплате в ближайшие дни", "field": "due_soon_only", "align": "right", "sortable": True},
            {"name": "overdue_debt", "label": "Просрочка", "field": "overdue_debt", "align": "right", "sortable": True},
            {"name": "overdue_share_pct", "label": "% просрочки", "field": "overdue_share_pct", "align": "right", "sortable": True},
            {"name": "rating_placeholder", "label": "Рейтинг", "field": "rating_placeholder", "align": "center"},
        ],
        rows=prepare_contractor_rows(),
    ).classes("w-full")

    contractor_table.add_slot(
        "body-cell-client_group",
        """
        <q-td :props="props">
            <q-btn
                flat
                dense
                color="primary"
                :label="props.row.client_group"
                @click="$parent.$emit('branch_click', props.row.client_group)"
            />
        </q-td>
        """,
    )

    contractor_table.add_slot(
        "body-cell-client_name",
        """
        <q-td :props="props">
            <q-btn
                flat
                dense
                color="primary"
                :label="props.row.client_name"
                @click="$parent.$emit('client_click', props.row.client_id)"
            />
        </q-td>
        """,
    )

    for column_name, fmt_name in [
        ("total_debt", "total_debt_fmt"),
        ("due_today", "due_today_fmt"),
        ("due_soon_only", "due_soon_only_fmt"),
        ("overdue_debt", "overdue_debt_fmt"),
    ]:
        contractor_table.add_slot(
            f"body-cell-{column_name}",
            f"""
            <q-td :props="props" class="text-right">
                {{{{ props.row.{fmt_name} }}}}
            </q-td>
            """,
        )

    contractor_table.add_slot(
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
        result = filtered_df().copy()

        result["invoice_amount_fmt"] = result["invoice_amount"].apply(money)
        result["is_overdue_fmt"] = result["is_overdue_real"].map({True: "Да", False: "Нет"})
        result["aging_bucket"] = result.apply(aging_bucket, axis=1)

        return result.to_dict("records")

    ui.label("Накладные").classes("text-xl mt-6")

    invoice_table = ui.table(
        columns=[
            {"name": "client_group", "label": "Филиал", "field": "client_group", "sortable": True},
            {"name": "client_name", "label": "Организация", "field": "client_name", "sortable": True},
            {"name": "client_id", "label": "Код клиента", "field": "client_id", "sortable": True},
            {"name": "invoice_date", "label": "Дата накладной", "field": "invoice_date", "sortable": True},
            {"name": "due_date", "label": "Оплатить до", "field": "due_date", "sortable": True},
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
                        :label="props.row.client_name"
                        @click="$parent.$emit('client_click', props.row.client_id)"
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

        contractor_table.rows = prepare_contractor_rows()
        contractor_table.update()

        invoice_table.rows = prepare_invoice_rows()
        invoice_table.update()

    def select_branch(event):
        selected_branches.clear()
        selected_branches.append(event.args)
        apply_filters()

    def reset_branch_filter():
        selected_branches.clear()
        apply_filters()

    def open_client(event):
        ui.navigate.to(f"/client/{event.args}?from=parent-org&parent_org_id={parent_org_id}")

    contractor_table.on("branch_click", select_branch)
    contractor_table.on("client_click", open_client)
    invoice_table.on("client_click", open_client)