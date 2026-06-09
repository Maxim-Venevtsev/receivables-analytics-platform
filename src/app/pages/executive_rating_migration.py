from pathlib import Path
import os

import pandas as pd
from dotenv import load_dotenv
from fastapi import Request
from nicegui import ui
from sqlalchemy import create_engine, text

from src.app.components.navigation import top_navigation
from src.app.components.kpi_cards import money


PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env")

engine = create_engine(
    f"postgresql+psycopg2://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@"
    f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)


def query_df(sql: str, params: dict | None = None) -> pd.DataFrame:
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn, params=params)


def compact_kpi(title: str, value: str, subtitle: str = "", color_class: str = "text-gray-900"):
    with ui.card().classes("w-64 h-32 p-4"):
        with ui.column().classes("w-full h-full items-center justify-between text-center"):
            ui.label(title).classes("text-sm text-gray-500")
            ui.label(value).classes(f"text-2xl font-bold {color_class}")
            ui.label(subtitle).classes("text-xs text-gray-500")


def rating_label(value) -> str:
    if pd.isna(value):
        return "—"
    return f"{int(value)}★"


@ui.page("/executive/rating-migration")
def executive_rating_migration_page(request: Request):
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

    def load_summary(period_label: str) -> pd.DataFrame:
        return query_df("""
            SELECT *
            FROM core.v_executive_rating_migration_summary
            WHERE period_label = :period_label
        """, {"period_label": period_label})

    def load_clients(period_label: str) -> pd.DataFrame:
        return query_df("""
            SELECT *
            FROM core.v_executive_rating_migration_clients
            WHERE period_label = :period_label
              AND migration_status IN ('UPGRADED', 'DOWNGRADED')
            ORDER BY rating_delta ASC NULLS LAST, client_name
        """, {"period_label": period_label})

    def prepare_rows(df: pd.DataFrame):
        dff = df.copy()

        dff["start_rating_fmt"] = dff["start_stars"].apply(rating_label)
        dff["end_rating_fmt"] = dff["end_stars"].apply(rating_label)

        dff["rating_delta_fmt"] = dff["rating_delta"].apply(
            lambda value: "—" if pd.isna(value) else f"{int(value):+d}"
        )

        dff["status_fmt"] = dff["migration_status"].map({
            "UPGRADED": "Повысился",
            "DOWNGRADED": "Понизился",
        }).fillna(dff["migration_status"])

        return dff.to_dict("records")

    def render():
        period_label = selected_period.value

        summary = load_summary(period_label)
        clients = load_clients(period_label)

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

            ui.label("Клиенты с изменившимся рейтингом").classes("text-xl font-bold mb-2")

            if clients.empty:
                ui.label("За выбранный период изменений рейтинга нет.").classes("text-gray-500")
                return

            table = ui.table(
                columns=[
                    {"name": "client_name", "label": "Клиент", "field": "client_name", "sortable": True, "align": "left"},
                    {"name": "client_group", "label": "Филиал", "field": "client_group", "sortable": True},
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
                        :color="props.row.migration_status === 'UPGRADED' ? 'green' : 'red'"
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

    selected_period.on_value_change(lambda _: render())
    render()