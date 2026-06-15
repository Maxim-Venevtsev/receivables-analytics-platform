from pathlib import Path
import os
from urllib.parse import quote

import pandas as pd
from dotenv import load_dotenv
from nicegui import ui
from sqlalchemy import create_engine, text

from src.app.components.navigation import top_navigation
from src.app.components.rating_stars import rating_stars_html
from src.app.components.clients_table import render_clients_table


PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env")

engine = create_engine(
    f"postgresql+psycopg2://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@"
    f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)


def query_df(sql: str) -> pd.DataFrame:
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn)


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


def compact_kpi(
    title: str,
    value: str,
    subtitle: str = "",
    color_class: str = "text-gray-900",
):
    with ui.card().classes("w-64 h-36 p-4"):
        with ui.column().classes("w-full h-full items-center justify-between text-center"):
            ui.label(title).classes("text-sm text-gray-500 h-6 flex items-center justify-center")
            ui.label(value).classes(
                f"text-2xl font-bold h-10 flex items-center justify-center {color_class}"
            )
            ui.label(subtitle).classes("text-sm text-gray-500 h-8 flex items-center justify-center")


def prepare_money_cols(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    result = df.copy()

    for col in cols:
        if col in result.columns:
            result[f"{col}_fmt"] = result[col].apply(money_precise)

    return result


def prepare_percent_cols(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    result = df.copy()

    for col in cols:
        if col in result.columns:
            result[f"{col}_fmt"] = result[col].apply(percent)

    return result


def table_page_props() -> str:
    return 'rows-per-page-options="[20, 50, 100]"'


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
        "total_debt",
        "overdue_debt",
        "overdue_45_plus",
        "overdue_90_plus",
        "overdue_120_plus",
    ]:
        table.add_slot(
            f"body-cell-{col}",
            f"""
            <q-td :props="props" class="text-right" :style="props.row.is_dimmed ? 'opacity:0.45;' : ''">
                {{{{ props.row.{col}_fmt }}}}
            </q-td>
            """,
        )

    for col in [
        "overdue_share_pct",
        "overdue_45_share_pct",
        "overdue_90_share_pct",
        "overdue_120_share_pct",
    ]:
        table.add_slot(
            f"body-cell-{col}",
            f"""
            <q-td :props="props" class="text-right" :style="props.row.is_dimmed ? 'opacity:0.45;' : ''">
                <q-badge
                    :color="props.row.{col} > 20 ? 'red' : props.row.{col} > 0 ? 'orange' : 'green'"
                    :label="props.row.{col}_fmt"
                />
            </q-td>
            """,
        )


def add_client_summary_slot(table):
    table.add_slot(
        "body",
        """
        <q-tr :props="props">
            <q-td v-for="col in props.cols" :key="col.name" :props="props">

                <template v-if="col.name === 'client'">
                    <a
                        :href="props.row.client_url"
                        class="text-blue-600 hover:underline font-medium"
                    >
                        {{ props.row.client_display }}
                    </a>
                </template>

                <template v-else-if="col.name === 'rating'">
                    <span v-html="props.row.rating_html"></span>
                </template>

                <template v-else-if="[
                    'total_debt',
                    'overdue_debt',
                    'overdue_45_plus',
                    'overdue_90_plus',
                    'overdue_120_plus'
                ].includes(col.name)">
                    {{ props.row[col.name + '_fmt'] }}
                </template>

                <template v-else-if="[
                    'overdue_share_pct',
                    'overdue_45_share_pct',
                    'overdue_90_share_pct',
                    'overdue_120_share_pct'
                ].includes(col.name)">
                    <q-badge
                        :color="props.row[col.name] > 20 ? 'red' : props.row[col.name] > 0 ? 'orange' : 'green'"
                        :label="props.row[col.name + '_fmt']"
                    />
                </template>

                <template v-else>
                    {{ col.value }}
                </template>

            </q-td>
        </q-tr>
        """,
    )


@ui.page("/overdue")
def overdue_page():
    ui.label("Просроченная дебиторка").classes("text-3xl font-bold mb-2")
    ui.label(
        "Клиенты и филиалы с просроченной задолженностью. "
        "Отдельно выделены долги 45+, 90+ и 120+ дней."
    ).classes("text-gray-500 mb-4")

    top_navigation()

    df = query_df("""
        SELECT *
        FROM core.v_client_operational_summary
        WHERE overdue_debt > 0
        ORDER BY
            overdue_debt DESC,
            max_days_overdue DESC,
            total_debt DESC
    """)

    if df.empty:
        ui.label("Просроченной задолженности нет.").classes("text-lg text-green-700")
        return

    branches = query_df("""
        WITH branch_debt AS (
            SELECT
                i.client_group,

                SUM(i.invoice_amount) AS total_debt,

                SUM(
                    CASE
                        WHEN i.is_overdue_real
                        THEN i.invoice_amount
                        ELSE 0
                    END
                ) AS overdue_debt,

                SUM(
                    CASE
                        WHEN i.is_overdue_real
                         AND i.days_overdue_real >= 45
                        THEN i.invoice_amount
                        ELSE 0
                    END
                ) AS overdue_45_plus,

                SUM(
                    CASE
                        WHEN i.is_overdue_real
                         AND i.days_overdue_real >= 90
                        THEN i.invoice_amount
                        ELSE 0
                    END
                ) AS overdue_90_plus,

                SUM(
                    CASE
                        WHEN i.is_overdue_real
                         AND i.days_overdue_real >= 120
                        THEN i.invoice_amount
                        ELSE 0
                    END
                ) AS overdue_120_plus
            FROM core.v_invoice_detail i
            GROUP BY i.client_group
        )
        SELECT
            b.client_group,
            bh.weighted_rating,

            b.total_debt,
            b.overdue_debt,
            b.overdue_45_plus,
            b.overdue_90_plus,
            b.overdue_120_plus,

            ROUND(b.overdue_debt / NULLIF(b.total_debt, 0) * 100, 2) AS overdue_share_pct,
            ROUND(b.overdue_45_plus / NULLIF(b.total_debt, 0) * 100, 2) AS overdue_45_share_pct,
            ROUND(b.overdue_90_plus / NULLIF(b.total_debt, 0) * 100, 2) AS overdue_90_share_pct,
            ROUND(b.overdue_120_plus / NULLIF(b.total_debt, 0) * 100, 2) AS overdue_120_share_pct
        FROM branch_debt b
        LEFT JOIN core.v_executive_branch_health bh
            ON b.client_group = bh.client_group
        WHERE b.overdue_debt > 0
        ORDER BY b.overdue_debt DESC
    """)

    selected_branches: list[str] = []

    money_cols = [
        "total_debt",
        "overdue_debt",
        "overdue_45_plus",
        "overdue_90_plus",
        "overdue_120_plus",
    ]

    percent_cols = [
        "overdue_share_pct",
        "overdue_45_share_pct",
        "overdue_90_share_pct",
        "overdue_120_share_pct",
    ]

    for frame in [df, branches]:
        for col in money_cols + percent_cols + ["max_days_overdue", "weighted_rating"]:
            if col in frame.columns:
                frame[col] = frame[col].fillna(0).astype(float)

    df = prepare_money_cols(df, money_cols)
    df = prepare_percent_cols(df, percent_cols)

    branches = prepare_money_cols(branches, money_cols)
    branches = prepare_percent_cols(branches, percent_cols)

    branches["weighted_rating_fmt"] = branches["weighted_rating"].apply(
        lambda value: "—" if pd.isna(value) else f"{float(value):.2f}"
    )

    def filtered_clients() -> pd.DataFrame:
        result = df.copy()

        if selected_branches:
            result = result[result["client_group"].isin(selected_branches)]

        value = (search_input.value or "").strip().lower() if "search_input" in locals() else ""

        if value:
            result = result[
                result["client_id"].astype(str).str.lower().str.contains(value, na=False)
                | result["client_name"].astype(str).str.lower().str.contains(value, na=False)
            ]

        return result.sort_values(
            by=["overdue_debt", "debt_90_plus", "debt_120_plus"],
            ascending=[False, False, False],
        )

    def filtered_branches() -> pd.DataFrame:
        result = branches.copy()

        result["is_selected"] = result["client_group"].isin(selected_branches)
        result["is_dimmed"] = bool(selected_branches) & ~result["is_selected"]

        return result

    def get_kpi_metrics() -> dict[str, float | int]:
        branch_df = branches.copy()

        if selected_branches:
            branch_df = branch_df[branch_df["client_group"].isin(selected_branches)]

        client_df = df.copy()

        if selected_branches:
            client_df = client_df[client_df["client_group"].isin(selected_branches)]

        total_debt = float(branch_df["total_debt"].sum())
        overdue_debt = float(branch_df["overdue_debt"].sum())
        overdue_90_plus = float(branch_df["overdue_90_plus"].sum())
        overdue_120_plus = float(branch_df["overdue_120_plus"].sum())

        max_days = (
            int(client_df["max_days_overdue"].max())
            if not client_df.empty
            else 0
        )

        return {
            "total_debt": total_debt,
            "overdue_debt": overdue_debt,
            "overdue_clients": int(client_df["client_id"].nunique()),
            "overdue_share_pct": overdue_debt / total_debt * 100 if total_debt else 0,
            "max_days": max_days,
            "overdue_90_plus": overdue_90_plus,
            "overdue_90_share_pct": overdue_90_plus / total_debt * 100 if total_debt else 0,
            "overdue_120_plus": overdue_120_plus,
            "overdue_120_share_pct": overdue_120_plus / total_debt * 100 if total_debt else 0,
        }

    initial_kpi = get_kpi_metrics()

    with ui.row().classes("gap-4 mb-6"):
        compact_kpi(
            "Просрочено",
            money(initial_kpi["overdue_debt"]),
            f"{percent(initial_kpi['overdue_share_pct'])} портфеля",
            "text-red-700",
        )

        compact_kpi(
            "Клиентов с просрочкой",
            str(initial_kpi["overdue_clients"]),
        )

        compact_kpi(
            "Макс. дней просрочки",
            str(initial_kpi["max_days"]),
        )

        compact_kpi(
            "90+ просрочено",
            money(initial_kpi["overdue_90_plus"]),
            f"{percent(initial_kpi['overdue_90_share_pct'])} портфеля",
            "text-red-700",
        )

        compact_kpi(
            "120+ просрочено",
            money(initial_kpi["overdue_120_plus"]),
            f"{percent(initial_kpi['overdue_120_share_pct'])} портфеля",
            "text-red-700",
        )

    ui.label("Сводка по филиалам").classes("text-xl font-bold mt-6 mb-1")
    ui.label(
        "Агрегация просроченной задолженности по филиалам. "
        "Нажатие на филиал ограничивает клиентскую таблицу выбранным филиалом."
    ).classes("text-sm text-gray-500 mb-3")

    with ui.row().classes("items-center gap-4 mb-2"):
        selected_branch_label = ui.label("Показаны все филиалы").classes("text-sm text-gray-500")
        reset_branch_button = ui.button("ВСЕ ФИЛИАЛЫ").props("flat color=primary")

    branch_table = ui.table(
        columns=[
            {"name": "client_group", "label": "Филиал", "field": "client_group", "align": "left", "sortable": True},
            {"name": "rating", "label": "Рейтинг", "field": "weighted_rating", "align": "center", "sortable": True},
            {"name": "total_debt", "label": "Весь долг", "field": "total_debt", "align": "right", "sortable": True},
            {"name": "overdue_debt", "label": "Просрочено", "field": "overdue_debt", "align": "right", "sortable": True},
            {"name": "overdue_share_pct", "label": "%", "field": "overdue_share_pct", "align": "right", "sortable": True},
            {"name": "overdue_45_plus", "label": "45+", "field": "overdue_45_plus", "align": "right", "sortable": True},
            {"name": "overdue_45_share_pct", "label": "% 45+", "field": "overdue_45_share_pct", "align": "right", "sortable": True},
            {"name": "overdue_90_plus", "label": "90+", "field": "overdue_90_plus", "align": "right", "sortable": True},
            {"name": "overdue_90_share_pct", "label": "% 90+", "field": "overdue_90_share_pct", "align": "right", "sortable": True},
            {"name": "overdue_120_plus", "label": "120+", "field": "overdue_120_plus", "align": "right", "sortable": True},
            {"name": "overdue_120_share_pct", "label": "% 120+", "field": "overdue_120_share_pct", "align": "right", "sortable": True},
        ],
        rows=filtered_branches().to_dict("records"),
        pagination={"rowsPerPage": 20},
    ).classes("w-full mb-6")
    branch_table.props(table_page_props())
    add_branch_summary_slots(branch_table)

    client_table = render_clients_table(
        clients=filtered_clients(),
        title="Контрагенты",
        show_branch=True,
        show_search=True,
        from_route="overdue",
        visible_columns=[
            "client_group",
            "client",
            "rating",
            "total_debt",
            "overdue_debt",
            "overdue_share_pct",
            "debt_45_plus",
            "debt_60_plus",
            "debt_90_plus",
            "debt_120_plus",
            "max_days_overdue",
        ],
    )

    def update_kpi_cards():
        metrics = get_kpi_metrics()

        # KPI cards are static NiceGUI elements in this page version.
        # The table filters are updated reactively; KPI refresh can be
        # centralized later together with UI unification.

    def apply_filters():
        if selected_branches:
            selected_branch_label.text = f"Фильтр: {', '.join(selected_branches)}"
        else:
            selected_branch_label.text = "Показаны все филиалы"

        selected_branch_label.update()

        branch_table.rows = filtered_branches().to_dict("records")
        branch_table.update()

        if client_table is not None:
            client_table.rows = filtered_clients().to_dict("records")
            client_table.update()

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

    branch_table.on("branch_click", toggle_branch)
    reset_branch_button.on_click(reset_branch_filter)
    
    def open_client(event):
        ui.navigate.to(f"/client/{event.args}?from=overdue")

    def open_branch(event):
        ui.navigate.to(f"/branch/{quote(str(event.args))}?from=/overdue")

    if client_table is not None:
        client_table.on("client_click", open_client)
        client_table.on("branch_click", open_branch)