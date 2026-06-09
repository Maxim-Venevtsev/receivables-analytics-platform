from pathlib import Path
import os

import pandas as pd
from dotenv import load_dotenv
from nicegui import ui
from sqlalchemy import create_engine, text

from src.app.components.navigation import top_navigation
from src.app.components.kpi_cards import money, percent
from src.app.components.charts import (
    build_portfolio_debt_history_chart,
    build_portfolio_debt_structure_chart,
    build_debt_quality_chart,
    build_green_debt_maturity_chart,
    build_weighted_payment_term_chart,
    build_long_green_exposure_chart,
    build_rating_exposure_chart,
    build_rating_migration_chart,
    build_client_risk_bubble_chart,
    build_top_client_risk_bubble_chart,
    build_hidden_risk_bubble_chart,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env")

engine = create_engine(
    f"postgresql+psycopg2://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@"
    f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)


def query_df(sql: str, params: dict | None = None) -> pd.DataFrame:
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn, params=params)


def rating_text(value) -> str:
    if pd.isna(value):
        return "—"
    return f"{round(float(value), 1):.1f} / 5"


def compact_kpi(
    title: str,
    value: str,
    subtitle: str = "",
    color_class: str = "text-gray-900",
):
    with ui.card().classes("w-64 h-36 p-4"):
        with ui.column().classes("w-full h-full items-center justify-between text-center"):
            ui.label(title).classes("text-sm text-gray-500 h-6 flex items-center justify-center")
            ui.label(value).classes(
                f"text-2xl font-bold h-10 flex items-center justify-center {color_class}"
            )
            ui.label(subtitle).classes("text-sm text-gray-500 h-8 flex items-center justify-center")


def section_title(title: str, subtitle: str):
    ui.label(title).classes("text-2xl font-bold mt-6 mb-1")
    ui.label(subtitle).classes("text-sm text-gray-500 mb-3")


def chart_card(title: str, subtitle: str, chart):
    with ui.card().classes("w-full p-4 mb-6"):
        ui.label(title).classes("text-xl font-bold mb-1")
        ui.label(subtitle).classes("text-sm text-gray-500 mb-3")
        ui.plotly(chart).classes("w-full")


def render_executive_verdict(kpi: pd.Series):
    overdue_share = float(kpi["overdue_share_pct"] or 0)
    green_90_share = float(kpi["green_90_plus_share_of_portfolio_pct"] or 0)
    green_90_debt = float(kpi["green_90_plus_debt"] or 0)
    green_120_debt = float(kpi["green_120_plus_debt"] or 0)

    if overdue_share >= 20 or green_90_share >= 10 or green_120_debt > 0:
        status = "ТРЕБУЕТСЯ КОНТРОЛЬ"
        icon = "🟠"
        color = "bg-orange-50 border-orange-200 text-orange-800"
        message = (
            "Портфель требует управленческого внимания из-за просрочки "
            "и/или длинной непросроченной задолженности."
        )
    elif overdue_share >= 10 or green_90_share >= 5:
        status = "ЗОНА НАБЛЮДЕНИЯ"
        icon = "🟡"
        color = "bg-yellow-50 border-yellow-200 text-yellow-800"
        message = "Ситуация в целом управляема, но есть ранние признаки ухудшения качества портфеля."
    else:
        status = "СТАБИЛЬНО"
        icon = "🟢"
        color = "bg-green-50 border-green-200 text-green-800"
        message = "Портфель выглядит стабильным по текущим показателям просрочки и качества непросроченного долга."

    with ui.card().classes(f"w-full p-5 mb-6 border {color}"):
        with ui.row().classes("items-center justify-between w-full"):
            with ui.column().classes("gap-1"):
                ui.label(f"{icon} Статус портфеля: {status}").classes("text-2xl font-bold")
                ui.label(message).classes("text-sm")

            with ui.row().classes("gap-6"):
                with ui.column().classes("items-center"):
                    ui.label(percent(overdue_share)).classes("text-xl font-bold")
                    ui.label("Доля просрочки").classes("text-xs")

                with ui.column().classes("items-center"):
                    ui.label(percent(green_90_share)).classes("text-xl font-bold")
                    ui.label("Доля 90+ непросрочено").classes("text-xs")

                with ui.column().classes("items-center"):
                    ui.label(money(green_90_debt)).classes("text-xl font-bold")
                    ui.label("90+ непросрочено").classes("text-xs")

                with ui.column().classes("items-center"):
                    ui.label(money(green_120_debt)).classes("text-xl font-bold")
                    ui.label("120+ непросрочено").classes("text-xs")


def render_signal_card(icon: str, title: str, detail: str, route: str):
    with ui.card().classes("w-full p-4 mb-3 bg-gray-50"):
        with ui.row().classes("items-center justify-between w-full gap-4"):
            with ui.row().classes("items-start gap-3"):
                ui.label(icon).classes("text-xl")
                with ui.column().classes("gap-0"):
                    ui.label(title).classes("font-bold")
                    ui.label(detail).classes("text-sm text-gray-600")

            ui.button(
                "Открыть",
                on_click=lambda route=route: ui.navigate.to(route),
            ).props("outline color=primary")


def render_management_signals(
    kpi: pd.Series,
    branch_health: pd.DataFrame,
    hidden_risk: pd.DataFrame,
    term_shift_kpi: pd.DataFrame,
):
    ui.label("Управленческие сигналы").classes("text-2xl font-bold mt-6 mb-1")
    ui.label(
        "Карточки ведут на детальные страницы с табличной расшифровкой. "
        "Сами страницы добавим следующим шагом."
    ).classes("text-sm text-gray-500 mb-3")

    green_90 = float(kpi["green_90_plus_debt"] or 0)
    green_90_pct = float(kpi["green_90_plus_share_of_portfolio_pct"] or 0)
    overdue = float(kpi["overdue_debt"] or 0)
    overdue_pct = float(kpi["overdue_share_pct"] or 0)

    if green_90 > 0:
        render_signal_card(
            "🔴",
            "Обнаружена длинная непросроченная задолженность",
            f"90+ непросрочено: {money(green_90)} · {percent(green_90_pct)} портфеля",
            "/executive/long-green",
        )

    if overdue > 0:
        render_signal_card(
            "🔴",
            "Есть просроченная задолженность",
            f"Просрочено: {money(overdue)} · {percent(overdue_pct)} портфеля",
            "/executive/overdue",
        )

    if not hidden_risk.empty:
        top = hidden_risk.iloc[0]
        render_signal_card(
            "🟠",
            "Скрытый риск: аномально длинные отсрочки",
            f"{top['client_name']} · максимум отсрочки: {int(top['max_payment_term_days'])} дней",
            "/executive/hidden-risk",
        )

    if not branch_health.empty:
        worst = branch_health.iloc[0]
        render_signal_card(
            "🟡",
            "Филиал с худшим риск-профилем",
            f"{worst['client_group']} · просрочка {percent(worst['overdue_share_pct'])}, "
            f"90+ непросрочено {percent(worst['green_90_plus_share_pct'])}",
            "/executive/branches",
        )

    if not term_shift_kpi.empty:
        shift = term_shift_kpi.iloc[0]

        clients_with_shifts = int(shift["clients_with_term_shifts"] or 0)
        events = int(shift["term_shift_events_count"] or 0)
        shifted_amount = float(shift["shifted_amount"] or 0)

        if clients_with_shifts > 0:
            render_signal_card(
                "🟠",
                "Обнаружены повторные переносы сроков оплаты",
                f"{clients_with_shifts} клиентов · "
                f"{events} событий · "
                f"{money(shifted_amount)}",
                "/executive/term-shifts",
            )

    if green_90 <= 0 and overdue <= 0 and hidden_risk.empty and branch_health.empty:
        render_signal_card(
            "🟢",
            "Существенных сигналов нет",
            "Портфель выглядит стабильным.",
            "/executive",
        )


@ui.page("/executive")
def executive_overview_page():
    ui.label("Сводка для руководителя").classes("text-3xl font-bold mb-2")
    ui.label("Общее состояние портфеля дебиторской задолженности").classes("text-gray-500 mb-4")

    top_navigation()

    kpi_df = query_df("SELECT * FROM core.v_executive_overview_kpi")

    portfolio_history = query_df("""
        SELECT *
        FROM core.v_executive_portfolio_daily_history
        ORDER BY report_generated_date
    """)

    maturity_history = query_df("""
        SELECT *
        FROM core.v_executive_green_debt_maturity_history
        ORDER BY report_generated_date, maturity_bucket
    """)

    payment_term_history = query_df("""
        SELECT *
        FROM core.v_executive_payment_term_history
        ORDER BY report_generated_date
    """)

    long_green_history = query_df("""
        SELECT *
        FROM core.v_executive_long_green_exposure
        ORDER BY report_generated_date
    """)

    rating_exposure = query_df("""
        SELECT *
        FROM core.v_executive_rating_exposure
        ORDER BY stars NULLS LAST
    """)

    rating_migration = query_df("""
        SELECT *
        FROM core.v_executive_rating_migration_summary
        ORDER BY sort_order
    """)

    client_risk_bubble = query_df("""
        SELECT *
        FROM core.v_executive_client_risk_bubble
        ORDER BY bubble_size DESC
    """)
    
    hidden_risk_bubble = query_df("""
        SELECT *
        FROM core.v_executive_hidden_risk_bubble
        ORDER BY bubble_size DESC
    """)

    branch_health = query_df("""
        SELECT *
        FROM core.v_executive_branch_health
        ORDER BY overdue_share_pct DESC, green_90_plus_share_pct DESC
    """)

    hidden_risk = query_df("""
        SELECT *
        FROM core.v_executive_hidden_risk_clients
        ORDER BY green_120_plus_debt DESC, green_90_plus_debt DESC, max_payment_term_days DESC
    """)

    term_shift_kpi = query_df("""
        SELECT *
        FROM core.v_executive_term_shift_kpi
    """)

    if kpi_df.empty:
        ui.label("Нет данных для сводки руководителя.").classes("text-lg text-red-700")
        return

    kpi = kpi_df.iloc[0]

    total_portfolio_debt = float(kpi["total_debt"] or 0)

    top20_debt = (
        client_risk_bubble
        .nlargest(20, "bubble_size")["bubble_size"]
        .sum()
    )

    top20_share_pct = (
        top20_debt / total_portfolio_debt * 100
        if total_portfolio_debt > 0
        else 0
    )

    with ui.row().classes("gap-4 mb-6"):
        compact_kpi(
            "Общая дебиторка",
            money(kpi["total_debt"]),
            f"срез: {kpi['latest_snapshot_date']}",
        )
        compact_kpi(
            "Просрочено",
            money(kpi["overdue_debt"]),
            f"{percent(kpi['overdue_share_pct'])} портфеля",
            "text-red-600",
        )
        compact_kpi(
            "К оплате сегодня",
            money(kpi["due_today"]),
            "операционный контроль",
            "text-orange-600",
        )
        compact_kpi(
            "90+ непросрочено",
            money(kpi["green_90_plus_debt"]),
            f"{percent(kpi['green_90_plus_share_of_portfolio_pct'])} портфеля",
            "text-red-600",
        )
        compact_kpi(
            "120+ непросрочено",
            money(kpi["green_120_plus_debt"]),
            "длинная отсрочка",
            "text-red-700",
        )
        compact_kpi(
            "Рейтинг портфеля",
            rating_text(kpi["weighted_portfolio_rating"]),
            "взвешено по сумме долга",
            "text-blue-700",
        )

    render_executive_verdict(kpi)

    section_title(
        "Структура портфеля",
        "Как меняется общий долг, просрочка, операционные сроки оплаты и качество задолженности.",
    )

    chart_card(
        "Общая динамика задолженности",
        "Общий долг и просроченная задолженность по дням.",
        build_portfolio_debt_history_chart(portfolio_history),
    )

    chart_card(
        "Структура задолженности по дням",
        "Не просрочено, к оплате в ближайшие дни, к оплате сегодня и просрочено.",
        build_portfolio_debt_structure_chart(portfolio_history),
    )

    chart_card(
        "Надежная задолженность и задолженность, требующая контроля",
        "Надежная задолженность: рейтинг 4–5 звезд, нет просрочки, отсрочка до 45 дней включительно.",
        build_debt_quality_chart(portfolio_history),
    )

    section_title(
        "Качество отсрочек",
        "Контроль скрытых рисков внутри формально непросроченной задолженности.",
    )

    chart_card(
        "Структура непросроченной задолженности по срокам отсрочки",
        "Показывает концентрацию непросроченного долга в коротких и длинных отсрочках.",
        build_green_debt_maturity_chart(maturity_history),
    )

    chart_card(
        "Средневзвешенная отсрочка по портфелю",
        "Динамика средней отсрочки в днях, взвешенной по сумме задолженности.",
        build_weighted_payment_term_chart(payment_term_history),
    )

    chart_card(
        "Длинная непросроченная задолженность",
        "История непросроченного долга с отсрочкой 90+ и 120+ дней.",
        build_long_green_exposure_chart(long_green_history),
    )

    section_title(
        "Качество клиентов",
        "Распределение задолженности по рейтинговым сегментам клиентов.",
    )

    chart_card(
        "Экспозиция по рейтинговым сегментам",
        "Сколько денег находится в каждом рейтинговом сегменте и какая часть из них уже просрочена.",
        build_rating_exposure_chart(rating_exposure),
    )

    section_title(
        "Миграция рейтингов",
        "Изменение рейтингов клиентов за последние 28 дней.",
    )

    if not rating_migration.empty:

        migration_28 = rating_migration[
            rating_migration["period_label"] == "28 дней"
        ]

        if not migration_28.empty:

            migration = migration_28.iloc[0]

            with ui.row().classes("gap-4 mb-6"):

                compact_kpi(
                    "Улучшились",
                    str(int(migration["upgraded_clients"])),
                    "рост рейтинга",
                    "text-green-600",
                )

                compact_kpi(
                    "Ухудшились",
                    str(int(migration["downgraded_clients"])),
                    "снижение рейтинга",
                    "text-red-600",
                )

                compact_kpi(
                    "Без изменений",
                    str(int(migration["unchanged_clients"])),
                    "стабильные клиенты",
                )

                compact_kpi(
                    "Чистая миграция",
                    f"{int(migration['net_migration_clients']):+d}",
                    "улучшились − ухудшились",
                    (
                        "text-green-600"
                        if migration["net_migration_clients"] >= 0
                        else "text-red-600"
                    ),
                )

                compact_kpi(
                    "Новые в рейтинге",
                    str(int(migration["new_clients"])),
                    "новые клиенты",
                    "text-blue-600",
                )

        with ui.row().classes("mb-4"):
            ui.button(
                "Открыть изменения рейтингов",
                on_click=lambda: ui.navigate.to("/executive/rating-migration"),
            ).props("outline color=primary")

        chart_card(
            "Миграция рейтингов по периодам",
            "Сравнение рейтингов на начало и конец периода.",
            build_rating_migration_chart(rating_migration),
        )

    section_title(
        "Карта клиентского риска",
        "Визуальная карта крупных клиентов, отсрочек, рейтингов и скрытого риска.",
    )

    chart_card(
        "Рейтинг × отсрочка × сумма долга",
        "X — средневзвешенная отсрочка, Y — рейтинг клиента, размер пузыря — сумма долга, цвет — уровень просрочки.",
        build_client_risk_bubble_chart(client_risk_bubble),
    )

    chart_card(
        "TOP-20 крупнейших клиентов",
        (
            f"{money(top20_debt)} руб "
            f"({top20_share_pct:.1f}% общей дебиторской задолженности)"
        ),
    build_top_client_risk_bubble_chart(client_risk_bubble),
    )

    chart_card(
        "Рейтинг × длинная непросроченная задолженность",
        "X — доля 90+ непросроченной задолженности, Y — рейтинг клиента, размер пузыря — сумма долга, цвет — уровень скрытого риска.",
        build_hidden_risk_bubble_chart(hidden_risk_bubble),
    )
    
    render_management_signals(
        kpi=kpi,
        branch_health=branch_health,
        hidden_risk=hidden_risk,
        term_shift_kpi=term_shift_kpi,
    )
