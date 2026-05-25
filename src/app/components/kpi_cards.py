import pandas as pd
from nicegui import ui


def money(value) -> str:
    if pd.isna(value):
        return "0"
    return f"{float(value):,.0f}".replace(",", " ")


def percent(value) -> str:
    if pd.isna(value):
        return "0%"
    return f"{float(value):.1f}%"


def kpi_card(title: str, value: str, subtitle: str | None = None):
    with ui.card().classes("w-64 h-36 p-4"):
        with ui.column().classes("w-full h-full items-center justify-between text-center"):
            ui.label(title).classes("text-sm text-gray-500 h-6 flex items-center justify-center")
            ui.html(value).classes("text-2xl font-bold h-10 flex items-center justify-center")
            ui.label(subtitle or "").classes("text-sm text-gray-500 h-8 flex items-center justify-center")


def compact_kpi_card(title: str, value: str, subtitle: str | None = None):
    with ui.card().classes("w-44 h-20 p-2"):
        with ui.column().classes("w-full h-full items-center justify-between text-center"):
            ui.label(title).classes("text-xs text-gray-500")
            ui.html(value).classes("text-lg font-bold")
            ui.label(subtitle or "").classes("text-[10px] text-gray-500")