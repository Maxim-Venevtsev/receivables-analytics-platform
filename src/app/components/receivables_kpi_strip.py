from nicegui import ui


def receivables_kpi_card(
    title: str,
    value: str,
    subtitle: str = "",
    value_color_class: str = "text-gray-900",
):
    with ui.card().classes("w-64 h-36 p-4"):
        with ui.column().classes("w-full h-full items-center justify-between text-center"):
            ui.label(title).classes("text-sm text-gray-500 h-6 flex items-center justify-center")
            ui.label(value).classes(
                f"text-2xl font-bold h-10 flex items-center justify-center {value_color_class}"
            )
            ui.label(subtitle).classes("text-sm text-gray-500 h-8 flex items-center justify-center")


def render_receivables_kpi_strip(
    total_debt: str,
    overdue_debt: str,
    overdue_share: str,
    due_today: str,
    due_today_share: str,
    due_soon: str,
    due_soon_share: str,
    shifted_amount: str,
    shifted_share: str,
):
    with ui.row().classes("gap-4 mb-6"):
        receivables_kpi_card(
            "Общий долг",
            total_debt,
            "",
            "text-gray-900",
        )
        receivables_kpi_card(
            "Просрочено",
            overdue_debt,
            overdue_share,
            "text-red-700",
        )
        receivables_kpi_card(
            "К оплате сегодня",
            due_today,
            due_today_share,
            "text-orange-600",
        )
        receivables_kpi_card(
            "Ближайшие 3 дня",
            due_soon,
            due_soon_share,
            "text-yellow-600",
        )
        receivables_kpi_card(
            "Переносы",
            shifted_amount,
            shifted_share,
            "text-blue-700",
        )
