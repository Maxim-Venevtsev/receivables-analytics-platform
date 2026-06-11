import pandas as pd
from nicegui import ui


def _safe_float(value, default: float = 0.0) -> float:
    if pd.isna(value):
        return default
    return float(value)


def _pct(value: float) -> str:
    return f"{value:.0f}%"


def _days(value) -> str:
    if pd.isna(value):
        return "—"
    return f"{int(round(float(value)))} дн."


def _calc_contract_term(df: pd.DataFrame) -> int | None:
    terms = df["payment_term_days"].dropna()

    if terms.empty:
        return None

    return int(terms.mode().iloc[0])


def get_payment_behavior_metrics(paid_invoices: pd.DataFrame) -> dict:
    if paid_invoices.empty:
        return {"has_data": False, "invoice_count": 0}

    df = paid_invoices.copy()

    df = df[
        df["actual_payment_term_days"].notna()
        & df["payment_term_days"].notna()
    ].copy()

    if df.empty:
        return {"has_data": False, "invoice_count": 0}

    invoice_count = len(df)

    contract_term = _calc_contract_term(df)

    q25 = df["actual_payment_term_days"].quantile(0.25)
    q75 = df["actual_payment_term_days"].quantile(0.75)

    avg_actual_term = df["actual_payment_term_days"].mean()
    median_actual_term = df["actual_payment_term_days"].median()

    paid_without_overdue_pct = (
        (df["days_vs_due_date"].fillna(0) <= 0).mean() * 100
    )

    paid_with_overdue_pct = (
        (df["days_vs_due_date"].fillna(0) > 0).mean() * 100
    )

    term_shift_pct = (
        (df["term_shift_count"].fillna(0) > 0).mean() * 100
    )

    repeated_shift_pct = (
        (df["term_shift_count"].fillna(0) >= 2).mean() * 100
    )

    avg_delay_days = df["days_vs_due_date"].fillna(0).mean()

    return {
        "has_data": True,
        "invoice_count": invoice_count,
        "contract_term": contract_term,
        "usual_from": q25,
        "usual_to": q75,
        "avg_actual_term": avg_actual_term,
        "median_actual_term": median_actual_term,
        "paid_without_overdue_pct": paid_without_overdue_pct,
        "paid_with_overdue_pct": paid_with_overdue_pct,
        "term_shift_pct": term_shift_pct,
        "repeated_shift_pct": repeated_shift_pct,
        "avg_delay_days": avg_delay_days,
    }


def _behavior_status(metrics: dict) -> tuple[str, str, str]:
    without_overdue = _safe_float(metrics.get("paid_without_overdue_pct"))
    repeated = _safe_float(metrics.get("repeated_shift_pct"))
    shifts = _safe_float(metrics.get("term_shift_pct"))
    avg_delay = _safe_float(metrics.get("avg_delay_days"))

    if without_overdue >= 80 and repeated < 10 and avg_delay <= 1:
        return "🟢", "Стабильное платежное поведение", "bg-green-50 border-green-200 text-green-800"

    if without_overdue >= 60 and repeated < 20 and avg_delay <= 5:
        return "🟡", "Платежное поведение под контролем", "bg-yellow-50 border-yellow-200 text-yellow-800"

    if shifts >= 30 or repeated >= 20 or avg_delay > 5:
        return "🟠", "Есть признаки напряжения платежей", "bg-orange-50 border-orange-200 text-orange-800"

    return "🔵", "Платежное поведение требует наблюдения", "bg-blue-50 border-blue-200 text-blue-800"


def render_payment_behavior_strip(paid_invoices: pd.DataFrame):
    metrics = get_payment_behavior_metrics(paid_invoices)

    if not metrics.get("has_data"):
        with ui.card().classes("w-full p-4 mb-6 bg-gray-50 border border-gray-200"):
            ui.label("Фактическое платежное поведение").classes("font-bold text-base")
            ui.label(
                "Недостаточно данных по оплаченным накладным для расчета профиля."
            ).classes("text-sm text-gray-500")
        return

    icon, title, color = _behavior_status(metrics)

    with ui.card().classes(f"w-full p-4 mb-6 border {color}"):
        with ui.row().classes("items-start justify-between w-full gap-4"):
            with ui.column().classes("gap-2"):
                with ui.row().classes("items-center gap-3"):
                    ui.label(icon).classes("text-xl")
                    ui.label("Фактическое платежное поведение").classes("font-bold text-base")
                    ui.label(title).classes("text-sm font-bold")
                    with ui.icon("info_outline").classes("text-gray-500 cursor-help"):
                        ui.tooltip(
                            "Профиль рассчитан по последним оплаченным накладным клиента. "
                            "Без просрочки - оплачено не позже актуального срока оплаты. "
                            "С переносами - срок оплаты по накладной менялся хотя бы один раз. "
                            "Обычный интервал оплаты - диапазон, в котором находится большинство фактических сроков оплаты клиента."
                        )

                ui.label(
                    f"Основано на {metrics['invoice_count']} последних оплаченных накладных"
                ).classes("text-xs text-gray-500")

                ui.label(
                    f"Контрактная отсрочка: {_days(metrics.get('contract_term'))}"
                ).classes("text-sm")

                ui.label(
                    "Обычно платит в интервале: "
                    f"{_days(metrics.get('usual_from'))} – {_days(metrics.get('usual_to'))}"
                ).classes("text-sm")

                ui.label(
                    f"Средний фактический срок оплаты: {_days(metrics.get('avg_actual_term'))} "
                    f"(медиана: {_days(metrics.get('median_actual_term'))})"
                ).classes("text-sm")

            with ui.row().classes("gap-4"):
                with ui.column().classes("items-center"):
                    ui.label(_pct(metrics["paid_without_overdue_pct"])).classes("text-2xl font-bold")
                    ui.label("без просрочки").classes("text-xs")

                with ui.column().classes("items-center"):
                    ui.label(_pct(metrics["paid_with_overdue_pct"])).classes("text-2xl font-bold")
                    ui.label("с просрочкой").classes("text-xs")

                with ui.column().classes("items-center"):
                    ui.label(_pct(metrics["term_shift_pct"])).classes("text-2xl font-bold")
                    ui.label("с переносами").classes("text-xs")

                with ui.column().classes("items-center"):
                    ui.label(_pct(metrics["repeated_shift_pct"])).classes("text-2xl font-bold")
                    ui.label("повторные переносы").classes("text-xs")