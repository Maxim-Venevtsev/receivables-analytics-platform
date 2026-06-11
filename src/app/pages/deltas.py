from pathlib import Path
import os
from urllib.parse import quote

import pandas as pd
from dotenv import load_dotenv
from nicegui import ui
from sqlalchemy import create_engine, text

from src.app.components.navigation import top_navigation
from src.app.components.kpi_cards import money
from src.app.components.rating_stars import rating_stars_html


PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env")

engine = create_engine(
    f"postgresql+psycopg2://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@"
    f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)


def query_df(sql: str, params: dict | None = None) -> pd.DataFrame:
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn, params=params)


def date_fmt(value) -> str:
    if pd.isna(value):
        return ""
    return pd.to_datetime(value).strftime("%d.%m.%Y")


def money_precise(value) -> str:
    if pd.isna(value):
        return "0,00"
    return f"{float(value):,.2f}".replace(",", " ").replace(".", ",")


def compact_kpi(title: str, value: str, subtitle: str = "", color_class: str = "text-gray-900"):
    with ui.card().classes("w-60 h-32 p-4"):
        with ui.column().classes("w-full h-full items-center justify-between text-center"):
            ui.label(title).classes("text-sm text-gray-500 h-6 flex items-center justify-center")
            ui.label(value).classes(f"text-2xl font-bold h-10 flex items-center justify-center {color_class}")
            ui.label(subtitle).classes("text-sm text-gray-500 h-8 flex items-center justify-center")


def prepare_money_cols(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    result = df.copy()
    for col in cols:
        if col in result.columns:
            result[f"{col}_fmt"] = result[col].apply(money_precise)
    return result


def table_page_props() -> str:
    return 'rows-per-page-options="[20, 50, 100]"'


def render_table(title: str, subtitle: str, df: pd.DataFrame, columns: list[dict], empty_text: str):
    ui.label(title).classes("text-xl font-bold mt-6 mb-1")
    ui.label(subtitle).classes("text-sm text-gray-500 mb-3")

    if df.empty:
        ui.label(empty_text).classes("text-sm text-gray-500 mb-6")
        return None

    table = ui.table(
        columns=columns,
        rows=df.to_dict("records"),
        pagination={"rowsPerPage": 20},
    ).classes("w-full mb-6")
    table.props(table_page_props())
    return table


def add_client_summary_slot(table):
    table.add_slot(
        "body",
        """
        <q-tr :props="props">
            <q-td v-for="col in props.cols" :key="col.name" :props="props">
                <template v-if="col.name === 'client'">
                    <a :href="props.row.client_url" class="text-blue-600 hover:underline font-medium">
                        {{ props.row.client_display }}
                    </a>
                </template>

                <template v-else-if="col.name === 'rating'">
                    <span v-html="props.row.rating_html"></span>
                </template>

                <template v-else>
                    {{ col.value }}
                </template>
            </q-td>
        </q-tr>
        """,
    )



def add_event_table_slots(table):
    table.add_slot(
        "body",
        """
        <q-tr :props="props">
            <q-td v-for="col in props.cols" :key="col.name" :props="props">
                <template v-if="col.name === 'client'">
                    <a :href="props.row.client_url" class="text-blue-600 hover:underline font-medium">
                        {{ props.row.client_display }}
                    </a>
                </template>

                <template v-else-if="col.name === 'rating'">
                    <span v-html="props.row.rating_html"></span>
                </template>

                <template v-else>
                    {{ col.value }}
                </template>
            </q-td>
        </q-tr>
        """,
    )


def add_branch_summary_slots(table):
    table.add_slot(
        "body-cell-client_group",
        """
        <q-td :props="props" :style="props.row.is_dimmed ? 'opacity:0.45;' : ''">
            <q-btn
                dense
                :flat="!props.row.is_selected"
                :unelevated="props.row.is_selected"
                :outline="!props.row.is_selected"
                :color="props.row.is_selected ? 'primary' : 'grey-7'"
                :label="props.row.client_group"
                @click="$parent.$emit('branch_click', props.row.client_group)"
            />
        </q-td>
        """,
    )

    table.add_slot(
        "body-cell-rating",
        """
        <q-td :props="props" class="text-center" :style="props.row.is_dimmed ? 'opacity:0.45;' : ''">
            {{ props.row.weighted_rating_fmt }}
        </q-td>
        """,
    )

    for col in [
        "new_debt",
        "paid_debt",
        "net_delta",
        "shifted_debt",
        "new_overdue_debt",
    ]:
        table.add_slot(
            f"body-cell-{col}",
            f"""
            <q-td :props="props" class="text-right" :style="props.row.is_dimmed ? 'opacity:0.45;' : ''">
                {{{{ props.row.{col}_fmt }}}}
            </q-td>
            """,
        )


@ui.page("/deltas")
def deltas_page():
    ui.label("Операционные изменения за день").classes("text-3xl font-bold mb-2")
    ui.label(
        "Что изменилось между последним снэпшотом и выбранным предыдущим снэпшотом."
    ).classes("text-gray-500 mb-4")

    top_navigation()

    selected_offset = ui.select(
        {
            1: "Последний снэпшот vs предыдущий",
            2: "Последний снэпшот vs 2 снэпшота назад",
            3: "Последний снэпшот vs 3 снэпшота назад",
        },
        value=1,
        label="Период сравнения",
    ).classes("w-80 mb-6")

    container = ui.column().classes("w-full")
    selected_branches: list[str] = []

    def render():
        container.clear()
        selected_branches.clear()
        offset = int(selected_offset.value)

        snapshot_info = query_df("""
            WITH snapshot_dates AS (
                SELECT
                    report_generated_date,
                    ROW_NUMBER() OVER (ORDER BY report_generated_date DESC) AS rn
                FROM (
                    SELECT DISTINCT report_generated_date
                    FROM core.receivables_snapshot_fact
                ) d
            )
            SELECT
                MAX(report_generated_date) FILTER (WHERE rn = 1) AS latest_snapshot_date,
                MAX(report_generated_date) FILTER (WHERE rn = :base_rn) AS base_snapshot_date
            FROM snapshot_dates
        """, {"base_rn": offset + 1})

        if snapshot_info.empty or pd.isna(snapshot_info.iloc[0]["base_snapshot_date"]):
            with container:
                ui.label("Недостаточно снэпшотов для сравнения.").classes("text-red-700")
            return

        latest_snapshot_date = snapshot_info.iloc[0]["latest_snapshot_date"]
        base_snapshot_date = snapshot_info.iloc[0]["base_snapshot_date"]

        params = {
            "latest_snapshot_date": latest_snapshot_date,
            "base_snapshot_date": base_snapshot_date,
        }

        kpi = query_df("""
            WITH base_snapshot AS (
                SELECT *
                FROM core.receivables_snapshot_fact
                WHERE report_generated_date = :base_snapshot_date
            ),
            latest_snapshot AS (
                SELECT *
                FROM core.receivables_snapshot_fact
                WHERE report_generated_date = :latest_snapshot_date
            ),
            b AS (
                SELECT
                    *,
                    CONCAT_WS('|', client_id, COALESCE(print_invoice_number, ''), COALESCE(order_number, ''), invoice_date::text) AS invoice_key
                FROM base_snapshot
            ),
            l AS (
                SELECT
                    *,
                    CONCAT_WS('|', client_id, COALESCE(print_invoice_number, ''), COALESCE(order_number, ''), invoice_date::text) AS invoice_key
                FROM latest_snapshot
            ),
            new_invoices AS (
                SELECT l.*
                FROM l
                LEFT JOIN b ON l.invoice_key = b.invoice_key
                WHERE b.invoice_key IS NULL
            ),
            paid_invoices AS (
                SELECT b.*
                FROM b
                LEFT JOIN l ON b.invoice_key = l.invoice_key
                WHERE l.invoice_key IS NULL
            ),
            term_shift_events AS (
                SELECT l.*
                FROM l
                JOIN b ON l.invoice_key = b.invoice_key
                WHERE COALESCE(l.due_date::text, '') <> COALESCE(b.due_date::text, '')
            ),
            new_overdue_events AS (
                SELECT l.*
                FROM l
                LEFT JOIN b ON l.invoice_key = b.invoice_key
                WHERE l.is_overdue_real = TRUE
                  AND COALESCE(b.is_overdue_real, FALSE) = FALSE
            )
            SELECT
                (SELECT COALESCE(SUM(invoice_amount), 0) FROM new_invoices) AS new_debt,
                (SELECT COALESCE(SUM(invoice_amount), 0) FROM paid_invoices) AS paid_debt,
                (
                    (SELECT COALESCE(SUM(invoice_amount), 0) FROM new_invoices)
                    -
                    (SELECT COALESCE(SUM(invoice_amount), 0) FROM paid_invoices)
                ) AS net_delta,
                (SELECT COUNT(*) FROM new_invoices) AS new_invoice_count,
                (SELECT COUNT(*) FROM paid_invoices) AS paid_invoice_count,
                (SELECT COALESCE(SUM(invoice_amount), 0) FROM term_shift_events) AS shifted_debt,
                (SELECT COUNT(*) FROM term_shift_events) AS shifted_invoice_count,
                (SELECT COALESCE(SUM(invoice_amount), 0) FROM new_overdue_events) AS new_overdue_debt,
                (SELECT COUNT(*) FROM new_overdue_events) AS new_overdue_invoice_count
        """, params)

        summary = query_df("""
            WITH base_snapshot AS (
                SELECT *
                FROM core.receivables_snapshot_fact
                WHERE report_generated_date = :base_snapshot_date
            ),
            latest_snapshot AS (
                SELECT *
                FROM core.receivables_snapshot_fact
                WHERE report_generated_date = :latest_snapshot_date
            ),
            b AS (
                SELECT
                    *,
                    CONCAT_WS('|', client_id, COALESCE(print_invoice_number, ''), COALESCE(order_number, ''), invoice_date::text) AS invoice_key
                FROM base_snapshot
            ),
            l AS (
                SELECT
                    *,
                    CONCAT_WS('|', client_id, COALESCE(print_invoice_number, ''), COALESCE(order_number, ''), invoice_date::text) AS invoice_key
                FROM latest_snapshot
            ),
            events AS (
                SELECT
                    l.client_group,
                    l.client_id,
                    l.client_name,
                    l.invoice_amount AS new_debt,
                    0::numeric AS paid_debt,
                    0::numeric AS shifted_debt,
                    0::numeric AS new_overdue_debt
                FROM l
                LEFT JOIN b ON l.invoice_key = b.invoice_key
                WHERE b.invoice_key IS NULL

                UNION ALL

                SELECT
                    b.client_group,
                    b.client_id,
                    b.client_name,
                    0::numeric AS new_debt,
                    b.invoice_amount AS paid_debt,
                    0::numeric AS shifted_debt,
                    0::numeric AS new_overdue_debt
                FROM b
                LEFT JOIN l ON b.invoice_key = l.invoice_key
                WHERE l.invoice_key IS NULL

                UNION ALL

                SELECT
                    l.client_group,
                    l.client_id,
                    l.client_name,
                    0::numeric AS new_debt,
                    0::numeric AS paid_debt,
                    l.invoice_amount AS shifted_debt,
                    0::numeric AS new_overdue_debt
                FROM l
                JOIN b ON l.invoice_key = b.invoice_key
                WHERE COALESCE(l.due_date::text, '') <> COALESCE(b.due_date::text, '')

                UNION ALL

                SELECT
                    l.client_group,
                    l.client_id,
                    l.client_name,
                    0::numeric AS new_debt,
                    0::numeric AS paid_debt,
                    0::numeric AS shifted_debt,
                    l.invoice_amount AS new_overdue_debt
                FROM l
                LEFT JOIN b ON l.invoice_key = b.invoice_key
                WHERE l.is_overdue_real = TRUE
                  AND COALESCE(b.is_overdue_real, FALSE) = FALSE
            ),
            aggregated AS (
                SELECT
                    client_group,
                    client_id,
                    client_name,
                    SUM(new_debt) AS new_debt,
                    SUM(paid_debt) AS paid_debt,
                    SUM(new_debt) - SUM(paid_debt) AS net_delta,
                    SUM(shifted_debt) AS shifted_debt,
                    SUM(new_overdue_debt) AS new_overdue_debt,
                    GREATEST(ABS(SUM(new_debt)), ABS(SUM(paid_debt))) AS movement_importance
                FROM events
                GROUP BY client_group, client_id, client_name
                HAVING
                    SUM(new_debt) <> 0
                    OR SUM(paid_debt) <> 0
                    OR SUM(shifted_debt) <> 0
                    OR SUM(new_overdue_debt) <> 0
            )
            SELECT
                a.client_group,
                a.client_id,
                a.client_name,
                a.new_debt,
                a.paid_debt,
                a.net_delta,
                a.shifted_debt,
                a.new_overdue_debt,
                a.movement_importance,
                cq.credit_quality_stars,
                cq.base_stars
            FROM aggregated a
            LEFT JOIN core.v_client_credit_quality_rating cq
                ON a.client_id = cq.client_id
            ORDER BY
                a.movement_importance DESC,
                ABS(a.net_delta) DESC
        """, params)

        branch_summary = query_df("""
            WITH base_snapshot AS (
                SELECT *
                FROM core.receivables_snapshot_fact
                WHERE report_generated_date = :base_snapshot_date
            ),
            latest_snapshot AS (
                SELECT *
                FROM core.receivables_snapshot_fact
                WHERE report_generated_date = :latest_snapshot_date
            ),
            b AS (
                SELECT
                    *,
                    CONCAT_WS('|', client_id, COALESCE(print_invoice_number, ''), COALESCE(order_number, ''), invoice_date::text) AS invoice_key
                FROM base_snapshot
            ),
            l AS (
                SELECT
                    *,
                    CONCAT_WS('|', client_id, COALESCE(print_invoice_number, ''), COALESCE(order_number, ''), invoice_date::text) AS invoice_key
                FROM latest_snapshot
            ),
            events AS (
                SELECT
                    l.client_group,
                    l.invoice_amount AS new_debt,
                    0::numeric AS paid_debt,
                    0::numeric AS shifted_debt,
                    0::numeric AS new_overdue_debt
                FROM l
                LEFT JOIN b ON l.invoice_key = b.invoice_key
                WHERE b.invoice_key IS NULL

                UNION ALL

                SELECT
                    b.client_group,
                    0::numeric AS new_debt,
                    b.invoice_amount AS paid_debt,
                    0::numeric AS shifted_debt,
                    0::numeric AS new_overdue_debt
                FROM b
                LEFT JOIN l ON b.invoice_key = l.invoice_key
                WHERE l.invoice_key IS NULL

                UNION ALL

                SELECT
                    l.client_group,
                    0::numeric AS new_debt,
                    0::numeric AS paid_debt,
                    l.invoice_amount AS shifted_debt,
                    0::numeric AS new_overdue_debt
                FROM l
                JOIN b ON l.invoice_key = b.invoice_key
                WHERE COALESCE(l.due_date::text, '') <> COALESCE(b.due_date::text, '')

                UNION ALL

                SELECT
                    l.client_group,
                    0::numeric AS new_debt,
                    0::numeric AS paid_debt,
                    0::numeric AS shifted_debt,
                    l.invoice_amount AS new_overdue_debt
                FROM l
                LEFT JOIN b ON l.invoice_key = b.invoice_key
                WHERE l.is_overdue_real = TRUE
                  AND COALESCE(b.is_overdue_real, FALSE) = FALSE
            ),
            aggregated AS (
                SELECT
                    client_group,
                    SUM(new_debt) AS new_debt,
                    SUM(paid_debt) AS paid_debt,
                    SUM(new_debt) - SUM(paid_debt) AS net_delta,
                    SUM(shifted_debt) AS shifted_debt,
                    SUM(new_overdue_debt) AS new_overdue_debt,
                    GREATEST(ABS(SUM(new_debt)), ABS(SUM(paid_debt))) AS movement_importance
                FROM events
                GROUP BY client_group
                HAVING
                    SUM(new_debt) <> 0
                    OR SUM(paid_debt) <> 0
                    OR SUM(shifted_debt) <> 0
                    OR SUM(new_overdue_debt) <> 0
            )
            SELECT
                a.client_group,
                a.new_debt,
                a.paid_debt,
                a.net_delta,
                a.shifted_debt,
                a.new_overdue_debt,
                a.movement_importance,
                bh.weighted_rating
            FROM aggregated a
            LEFT JOIN core.v_executive_branch_health bh
                ON a.client_group = bh.client_group
            ORDER BY
                a.movement_importance DESC,
                ABS(a.net_delta) DESC
        """, params)

        term_shifts = query_df("""
            WITH base_snapshot AS (
                SELECT *
                FROM core.receivables_snapshot_fact
                WHERE report_generated_date = :base_snapshot_date
            ),
            latest_snapshot AS (
                SELECT *
                FROM core.receivables_snapshot_fact
                WHERE report_generated_date = :latest_snapshot_date
            ),
            b AS (
                SELECT
                    *,
                    CONCAT_WS('|', client_id, COALESCE(print_invoice_number, ''), COALESCE(order_number, ''), invoice_date::text) AS invoice_key
                FROM base_snapshot
            ),
            l AS (
                SELECT
                    *,
                    CONCAT_WS('|', client_id, COALESCE(print_invoice_number, ''), COALESCE(order_number, ''), invoice_date::text) AS invoice_key
                FROM latest_snapshot
            )
            SELECT
                l.client_group,
                l.client_id,
                l.client_name,
                cq.credit_quality_stars,
                l.invoice_date,
                l.print_invoice_number,
                l.order_number,
                l.analytics_type,
                b.due_date AS previous_due_date,
                l.due_date AS current_due_date,
                (l.due_date - b.due_date) AS due_date_delta_days,
                l.invoice_amount
            FROM l
            JOIN b ON l.invoice_key = b.invoice_key
            LEFT JOIN core.v_client_credit_quality_rating cq
                ON l.client_id = cq.client_id
            WHERE COALESCE(l.due_date::text, '') <> COALESCE(b.due_date::text, '')
            ORDER BY ABS(l.invoice_amount) DESC
        """, params)

        new_overdue = query_df("""
            WITH base_snapshot AS (
                SELECT *
                FROM core.receivables_snapshot_fact
                WHERE report_generated_date = :base_snapshot_date
            ),
            latest_snapshot AS (
                SELECT *
                FROM core.receivables_snapshot_fact
                WHERE report_generated_date = :latest_snapshot_date
            ),
            b AS (
                SELECT
                    *,
                    CONCAT_WS('|', client_id, COALESCE(print_invoice_number, ''), COALESCE(order_number, ''), invoice_date::text) AS invoice_key
                FROM base_snapshot
            ),
            l AS (
                SELECT
                    *,
                    CONCAT_WS('|', client_id, COALESCE(print_invoice_number, ''), COALESCE(order_number, ''), invoice_date::text) AS invoice_key
                FROM latest_snapshot
            )
            SELECT
                l.client_group,
                l.client_id,
                l.client_name,
                cq.credit_quality_stars,
                l.invoice_date,
                l.due_date,
                l.print_invoice_number,
                l.order_number,
                l.analytics_type,
                l.invoice_amount,
                l.days_overdue_real
            FROM l
            LEFT JOIN b ON l.invoice_key = b.invoice_key
            LEFT JOIN core.v_client_credit_quality_rating cq
                ON l.client_id = cq.client_id
            WHERE l.is_overdue_real = TRUE
              AND COALESCE(b.is_overdue_real, FALSE) = FALSE
            ORDER BY l.invoice_amount DESC
        """, params)

        if kpi.empty:
            with container:
                ui.label("Нет данных для расчета изменений.").classes("text-red-700")
            return

        k = kpi.iloc[0]

        for frame in [summary, branch_summary, term_shifts, new_overdue]:
            for col in ["invoice_date", "due_date", "previous_due_date", "current_due_date"]:
                if col in frame.columns:
                    frame[f"{col}_fmt"] = frame[col].apply(date_fmt)

        summary = prepare_money_cols(summary, ["new_debt", "paid_debt", "net_delta", "shifted_debt", "new_overdue_debt"])
        branch_summary = prepare_money_cols(branch_summary, ["new_debt", "paid_debt", "net_delta", "shifted_debt", "new_overdue_debt"])
        term_shifts = prepare_money_cols(term_shifts, ["invoice_amount"])
        new_overdue = prepare_money_cols(new_overdue, ["invoice_amount"])

        if not summary.empty:
            summary["client_display"] = summary.apply(
                lambda row: f"{row['client_id']} · {row['client_name']}",
                axis=1,
            )
            summary["client_url"] = summary["client_id"].apply(
                lambda value: f"/client/{quote(str(value))}?from=deltas"
            )
            summary["rating_html"] = summary["credit_quality_stars"].apply(
                lambda value: rating_stars_html(int(value)) if pd.notna(value) else "—"
            )

        if not branch_summary.empty:
            branch_summary["weighted_rating_fmt"] = branch_summary["weighted_rating"].apply(
                lambda value: "—" if pd.isna(value) else f"{float(value):.2f}"
            )

        def prepare_event_client_columns(frame: pd.DataFrame) -> pd.DataFrame:
            result = frame.copy()
            if result.empty:
                return result

            result["client_display"] = result.apply(
                lambda row: f"{row['client_id']} · {row['client_name']}",
                axis=1,
            )
            result["client_url"] = result["client_id"].apply(
                lambda value: f"/client/{quote(str(value))}?from=deltas"
            )
            result["rating_html"] = result["credit_quality_stars"].apply(
                lambda value: rating_stars_html(int(value)) if pd.notna(value) else "—"
            )

            return result

        term_shifts = prepare_event_client_columns(term_shifts)
        new_overdue = prepare_event_client_columns(new_overdue)

        with container:
            ui.label(
                f"Сравнение: {date_fmt(base_snapshot_date)} → {date_fmt(latest_snapshot_date)}"
            ).classes("text-sm text-gray-500 mb-4")

            with ui.row().classes("gap-4 mb-6"):
                compact_kpi("Новый долг", money(k["new_debt"]), f"{int(k['new_invoice_count'])} накл.", "text-blue-700")
                compact_kpi("Погашено", money(k["paid_debt"]), f"{int(k['paid_invoice_count'])} накл.", "text-green-700")
                compact_kpi(
                    "Чистая дельта",
                    money(k["net_delta"]),
                    "новый долг − погашено",
                    "text-orange-700" if float(k["net_delta"]) > 0 else "text-green-700",
                )
                compact_kpi("Переносы сроков", money(k["shifted_debt"]), f"{int(k['shifted_invoice_count'])} накл.", "text-orange-700")
                compact_kpi("Новая просрочка", money(k["new_overdue_debt"]), f"{int(k['new_overdue_invoice_count'])} накл.", "text-red-700")

            ui.label("Сводка по филиалам").classes("text-xl font-bold mt-6 mb-1")
            ui.label(
                "Агрегация событий периода по филиалам. Нажатие на филиал ограничивает таблицы ниже выбранным филиалом."
            ).classes("text-sm text-gray-500 mb-3")

            with ui.row().classes("items-center gap-4 mb-2"):
                selected_branch_label = ui.label("Показаны все филиалы").classes("text-sm text-gray-500")
                reset_branch_button = ui.button("ВСЕ ФИЛИАЛЫ").props("flat color=primary")

            def prepare_branch_rows():
                df = branch_summary.copy()
                if df.empty:
                    return []

                df["is_selected"] = df["client_group"].isin(selected_branches)
                df["is_dimmed"] = bool(selected_branches) & ~df["is_selected"]
                return df.to_dict("records")

            branch_table = ui.table(
                columns=[
                    {"name": "client_group", "label": "Филиал", "field": "client_group", "align": "left", "sortable": True},
                    {"name": "rating", "label": "Рейтинг", "field": "weighted_rating", "align": "center", "sortable": True},
                    {"name": "new_debt", "label": "Новый долг", "field": "new_debt_fmt", "align": "right", "sortable": True},
                    {"name": "paid_debt", "label": "Погашено", "field": "paid_debt_fmt", "align": "right", "sortable": True},
                    {"name": "net_delta", "label": "Чистая дельта", "field": "net_delta_fmt", "align": "right", "sortable": True},
                    {"name": "shifted_debt", "label": "Переносы", "field": "shifted_debt_fmt", "align": "right", "sortable": True},
                    {"name": "new_overdue_debt", "label": "Новая просрочка", "field": "new_overdue_debt_fmt", "align": "right", "sortable": True},
                ],
                rows=prepare_branch_rows(),
                pagination={"rowsPerPage": 20},
            ).classes("w-full mb-6")
            branch_table.props(table_page_props())
            add_branch_summary_slots(branch_table)

            ui.label("Сводка по клиентам").classes("text-xl font-bold mt-6 mb-1")
            ui.label(
                "Агрегация всех событий периода по филиалу и клиенту. "
                "По умолчанию отсортировано по максимальному абсолютному движению: max(Новый долг, Погашено)."
            ).classes("text-sm text-gray-500 mb-3")

            search = ui.input(
                placeholder="Поиск клиента по названию или коду..."
            ).props("clearable").classes("w-96 mb-3")

            summary_table = ui.table(
                columns=[
                    {"name": "client", "label": "Наименование", "field": "client_display", "align": "left", "sortable": True},
                    {"name": "rating", "label": "Рейтинг", "field": "credit_quality_stars", "align": "center", "sortable": True},
                    {"name": "client_group", "label": "Филиал", "field": "client_group", "align": "center", "sortable": True},
                    {"name": "new_debt", "label": "Новый долг", "field": "new_debt_fmt", "align": "right", "sortable": True},
                    {"name": "paid_debt", "label": "Погашено", "field": "paid_debt_fmt", "align": "right", "sortable": True},
                    {"name": "net_delta", "label": "Чистая дельта", "field": "net_delta_fmt", "align": "right", "sortable": True},
                    {"name": "shifted_debt", "label": "Переносы", "field": "shifted_debt_fmt", "align": "right", "sortable": True},
                    {"name": "new_overdue_debt", "label": "Новая просрочка", "field": "new_overdue_debt_fmt", "align": "right", "sortable": True},
                ],
                rows=[],
                pagination={"rowsPerPage": 20},
            ).classes("w-full mb-6")
            summary_table.props(table_page_props())
            add_client_summary_slot(summary_table)

            term_shift_table = render_table(
                "Изменение сроков оплаты",
                "Накладные, по которым изменился срок оплаты между двумя снэпшотами.",
                term_shifts,
                [
                    {"name": "client", "label": "Наименование", "field": "client_display", "align": "left", "sortable": True},
                    {"name": "rating", "label": "Рейтинг", "field": "credit_quality_stars", "align": "center", "sortable": True},
                    {"name": "client_group", "label": "Филиал", "field": "client_group", "align": "center", "sortable": True},
                    {"name": "invoice_date", "label": "Дата накладной", "field": "invoice_date_fmt", "sortable": True},
                    {"name": "print_invoice_number", "label": "Печ. номер", "field": "print_invoice_number", "sortable": True},
                    {"name": "order_number", "label": "Заказ", "field": "order_number", "sortable": True},
                    {"name": "previous_due_date", "label": "Было", "field": "previous_due_date_fmt", "sortable": True},
                    {"name": "current_due_date", "label": "Стало", "field": "current_due_date_fmt", "sortable": True},
                    {"name": "due_date_delta_days", "label": "Δ дней", "field": "due_date_delta_days", "align": "right", "sortable": True},
                    {"name": "invoice_amount", "label": "Сумма", "field": "invoice_amount_fmt", "align": "right", "sortable": True},
                ],
                "Изменений сроков оплаты за выбранный период нет.",
            )

            new_overdue_table = render_table(
                "Новая просрочка",
                "Накладные, которые не были просрочены в базовом снэпшоте, но стали просроченными в последнем.",
                new_overdue,
                [
                    {"name": "client", "label": "Наименование", "field": "client_display", "align": "left", "sortable": True},
                    {"name": "rating", "label": "Рейтинг", "field": "credit_quality_stars", "align": "center", "sortable": True},
                    {"name": "client_group", "label": "Филиал", "field": "client_group", "align": "center", "sortable": True},
                    {"name": "invoice_date", "label": "Дата накладной", "field": "invoice_date_fmt", "sortable": True},
                    {"name": "due_date", "label": "Оплатить до", "field": "due_date_fmt", "sortable": True},
                    {"name": "print_invoice_number", "label": "Печ. номер", "field": "print_invoice_number", "sortable": True},
                    {"name": "order_number", "label": "Заказ", "field": "order_number", "sortable": True},
                    {"name": "invoice_amount", "label": "Сумма", "field": "invoice_amount_fmt", "align": "right", "sortable": True},
                    {"name": "days_overdue_real", "label": "Дней", "field": "days_overdue_real", "align": "right", "sortable": True},
                ],
                "Новой просрочки за выбранный период нет.",
            )

            if term_shift_table is not None:
                add_event_table_slots(term_shift_table)

            if new_overdue_table is not None:
                add_event_table_slots(new_overdue_table)

            def filtered_summary_rows():
                df = summary.copy()

                if selected_branches:
                    df = df[df["client_group"].isin(selected_branches)]

                value = (search.value or "").strip().lower()
                if value:
                    df = df[
                        df["client_id"].astype(str).str.lower().str.contains(value, na=False)
                        | df["client_name"].astype(str).str.lower().str.contains(value, na=False)
                    ]

                return df.to_dict("records")

            def filtered_table_rows(df: pd.DataFrame):
                result = df.copy()
                if selected_branches:
                    result = result[result["client_group"].isin(selected_branches)]
                return result.to_dict("records")

            def apply_branch_filter():
                if selected_branches:
                    selected_branch_label.text = f"Фильтр: {', '.join(selected_branches)}"
                else:
                    selected_branch_label.text = "Показаны все филиалы"
                selected_branch_label.update()

                branch_table.rows = prepare_branch_rows()
                branch_table.update()

                summary_table.rows = filtered_summary_rows()
                summary_table.update()

                if term_shift_table is not None:
                    term_shift_table.rows = filtered_table_rows(term_shifts)
                    term_shift_table.update()

                if new_overdue_table is not None:
                    new_overdue_table.rows = filtered_table_rows(new_overdue)
                    new_overdue_table.update()

            def toggle_branch(event):
                branch = event.args
                if branch in selected_branches:
                    selected_branches.remove(branch)
                else:
                    selected_branches.append(branch)
                apply_branch_filter()

            def reset_branch_filter():
                selected_branches.clear()
                apply_branch_filter()

            branch_table.on("branch_click", toggle_branch)
            reset_branch_button.on_click(reset_branch_filter)
            search.on_value_change(lambda _: apply_branch_filter())

            apply_branch_filter()

    selected_offset.on_value_change(lambda _: render())
    render()
