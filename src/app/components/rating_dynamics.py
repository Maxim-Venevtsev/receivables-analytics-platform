import pandas as pd
from nicegui import ui

from src.app.components.rating_stars import rating_stars_html


def _safe_int(value, default: int | None = None) -> int | None:
    if value is None or pd.isna(value):
        return default

    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _format_date(value) -> str:
    if value is None or pd.isna(value):
        return "—"

    try:
        return pd.to_datetime(value).strftime("%d.%m.%Y")
    except Exception:
        return str(value)

def portfolio_stars_html(weighted_rating) -> str:
    if weighted_rating is None or pd.isna(weighted_rating):
        return "—"

    rounded_stars = int(round(float(weighted_rating)))
    rounded_stars = max(1, min(5, rounded_stars))

    full = "★" * rounded_stars
    empty = "☆" * (5 - rounded_stars)

    return f'<span style="color:#f59e0b; font-size:18px;">{full}{empty}</span>'

def _status_config(status: str) -> dict[str, str]:
    if status == "IMPROVED":
        return {
            "icon": "↗",
            "label": "Рейтинг улучшился",
            "color": "text-green-600",
            "border": "border-green-200",
            "bg": "bg-green-50",
        }

    if status == "WORSENED":
        return {
            "icon": "↘",
            "label": "Рейтинг ухудшился",
            "color": "text-red-600",
            "border": "border-red-200",
            "bg": "bg-red-50",
        }

    if status == "NEW":
        return {
            "icon": "●",
            "label": "Новый в истории",
            "color": "text-blue-600",
            "border": "border-blue-200",
            "bg": "bg-blue-50",
        }

    return {
        "icon": "→",
        "label": "Рейтинг стабилен",
        "color": "text-gray-600",
        "border": "border-gray-200",
        "bg": "bg-gray-50",
    }


def render_client_rating_dynamics_strip(rating_row: dict | pd.Series | None):
    """
    Compact rating dynamics strip for Client Card.

    Expected fields:
    - stars
    - previous_stars
    - rating_delta
    - rating_change_status
    - snapshot_date
    - previous_snapshot_date
    """

    if rating_row is None:
        return

    if isinstance(rating_row, pd.Series):
        row = rating_row.to_dict()
    else:
        row = dict(rating_row)

    stars = _safe_int(row.get("stars"))
    previous_stars = _safe_int(row.get("previous_stars"))
    rating_delta = _safe_int(row.get("rating_delta"), 0)
    status = row.get("rating_change_status") or "STABLE"

    config = _status_config(status)

    current_rating_html = rating_stars_html(stars) if stars is not None else "—"

    if previous_stars is None:
        change_text = f"текущий рейтинг: {stars}" if stars is not None else "нет рейтинга"
    else:
        sign = "+" if rating_delta and rating_delta > 0 else ""
        change_text = f"{previous_stars} → {stars}"
        if rating_delta:
            change_text += f" ({sign}{rating_delta})"

    previous_date = _format_date(row.get("previous_snapshot_date"))
    current_date = _format_date(row.get("snapshot_date"))

    if previous_stars is None:
        date_text = f"первая фиксация: {current_date}"
    else:
        date_text = f"{previous_date} → {current_date}"

    with ui.card().classes(
        f"w-full px-4 py-3 mb-4 border {config['border']} {config['bg']}"
    ):
        with ui.row().classes("w-full items-center justify-between gap-4"):
            with ui.row().classes("items-center gap-3"):
                ui.label(config["icon"]).classes(f"text-xl font-bold {config['color']}")
                ui.html(current_rating_html).classes("text-lg")
                ui.label(config["label"]).classes(f"text-sm font-semibold {config['color']}")

            with ui.row().classes("items-center gap-4"):
                ui.label(change_text).classes("text-sm font-medium text-gray-700")
                ui.label(date_text).classes("text-xs text-gray-500")

def render_portfolio_rating_strip(portfolio_row: dict | pd.Series | None):
    """
    Compact weighted portfolio rating strip for Parent Org / Branch cards.

    Expected fields:
    - weighted_rating
    - portfolio_change_status
    - portfolio_change_label
    - clients_total
    - clients_with_rating
    - clients_improved
    - clients_worsened
    - clients_stable
    - clients_new
    - snapshot_date
    - previous_snapshot_date
    """

    if portfolio_row is None:
        return

    if isinstance(portfolio_row, pd.Series):
        row = portfolio_row.to_dict()
    else:
        row = dict(portfolio_row)

    status = row.get("portfolio_change_status") or "STABLE"
    config = _status_config(status)

    weighted_rating = row.get("weighted_rating")
    if weighted_rating is None or pd.isna(weighted_rating):
        rating_text = "—"
    else:
        rating_text = (
            f"{portfolio_stars_html(weighted_rating)} "
            f"<span style='font-weight:700;'>{float(weighted_rating):.2f}</span>"
        )

    clients_total = _safe_int(row.get("clients_total"), 0) or 0
    clients_with_rating = _safe_int(row.get("clients_with_rating"), 0) or 0
    clients_improved = _safe_int(row.get("clients_improved"), 0) or 0
    clients_worsened = _safe_int(row.get("clients_worsened"), 0) or 0
    clients_stable = _safe_int(row.get("clients_stable"), 0) or 0
    clients_new = _safe_int(row.get("clients_new"), 0) or 0

    previous_date = _format_date(row.get("previous_snapshot_date"))
    current_date = _format_date(row.get("snapshot_date"))

    if row.get("previous_snapshot_date") is None or pd.isna(row.get("previous_snapshot_date")):
        date_text = f"первая фиксация: {current_date}"
    else:
        date_text = f"{previous_date} → {current_date}"

    with ui.card().classes(
        f"w-full px-4 py-3 mb-4 border {config['border']} {config['bg']}"
    ):
        with ui.row().classes("w-full items-center justify-between gap-4"):
            with ui.row().classes("items-center gap-3"):
                ui.label(config["icon"]).classes(f"text-xl font-bold {config['color']}")
                ui.label("Рейтинг портфеля").classes("text-sm text-gray-500")
                ui.html(rating_text).classes("text-lg")
                ui.label(row.get("portfolio_change_label") or config["label"]).classes(
                    f"text-sm font-semibold {config['color']}"
                )

            with ui.row().classes("items-center gap-4"):
                ui.label(f"клиентов: {clients_with_rating}/{clients_total}").classes(
                    "text-xs text-gray-500"
                )
                ui.label(f"↗ {clients_improved}").classes("text-xs text-green-600")
                ui.label(f"↘ {clients_worsened}").classes("text-xs text-red-600")
                ui.label(f"→ {clients_stable}").classes("text-xs text-gray-500")
                ui.label(f"● {clients_new}").classes("text-xs text-blue-600")
                ui.label(date_text).classes("text-xs text-gray-500")