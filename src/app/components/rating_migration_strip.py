import pandas as pd
from nicegui import ui

from src.app.components.rating_stars import rating_stars_html


def _date_fmt(value) -> str:
    if pd.isna(value):
        return ""
    return pd.to_datetime(value).strftime("%d.%m.%Y")


def _stars_text(value) -> str:
    if pd.isna(value):
        return "—"
    return f"{int(value)}★"


def render_rating_migration_strip(row: pd.Series):
    start_stars = row.get("start_stars")
    end_stars = row.get("end_stars")
    rating_delta = row.get("rating_delta")
    migration_status = row.get("migration_status")
    rating_change_label = row.get("rating_change_label", "")

    start_date = _date_fmt(row.get("start_snapshot_date"))
    end_date = _date_fmt(row.get("end_snapshot_date"))

    if migration_status == "UPGRADED":
        icon = "↑"
        color = "bg-green-50 border-green-200 text-green-800"
        label = "Рейтинг улучшился"
    elif migration_status == "DOWNGRADED":
        icon = "↓"
        color = "bg-red-50 border-red-200 text-red-800"
        label = "Рейтинг ухудшился"
    elif migration_status == "NEW":
        icon = "●"
        color = "bg-blue-50 border-blue-200 text-blue-800"
        label = "Новый в истории"
    elif migration_status == "LOST":
        icon = "○"
        color = "bg-gray-50 border-gray-200 text-gray-800"
        label = "Исчез из рейтинга"
    else:
        icon = "→"
        color = "bg-gray-50 border-gray-200 text-gray-800"
        label = "Рейтинг стабилен"

    delta_text = ""
    if pd.notna(rating_delta):
        delta_value = int(rating_delta)
        if delta_value > 0:
            delta_text = f" · +{delta_value}"
        elif delta_value < 0:
            delta_text = f" · {delta_value}"

    with ui.card().classes(f"w-full p-3 mb-6 border {color}"):
        with ui.row().classes("items-center justify-between w-full"):
            with ui.row().classes("items-center gap-3"):
                ui.label(icon).classes("text-lg font-bold")

                if pd.notna(end_stars):
                    ui.html(rating_stars_html(int(end_stars)))

                ui.label(
                    f"{_stars_text(start_stars)} → {_stars_text(end_stars)}"
                ).classes("text-sm font-bold")

                ui.label(f"{label}{delta_text}").classes("text-sm font-bold")

                if rating_change_label and rating_change_label != label:
                    ui.label(str(rating_change_label)).classes("text-xs text-gray-500")

            ui.label(
                f"{start_date} → {end_date}"
            ).classes("text-sm text-gray-600")