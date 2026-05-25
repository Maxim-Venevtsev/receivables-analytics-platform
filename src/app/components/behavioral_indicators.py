import pandas as pd


def _safe_pct_change(start_value: float, end_value: float) -> float:
    if start_value == 0:
        return 0.0
    return (end_value - start_value) / start_value * 100


def get_debt_trend_indicator(history_df: pd.DataFrame) -> dict:
    """
    Debt trend based on avg(first 7 snapshots) vs avg(last 7 snapshots).
    Falls back gracefully when history is short.
    """

    if history_df.empty or len(history_df) < 2:
        return {
            "icon": "→",
            "label": "Недостаточно истории",
            "color": "gray",
        }

    df = history_df.sort_values("report_generated_date").copy()

    window = 7 if len(df) >= 14 else max(1, len(df) // 2)

    start_avg = float(df.head(window)["total_debt"].mean())
    end_avg = float(df.tail(window)["total_debt"].mean())

    change_pct = _safe_pct_change(start_avg, end_avg)

    if change_pct > 15:
        return {
            "icon": "↗",
            "label": "Долг растет",
            "color": "red",
            "detail": f"+{change_pct:.1f}%",
        }

    if change_pct < -15:
        return {
            "icon": "↘",
            "label": "Долг снижается",
            "color": "green",
            "detail": f"{change_pct:.1f}%",
        }

    return {
        "icon": "→",
        "label": "Долг стабилен",
        "color": "blue",
        "detail": f"{change_pct:+.1f}%",
    }

def get_overdue_behavior_indicator(history_df: pd.DataFrame) -> dict:
    """
    Overdue behavior based on overdue occurrence frequency.
    """

    if history_df.empty:
        return {
            "icon": "→",
            "label": "Нет данных по просрочке",
            "color": "gray",
        }

    history_days = int(history_df["report_generated_date"].nunique())

    if history_days == 0:
        return {
            "icon": "→",
            "label": "Нет данных по просрочке",
            "color": "gray",
        }

    overdue_days = int((history_df["overdue_debt"] > 0).sum())

    overdue_ratio = overdue_days / history_days * 100

    if overdue_ratio == 0:
        return {
            "icon": "✓",
            "label": "Просрочка отсутствует",
            "color": "green",
            "detail": "0%",
        }

    if overdue_ratio <= 20:
        return {
            "icon": "⚠",
            "label": "Эпизодическая просрочка",
            "color": "orange",
            "detail": f"{overdue_ratio:.1f}%",
        }

    return {
        "icon": "⚠",
        "label": "Регулярная просрочка",
        "color": "red",
        "detail": f"{overdue_ratio:.1f}%",
    }
def get_volatility_indicator(history_df: pd.DataFrame) -> dict:
    """
    Behavioral stability based on coefficient of variation:
    std(total_debt) / mean(total_debt).
    """

    if history_df.empty or len(history_df) < 2:
        return {
            "icon": "→",
            "label": "Недостаточно истории",
            "color": "gray",
        }

    mean_debt = float(history_df["total_debt"].mean())
    std_debt = float(history_df["total_debt"].std())

    if mean_debt == 0:
        return {
            "icon": "→",
            "label": "Нет задолженности",
            "color": "gray",
            "detail": "0%",
        }

    volatility_pct = std_debt / mean_debt * 100

    if volatility_pct < 15:
        return {
            "icon": "✓",
            "label": "Поведение стабильное",
            "color": "green",
            "detail": f"{volatility_pct:.1f}%",
        }

    if volatility_pct <= 35:
        return {
            "icon": "→",
            "label": "Умеренная волатильность",
            "color": "orange",
            "detail": f"{volatility_pct:.1f}%",
        }

    return {
        "icon": "⚠",
        "label": "Высокая волатильность",
        "color": "red",
        "detail": f"{volatility_pct:.1f}%",
    }