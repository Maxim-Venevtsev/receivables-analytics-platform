from nicegui import ui


def top_navigation():
    with ui.row().classes("mb-4"):

        ui.button("📊 ГЛАВНАЯ", on_click=lambda: ui.navigate.to("/")).props("flat color=primary")

        ui.button("📈 ДИНАМИКА", on_click=lambda: ui.navigate.to("/deltas")).props("flat color=primary")

        ui.button("🔴 ПРОСРОЧЕНО", on_click=lambda: ui.navigate.to("/overdue")).props("flat color=negative")

        ui.button("🟠 К ОПЛАТЕ СЕГОДНЯ", on_click=lambda: ui.navigate.to("/due-today")).props("flat color=warning")

        ui.button("🟡 БЛИЖАЙШИЕ ТРИ ДНЯ", on_click=lambda: ui.navigate.to("/due-soon")).props("flat color=warning")

        ui.button("🟨 ОЖИДАНИЕ ОПЛАТЫ", on_click=lambda: ui.navigate.to("/payment-attention")).props("flat color=warning")

        ui.button("🟧 ПЕРЕНОСЫ", on_click=lambda: ui.navigate.to("/term-shifts")).props("flat color=warning")

        ui.button("🏛️ СВОДКА", on_click=lambda: ui.navigate.to("/executive")).props("flat color=primary")