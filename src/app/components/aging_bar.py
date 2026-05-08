from nicegui import ui


def money(value) -> str:
    if value is None:
        return "0"
    return f"{float(value):,.0f}".replace(",", " ")


def receivables_structure_bar(
    normal_amount: float,
    due_soon_amount: float,
    due_today_amount: float,
    overdue_amount: float,
):
    total = normal_amount + due_soon_amount + due_today_amount + overdue_amount

    if total <= 0:
        return

    segments = [
        ("В обычном режиме", normal_amount, "#22c55e"),
        ("Ближайшие 3 дня", due_soon_amount, "#fde68a"),
        ("К оплате сегодня", due_today_amount, "#f59e0b"),
        ("Просрочено", overdue_amount, "#ef4444"),
    ]

    with ui.card().classes("w-full p-4 mb-6"):
        ui.label("Структура задолженности").classes("text-sm text-gray-500 mb-3")

        with ui.element("div").classes("w-full h-6 rounded-full overflow-hidden flex bg-gray-100"):
            for _, amount, color in segments:
                if amount <= 0:
                    continue

                width = amount / total * 100

                ui.element("div").style(
                    f"width: {width}%; background-color: {color}; height: 100%;"
                )

        with ui.row().classes("w-full justify-between mt-3"):
            for label, amount, color in segments:
                if amount <= 0:
                    continue

                share = amount / total * 100

                with ui.row().classes("items-center gap-2"):
                    ui.element("div").classes("w-3 h-3 rounded-full").style(
                        f"background-color: {color};"
                    )
                    ui.label(
                        f"{label}: {money(amount)} · {share:.1f}%"
                    ).classes("text-xs text-gray-600")