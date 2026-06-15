import pandas as pd
from nicegui import ui

from src.app.components.rating_stars import rating_stars_html


def _safe_int(value, default: int = 0) -> int:
    if pd.isna(value):
        return default
    return int(value)


def _safe_float(value, default: float = 0.0) -> float:
    if pd.isna(value):
        return default
    return float(value)


def _money(value) -> str:
    if pd.isna(value):
        return "0"
    return f"{float(value):,.0f}".replace(",", " ")


def _severity_style(level: str) -> tuple[str, str]:
    if level == "CRITICAL":
        return "🔴", "bg-red-50 border-red-200 text-red-800"
    if level == "HIGH":
        return "🟠", "bg-orange-50 border-orange-200 text-orange-800"
    if level == "MEDIUM":
        return "🟡", "bg-yellow-50 border-yellow-200 text-yellow-800"
    if level == "LOW":
        return "🔵", "bg-blue-50 border-blue-200 text-blue-800"
    return "🟢", "bg-green-50 border-green-200 text-green-800"


def render_credit_quality_strip(row: pd.Series):
    base_stars = _safe_int(row.get("base_stars"))
    credit_quality_stars = _safe_int(row.get("credit_quality_stars"))

    severity_level = str(row.get("severity_level") or "NONE")
    severity_penalty = _safe_float(row.get("severity_penalty"))
    severity_reasons = row.get("severity_reasons")

    total_debt = _safe_float(row.get("total_debt"))
    weighted_avg_payment_term_days = _safe_float(row.get("weighted_avg_payment_term_days"))
    max_payment_term_days = _safe_int(row.get("max_payment_term_days"))
    term_shift_count = _safe_int(row.get("term_shift_count"))
    repeated_shift_invoice_count = _safe_int(row.get("repeated_shift_invoice_count"))
    green_90_plus_share_pct = _safe_float(row.get("green_90_plus_share_pct"))
    green_120_plus_debt = _safe_float(row.get("green_120_plus_debt"))

    icon, color = _severity_style(severity_level)

    if isinstance(severity_reasons, str):
        reasons = severity_reasons.strip("{}").split(",") if severity_reasons else []
    elif isinstance(severity_reasons, (list, tuple)):
        reasons = list(severity_reasons)
    else:
        reasons = []

    reasons = [str(r).strip().strip('"') for r in reasons if str(r).strip()]

    rating_changed = credit_quality_stars < base_stars

    with ui.card().classes(f"w-full p-4 mb-6 border {color}"):
        with ui.row().classes("items-start justify-between w-full gap-4"):
            with ui.column().classes("gap-2"):
                with ui.row().classes("items-center gap-3"):
                    ui.label(icon).classes("text-xl")
                    ui.label("Кредитное качество").classes("font-bold text-base")
                    ui.html(rating_stars_html(credit_quality_stars))

                    if rating_changed:
                        ui.label(
                            f"базовый рейтинг: {base_stars}★ → итоговый: {credit_quality_stars}★"
                        ).classes("text-sm font-bold")
                    else:
                        ui.label(
                            f"базовый рейтинг: {base_stars}★"
                        ).classes("text-sm font-bold")

                ui.label(
                    f"Severity: {severity_level} · штраф: {severity_penalty:g}"
                ).classes("text-sm")

                if reasons:
                    ui.label("Причины: " + "; ".join(reasons)).classes("text-sm")
                else:
                    ui.label("Дополнительных severity-сигналов нет.").classes("text-sm")

            with ui.column().classes("items-end gap-1 text-sm"):
                ui.label(f"Средняя отсрочка: {weighted_avg_payment_term_days:.1f} дн.")
                ui.label(f"Макс. отсрочка: {max_payment_term_days} дн.")
                ui.label(f"90+ дней непросроченный долг: {green_90_plus_share_pct:.1f}%")
                ui.label(f"120+ дней непросроченный долг: {_money(green_120_plus_debt)}")
                ui.label(f"Переносы: {term_shift_count}")
                ui.label(f"Повторные переносы: {repeated_shift_invoice_count}")