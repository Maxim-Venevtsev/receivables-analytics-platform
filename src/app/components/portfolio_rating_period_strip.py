import pandas as pd
from nicegui import ui

from src.app.components.rating_stars import rating_stars_html


def _safe_float(value, default: float = 0.0) -> float:
    if pd.isna(value):
        return default
    return float(value)


def _safe_int(value, default: int = 0) -> int:
    if pd.isna(value):
        return default
    return int(value)


def _date_fmt(value) -> str:
    if pd.isna(value):
        return ""
    return pd.to_datetime(value).strftime("%d.%m.%Y")


def _weighted_avg(df: pd.DataFrame, value_col: str, weight_col: str) -> float | None:
    if df.empty or value_col not in df.columns:
        return None

    values = pd.to_numeric(df[value_col], errors="coerce")
    weights = (
        pd.to_numeric(df[weight_col], errors="coerce").fillna(0)
        if weight_col in df.columns
        else pd.Series([1] * len(df), index=df.index)
    )

    mask = values.notna() & (weights > 0)

    if not mask.any():
        mask = values.notna()
        weights = pd.Series([1] * len(df), index=df.index)

    if not mask.any():
        return None

    return float((values[mask] * weights[mask]).sum() / weights[mask].sum())


def render_portfolio_rating_period_strip(
    migration_period_df: pd.DataFrame,
    period_label: str,
    fallback_rating: float | None = None,
):
    """Render one compact portfolio rating strip for a selected period.

    The strip combines two ideas:
    - portfolio rating level at the start/end of the selected period;
    - number of clients whose rating improved, worsened or stayed stable.
    """

    if migration_period_df is None or migration_period_df.empty:
        if fallback_rating is None:
            return

        fallback_rating = _safe_float(fallback_rating)
        fallback_stars = max(1, min(5, int(round(fallback_rating))))

        with ui.card().classes("w-full p-4 mb-6 bg-gray-50 border border-gray-200"):
            with ui.row().classes("items-center justify-between w-full gap-4"):
                with ui.row().classes("items-center gap-3"):
                    ui.label("→").classes("text-lg")
                    ui.label("Рейтинг портфеля").classes("text-sm text-gray-500")
                    ui.html(rating_stars_html(fallback_stars))
                    ui.label(f"{fallback_rating:.1f}").classes("font-bold")
                    ui.label("нет истории за выбранный период").classes("text-sm text-gray-500")
                ui.label(period_label).classes("text-xs text-gray-500")
        return

    df = migration_period_df.copy()

    start_rating = _weighted_avg(df, "start_stars", "current_total_debt")
    end_rating = _weighted_avg(df, "end_stars", "current_total_debt")

    if start_rating is None and fallback_rating is not None:
        start_rating = _safe_float(fallback_rating)
    if end_rating is None and fallback_rating is not None:
        end_rating = _safe_float(fallback_rating)

    if start_rating is None or end_rating is None:
        return

    start_stars = max(1, min(5, int(round(start_rating))))
    end_stars = max(1, min(5, int(round(end_rating))))

    delta = end_rating - start_rating

    if delta > 0.05:
        icon = "↗"
        color = "bg-green-50 border-green-200 text-green-800"
        label = f"Рейтинг улучшился: +{delta:.1f}"
    elif delta < -0.05:
        icon = "↘"
        color = "bg-red-50 border-red-200 text-red-800"
        label = f"Рейтинг ухудшился: {delta:.1f}"
    else:
        icon = "→"
        color = "bg-gray-50 border-gray-200 text-gray-800"
        label = "Рейтинг стабилен"

    start_date = _date_fmt(df["start_snapshot_date"].min()) if "start_snapshot_date" in df.columns else ""
    end_date = _date_fmt(df["end_snapshot_date"].max()) if "end_snapshot_date" in df.columns else ""

    count_df = df.copy()

    if "current_total_debt" in count_df.columns:
        count_df = count_df[
            pd.to_numeric(
                count_df["current_total_debt"],
                errors="coerce",
            ).fillna(0) > 0
        ]

    rating_delta = pd.to_numeric(
        count_df.get("rating_delta", 0),
        errors="coerce",
    ).fillna(0)

    improved = int((rating_delta > 0).sum())
    worsened = int((rating_delta < 0).sum())
    stable = int((rating_delta == 0).sum())
    total = int(count_df["client_id"].nunique()) if "client_id" in count_df.columns else len(count_df)

    with ui.card().classes(f"w-full p-4 mb-6 border {color}"):
        with ui.row().classes("items-center justify-between w-full gap-4"):
            with ui.row().classes("items-center gap-3"):
                ui.label(icon).classes("text-lg")
                ui.html(rating_stars_html(end_stars))
                ui.label(f"{start_rating:.1f} → {end_rating:.1f}").classes("font-bold")
                ui.label(label).classes("text-sm font-bold")
                ui.label(f"период: {period_label}").classes("text-sm text-gray-500")

            with ui.row().classes("items-center gap-2 text-xs"):
                ui.label(f"клиентов: {total}").classes("text-gray-500")
                ui.label("·").classes("text-gray-400")

                ui.label(f"↗ {improved}").classes("text-green-600")
                ui.label("·").classes("text-gray-400")

                ui.label(f"↘ {worsened}").classes("text-red-600")
                ui.label("·").classes("text-gray-400")

                ui.label(f"→ {stable}").classes("text-blue-600")
                ui.label("·").classes("text-gray-400")

                ui.label(f"{start_date} → {end_date}").classes("text-gray-500")
