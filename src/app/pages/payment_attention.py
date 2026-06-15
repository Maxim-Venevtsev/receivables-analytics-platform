from pathlib import Path
import os
from urllib.parse import quote

import pandas as pd
from dotenv import load_dotenv
from nicegui import ui
from sqlalchemy import create_engine, text

from src.app.components.navigation import top_navigation
from src.app.components.kpi_cards import money
from src.app.components.rating_stars import rating_stars_html
from src.app.components.clients_table import render_clients_table


PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env")

engine = create_engine(
    f"postgresql+psycopg2://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@"
    f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)


def query_df(sql: str, params: dict | None = None) -> pd.DataFrame:
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn, params=params)


def money_precise(value) -> str:
    if pd.isna(value):
        return "0,00"
    return f"{float(value):,.2f}".replace(",", " ").replace(".", ",")


def compact_kpi(title: str, value: str, subtitle: str = "", color_class: str = "text-gray-900"):
    with ui.card().classes("w-60 h-32 p-4"):
        with ui.column().classes("w-full h-full items-center justify-between text-center"):
            ui.label(title).classes("text-sm text-gray-500 h-6 flex items-center justify-center")
            ui.label(value).classes(f"text-2xl font-bold h-10 flex items-center justify-center {color_class}")
            ui.label(subtitle).classes("text-sm text-gray-500 h-8 flex items-center justify-center")


def table_page_props() -> str:
    return 'rows-per-page-options="[20, 50, 100]"'


def prepare_money_cols(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    result = df.copy()
    for col in cols:
        if col in result.columns:
            result[f"{col}_fmt"] = result[col].apply(money_precise)
    return result


def add_branch_summary_slots(table):
    table.add_slot(
        "body-cell-client_group",
        """
        <q-td :props="props" :style="props.row.is_dimmed ? 'opacity:0.45;' : ''">
            <q-btn
                dense
                :flat="!props.row.is_selected"
                :unelevated="props.row.is_selected"
                :outline="!props.row.is_selected"
                :color="props.row.is_selected ? 'primary' : 'grey-7'"
                :label="props.row.client_group"
                @click="$parent.$emit('branch_click', props.row.client_group)"
            />
        </q-td>
        """,
    )

    table.add_slot(
        "body-cell-rating",
        """
        <q-td :props="props" class="text-center" :style="props.row.is_dimmed ? 'opacity:0.45;' : ''">
            {{ props.row.weighted_rating_fmt }}
        </q-td>
        """,
    )

    for col in [
        "amount_in_window",
        "amount_out_of_window",
        "amount_shift_once",
        "amount_shift_repeated",
        "clients_to_control",
    ]:
        table.add_slot(
            f"body-cell-{col}",
            f"""
            <q-td :props="props" class="text-right" :style="props.row.is_dimmed ? 'opacity:0.45;' : ''">
                {{{{ props.row.{col}_fmt || props.row.{col} }}}}
            </q-td>
            """,
        )


def add_client_summary_slot(table):
    table.add_slot(
        "body",
        r"""
        <q-tr
            :props="props"
            :class="{
                'bg-orange-1': props.row.row_color === 'today',
                'bg-yellow-1': props.row.row_color === 'soon'
            }"
        >
            <q-td v-for="col in props.cols" :key="col.name" :props="props">

                <template v-if="col.name === 'client'">
                    <a
                        :href="props.row.client_url"
                        class="text-blue-600 hover:underline font-medium"
                    >
                        {{ props.row.client_display }}
                    </a>
                </template>

                <template v-else-if="col.name === 'rating'">
                    <span v-html="props.row.rating_html"></span>
                </template>

                <template v-else>
                    {{ col.value }}
                </template>

            </q-td>
        </q-tr>
        """,
    )

@ui.page("/payment-attention")
def payment_attention_page():

    ui.label("Ожидание оплаты").classes("text-3xl font-bold mb-2")

    ui.label(
        "Клиенты с непросроченными накладными, которые уже вошли в обычное платежное окно, "
        "вышли из него или имеют переносы срока оплаты."
    ).classes("text-subtitle1 text-grey-7 mb-4")

    top_navigation()

    clients_df = query_df("""
        SELECT *
        FROM core.v_client_operational_summary
        WHERE
            payment_attention_amount > 0
            OR normal_window_amount > 0
            OR shifted_amount > 0
            OR repeated_shift_amount > 0
        ORDER BY
            payment_attention_amount DESC,
            repeated_shift_amount DESC,
            shifted_amount DESC,
            normal_window_amount DESC,
            total_debt DESC
    """)

    branches_df = query_df("""
        SELECT *
        FROM core.v_payment_attention_branches
    """)

    if clients_df.empty:
        ui.label("Нет данных для отображения").classes("text-grey-6")
        return

    selected_branch = {"value": None}

    def filtered_clients(search_text: str = "") -> pd.DataFrame:
        df = clients_df.copy()

        if selected_branch["value"]:
            df = df[df["client_group"] == selected_branch["value"]]

        return df

    def current_metrics(df: pd.DataFrame) -> dict:
        return {
            "in_window": float(df["normal_window_amount"].sum()),
            "out_window": float(df["payment_attention_amount"].sum()),
            "shift_once": float(df["shifted_amount"].sum()),
            "shift_repeated": float(df["repeated_shift_amount"].sum()),
            "clients_to_control": int(
                (
                    (df["payment_attention_amount"] > 0)
                    | (df["shifted_amount"] > 0)
                    | (df["repeated_shift_amount"] > 0)
                ).sum()
            ),
            "in_window_clients": int((df["normal_window_amount"] > 0).sum()),
            "out_window_clients": int((df["payment_attention_amount"] > 0).sum()),
            "shift_once_clients": int((df["shifted_amount"] > 0).sum()),
            "shift_repeated_clients": int((df["repeated_shift_amount"] > 0).sum()),
        }

    metrics = current_metrics(clients_df)

    with ui.row().classes("gap-3 mb-8"):

        compact_kpi(
            "В обычном окне",
            money(metrics["in_window"]),
            f"{metrics['in_window_clients']} клиентов",
        )

        compact_kpi(
            "Вышли из окна",
            money(metrics["out_window"]),
            f"{metrics['out_window_clients']} клиентов",
            "text-orange-700",
        )

        compact_kpi(
            "Разовый перенос",
            money(metrics["shift_once"]),
            f"{metrics['shift_once_clients']} клиентов",
            "text-amber-700",
        )

        compact_kpi(
            "Повторный перенос",
            money(metrics["shift_repeated"]),
            f"{metrics['shift_repeated_clients']} клиентов",
            "text-red-700",
        )

        compact_kpi(
            "Клиентов к контролю",
            str(metrics["clients_to_control"]),
        )

    ui.separator().classes("mb-6")

    ui.label("Сводка по филиалам").classes("text-2xl font-bold mb-2")

    ui.label(
        "Нажатие на филиал ограничивает клиентскую сводку выбранным филиалом."
    ).classes("text-grey-6 mb-4")

    with ui.row().classes("items-center gap-4 mb-4"):
        selected_branch_label = ui.label("Показаны все филиалы").classes(
            "text-sm text-gray-500"
        )

        def reset_branch_filter():
            selected_branch["value"] = None
            selected_branch_label.set_text("Показаны все филиалы")
            refresh_clients()

        ui.button(
            "ВСЕ ФИЛИАЛЫ",
            on_click=reset_branch_filter,
        ).props("flat color=primary")

    branches = branches_df.copy()

    branches = prepare_money_cols(
        branches,
        [
            "amount_in_window",
            "amount_out_of_window",
            "amount_shift_once",
            "amount_shift_repeated",
        ],
    )

    branches["weighted_rating_fmt"] = branches["weighted_rating"].apply(
        lambda value: "—" if pd.isna(value) else f"{float(value):.2f}"
    )

    branches["clients_to_control_fmt"] = branches["clients_to_control"].astype(int).astype(str)
    branches["is_selected"] = False
    branches["is_dimmed"] = False

    def prepare_branch_rows():
        df = branches.copy()

        df["is_selected"] = df["client_group"] == selected_branch["value"]
        df["is_dimmed"] = selected_branch["value"] is not None
        df.loc[df["is_selected"], "is_dimmed"] = False

        return df.to_dict("records")

    branch_table = ui.table(
        columns=[
            {"name": "client_group", "label": "Филиал", "field": "client_group", "align": "left", "sortable": True},
            {"name": "rating", "label": "Рейтинг", "field": "weighted_rating", "align": "center", "sortable": True},
            {"name": "amount_in_window", "label": "В обычном окне", "field": "amount_in_window_fmt", "align": "right", "sortable": True},
            {"name": "amount_out_of_window", "label": "Превышение окна", "field": "amount_out_of_window_fmt", "align": "right", "sortable": True},
            {"name": "amount_shift_once", "label": "Разовый перенос", "field": "amount_shift_once_fmt", "align": "right", "sortable": True},
            {"name": "amount_shift_repeated", "label": "Повторный перенос", "field": "amount_shift_repeated_fmt", "align": "right", "sortable": True},
            {"name": "clients_to_control", "label": "Клиентов к контролю", "field": "clients_to_control_fmt", "align": "right", "sortable": True},
        ],
        rows=prepare_branch_rows(),
        pagination={"rowsPerPage": 20},
    ).classes("w-full mb-8")
    branch_table.props(table_page_props())
    add_branch_summary_slots(branch_table)

    def get_client_table_df() -> pd.DataFrame:
        df = filtered_clients().copy()

        return df.sort_values(
            by=[
                "payment_attention_amount",
                "repeated_shift_amount",
                "shifted_amount",
                "normal_window_amount",
                "total_debt",
            ],
            ascending=[False, False, False, False, False],
        )

    client_table = render_clients_table(
        clients=get_client_table_df(),
        title="Контрагенты",
        subtitle=None,
        show_branch=True,
        show_search=True,
        from_route="payment-attention",
        visible_columns=[
            "client_group",
            "client",
            "rating",
            "total_debt",
            "contract_payment_term_days",
            "usual_payment_window",
            "normal_window_amount",
            "payment_attention_amount",
            "shifted_amount",
            "repeated_shift_amount",
            "invoice_count",
        ],
    )

    def refresh_clients():
        if selected_branch["value"]:
            selected_branch_label.set_text(f"Фильтр: {selected_branch['value']}")
        else:
            selected_branch_label.set_text("Показаны все филиалы")

        branch_table.rows = prepare_branch_rows()
        branch_table.update()

        if client_table is not None:
            client_table.refresh_clients(get_client_table_df())

    def toggle_branch(event):
        branch = event.args

        if selected_branch["value"] == branch:
            selected_branch["value"] = None
        else:
            selected_branch["value"] = branch

        refresh_clients()

    branch_table.on("branch_click", toggle_branch)
    
    def open_client(event):
        ui.navigate.to(f"/client/{event.args}?from=payment-attention")

    def open_branch(event):
        ui.navigate.to(f"/branch/{quote(str(event.args))}?from=/payment-attention")

    if client_table is not None:
        client_table.on("client_click", open_client)
        client_table.on("branch_click", open_branch)

    refresh_clients()