import asyncio
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
from src.app.components.kpi_cards import money
from src.app.components.rating_stars import rating_stars_html


PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env")

engine = create_engine(
    f"postgresql+psycopg2://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@"
    f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)


async def query_df(sql: str, params: dict | None = None, *, operation: str) -> pd.DataFrame:
    return await read_dataframe(engine, sql, operation=operation, params=params)


def compact_kpi(title: str, value: str, subtitle: str = "", color_class: str = "text-gray-900"):
    with ui.card().classes("w-64 h-32 p-4"):
        with ui.column().classes("w-full h-full items-center justify-between text-center"):
            ui.label(title).classes("text-sm text-gray-500")
            ui.label(value).classes(f"text-2xl font-bold {color_class}")
            ui.label(subtitle).classes("text-xs text-gray-500")


def rating_label(value) -> str:
    if pd.isna(value):
        return "—"
    return f"{float(value):.1f}"


def rating_html(value) -> str:
    if pd.isna(value):
        return "—"
    stars = max(1, min(5, int(round(float(value)))))
    return rating_stars_html(stars)


def normalized_migration_status(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).upper()


def period_days_for_label(period_label: str) -> int | None:
    if period_label == "Все":
        return None
    return int(period_label.split()[0])


def credit_quality_migration_cte() -> str:
    return """
        WITH bounds AS (
            SELECT
                MIN(snapshot_date) AS min_snapshot_date,
                MAX(snapshot_date) AS max_snapshot_date
            FROM core.client_credit_quality_history
        ),
        period_bounds AS (
            SELECT
                :period_label AS period_label,
                :period_days AS period_days,
                CASE
                    WHEN :period_days IS NULL THEN b.min_snapshot_date
                    ELSE COALESCE(
                        (
                            SELECT MIN(h.snapshot_date)
                            FROM core.client_credit_quality_history h
                            WHERE h.snapshot_date >= b.max_snapshot_date - (:period_days * INTERVAL '1 day')
                        ),
                        b.min_snapshot_date
                    )
                END AS start_snapshot_date,
                b.max_snapshot_date AS end_snapshot_date
            FROM bounds b
        ),
        migration AS (
            SELECT
                pb.period_label,
                pb.period_days,
                pb.start_snapshot_date,
                pb.end_snapshot_date,
                e.client_id,
                e.client_name,
                e.client_group,
                e.parent_org_id,
                s.credit_quality_stars::numeric AS start_rating,
                e.credit_quality_stars::numeric AS end_rating,
                e.credit_quality_stars::numeric - s.credit_quality_stars::numeric AS rating_delta,
                CASE
                    WHEN s.credit_quality_stars IS NULL AND e.credit_quality_stars IS NOT NULL
                        THEN 'new'
                    WHEN e.credit_quality_stars::numeric - s.credit_quality_stars::numeric > 0.05
                        THEN 'improved'
                    WHEN e.credit_quality_stars::numeric - s.credit_quality_stars::numeric < -0.05
                        THEN 'worsened'
                    ELSE 'stable'
                END AS migration_status
            FROM period_bounds pb
            JOIN core.client_credit_quality_history e
                ON e.snapshot_date = pb.end_snapshot_date
            LEFT JOIN core.client_credit_quality_history s
                ON s.client_id = e.client_id
               AND s.snapshot_date = pb.start_snapshot_date
        )
    """


@ui.page(
    "/executive/rating-migration",
    response_timeout=get_page_response_timeout(),
)
@page_build("executive_rating_migration", "/executive/rating-migration")
async def executive_rating_migration_page(request: Request):
    ui.label("Миграция рейтингов").classes("text-3xl font-bold mb-2")
    ui.label("Клиенты, у которых рейтинг изменился между началом и концом выбранного периода.").classes(
        "text-gray-500 mb-4"
    )

    top_navigation()

    with ui.row().classes("mb-4"):
        ui.button("← Назад к сводке", on_click=lambda: ui.navigate.to("/executive")).props("flat color=primary")

    selected_period = ui.toggle(
        options=["28 дней", "90 дней", "180 дней", "Все"],
        value="28 дней",
    ).props("outline").classes("mb-4")

    content = ui.column().classes("w-full")

    async def load_summary(period_label: str) -> pd.DataFrame:
        return await query_df(
            credit_quality_migration_cte()
            + """
            SELECT
                period_label,
                period_days,
                start_snapshot_date,
                end_snapshot_date,
                COUNT(*) FILTER (WHERE migration_status = 'improved') AS upgraded_clients,
                COUNT(*) FILTER (WHERE migration_status = 'worsened') AS downgraded_clients,
                COUNT(*) FILTER (WHERE migration_status = 'new') AS new_clients,
                COUNT(*) FILTER (WHERE migration_status = 'stable') AS unchanged_clients,
                COUNT(*) FILTER (WHERE migration_status = 'improved')
                    - COUNT(*) FILTER (WHERE migration_status = 'worsened') AS net_migration_clients
            FROM migration
            GROUP BY
                period_label,
                period_days,
                start_snapshot_date,
                end_snapshot_date
            """,
            {
                "period_label": period_label,
                "period_days": period_days_for_label(period_label),
            },
            operation="executive_rating_migration_summary",
        )

    async def load_clients(period_label: str) -> pd.DataFrame:
        return await query_df(
            credit_quality_migration_cte()
            + """
            SELECT *
            FROM migration
            WHERE migration_status IN ('improved', 'worsened')
            ORDER BY rating_delta ASC NULLS LAST, client_name
            """,
            {
                "period_label": period_label,
                "period_days": period_days_for_label(period_label),
            },
            operation="executive_rating_migration_clients",
        )

    def prepare_rows(df: pd.DataFrame):
        dff = df.copy()

        dff["start_rating_fmt"] = dff["start_rating"].apply(rating_label)
        dff["end_rating_fmt"] = dff["end_rating"].apply(rating_label)
        dff["start_rating_html"] = dff["start_rating"].apply(rating_html)
        dff["end_rating_html"] = dff["end_rating"].apply(rating_html)

        dff["rating_delta_fmt"] = dff["rating_delta"].apply(
            lambda value: "—" if pd.isna(value) else f"{float(value):+.1f}"
        )

        dff["migration_status_normalized"] = dff["migration_status"].apply(normalized_migration_status)

        dff["status_fmt"] = dff["migration_status_normalized"].map({
            "UPGRADED": "Повысился",
            "IMPROVED": "Повысился",
            "DOWNGRADED": "Понизился",
            "WORSENED": "Понизился",
        }).fillna(dff["migration_status"])

        return dff.to_dict("records")

    async def render_content():
        period_label = selected_period.value

        summary = await load_summary(period_label)
        clients = await load_clients(period_label)

        content.clear()

        with content:
            if summary.empty:
                ui.label("Нет данных по выбранному периоду.").classes("text-red-700")
                return

            s = summary.iloc[0]

            start_date = pd.to_datetime(s["start_snapshot_date"]).strftime("%d.%m.%Y")
            end_date = pd.to_datetime(s["end_snapshot_date"]).strftime("%d.%m.%Y")

            ui.label(
                f"Период: {start_date} → {end_date}"
            ).classes("text-sm text-gray-500 mb-3")

            with ui.row().classes("gap-4 mb-6"):
                compact_kpi(
                    "Улучшились",
                    str(int(s["upgraded_clients"])),
                    "рост рейтинга",
                    "text-green-600",
                )
                compact_kpi(
                    "Ухудшились",
                    str(int(s["downgraded_clients"])),
                    "снижение рейтинга",
                    "text-red-600",
                )
                compact_kpi(
                    "Чистая миграция",
                    f"{int(s['net_migration_clients']):+d}",
                    "улучшились − ухудшились",
                    "text-green-600" if int(s["net_migration_clients"]) >= 0 else "text-red-600",
                )
                compact_kpi(
                    "Новые в рейтинге",
                    str(int(s["new_clients"])),
                    "не включены в таблицу",
                    "text-blue-600",
                )

            ui.label("Контрагенты с изменившимся рейтингом").classes("text-xl font-bold mb-2")

            if clients.empty:
                ui.label("За выбранный период изменений рейтинга нет.").classes("text-gray-500")
                return

            table = ui.table(
                columns=[
                    {"name": "client_group", "label": "Филиал", "field": "client_group", "sortable": True},
                    {"name": "client_name", "label": "Наименование", "field": "client_name", "sortable": True, "align": "left"},
                    {"name": "start_rating_fmt", "label": "Было", "field": "start_rating_fmt", "align": "center"},
                    {"name": "end_rating_fmt", "label": "Стало", "field": "end_rating_fmt", "align": "center"},
                    {"name": "rating_delta", "label": "Δ", "field": "rating_delta", "align": "center", "sortable": True},
                    {"name": "status_fmt", "label": "Статус", "field": "status_fmt", "align": "center", "sortable": True},
                ],
                rows=prepare_rows(clients),
                pagination=25,
            ).classes("w-full")

            table.add_slot(
                "body-cell-client_name",
                """
                <q-td :props="props" class="text-left">
                    <q-btn flat dense color="primary"
                        class="text-left"
                        :label="props.row.client_id + ' · ' + props.row.client_name"
                        @click="$parent.$emit('client_click', props.row.client_id)" />
                </q-td>
                """,
            )

            table.add_slot(
                "body-cell-start_rating_fmt",
                """
                <q-td :props="props" class="text-center">
                    <span v-html="props.row.start_rating_html"></span>
                </q-td>
                """,
            )

            table.add_slot(
                "body-cell-end_rating_fmt",
                """
                <q-td :props="props" class="text-center">
                    <span v-html="props.row.end_rating_html"></span>
                </q-td>
                """,
            )

            table.add_slot(
                "body-cell-rating_delta",
                """
                <q-td :props="props" class="text-center">
                    <q-badge
                        :color="props.row.rating_delta > 0 ? 'green' : 'red'"
                        :label="props.row.rating_delta_fmt"
                    />
                </q-td>
                """,
            )

            table.add_slot(
                "body-cell-status_fmt",
                """
                <q-td :props="props" class="text-center">
                    <q-badge
                        :color="['UPGRADED', 'IMPROVED'].includes(props.row.migration_status_normalized) ? 'green' : 'red'"
                        :label="props.row.status_fmt"
                    />
                </q-td>
                """,
            )

            table.on(
                "client_click",
                lambda event: ui.navigate.to(
                    f"/client/{event.args}?from=executive-rating-migration"
                ),
            )

    render_lock = asyncio.Lock()

    async def render() -> None:
        async with render_lock:
            await render_content()

    async def rerender(_event) -> None:
        await render()

    selected_period.on_value_change(rerender)
    await render()
