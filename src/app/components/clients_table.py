from urllib.parse import quote

import pandas as pd
from nicegui import ui

from src.app.components.rating_stars import rating_stars_html


DEFAULT_VISIBLE_COLUMNS = [
    "client_group",
    "client",
    "rating",
    "contract_payment_term_days",
    "usual_payment_window",
    "total_debt",
    "due_today",
    "due_soon_only",
    "normal_window_amount",
    "payment_attention_amount",
    "overdue_debt",
    "overdue_share_pct",
    "max_days_overdue",
    "shifted_amount",
    "shifted_share_pct",
    "shifted_invoice_count",
    "term_shift_count",
    "repeated_shift_amount",
    "repeated_shift_invoice_count",
    "last_shift_date",
    "max_current_term_delta_days",
    "max_current_payment_term_days",
    "invoice_count",
    "debt_45_plus",
    "debt_60_plus",
    "debt_90_plus",
    "debt_120_plus",
]


COLUMN_DEFS = {
    "client_group": {
        "name": "client_group",
        "label": "Филиал",
        "field": "client_group",
        "align": "left",
        "sortable": True,
    },
    "client": {
        "name": "client",
        "label": "Наименование",
        "field": "client_display",
        "align": "left",
        "sortable": True,
    },
    "rating": {
        "name": "rating",
        "label": "Рейтинг",
        "field": "stars",
        "align": "center",
        "sortable": True,
    },
    "contract_payment_term_days": {
        "name": "contract_payment_term_days",
        "label": "Контрактная отсрочка",
        "field": "contract_payment_term_days",
        "align": "right",
        "sortable": True,
    },
    "usual_payment_window": {
        "name": "usual_payment_window",
        "label": "Обычное окно",
        "field": "usual_payment_window_fmt",
        "align": "center",
        "sortable": True,
    },
    "total_debt": {
        "name": "total_debt",
        "label": "Весь долг",
        "field": "total_debt",
        "align": "right",
        "sortable": True,
    },
    "due_today": {
        "name": "due_today",
        "label": "К оплате сегодня",
        "field": "due_today",
        "align": "right",
        "sortable": True,
    },
    "due_soon_only": {
        "name": "due_soon_only",
        "label": "К оплате в ближайшие дни",
        "field": "due_soon_only",
        "align": "right",
        "sortable": True,
    },
    "normal_window_amount": {
        "name": "normal_window_amount",
        "label": "В обычном окне",
        "field": "normal_window_amount",
        "align": "right",
        "sortable": True,
    },
    "payment_attention_amount": {
        "name": "payment_attention_amount",
        "label": "Превышение окна",
        "field": "payment_attention_amount",
        "align": "right",
        "sortable": True,
    },
    "overdue_debt": {
        "name": "overdue_debt",
        "label": "Просрочка",
        "field": "overdue_debt",
        "align": "right",
        "sortable": True,
    },
    "overdue_share_pct": {
        "name": "overdue_share_pct",
        "label": "% просрочки",
        "field": "overdue_share_pct",
        "align": "center",
        "sortable": True,
    },
    "max_days_overdue": {
        "name": "max_days_overdue",
        "label": "Макс дней просрочки",
        "field": "max_days_overdue",
        "align": "right",
        "sortable": True,
    },
    "shifted_amount": {
        "name": "shifted_amount",
        "label": "Переносы",
        "field": "shifted_amount",
        "align": "right",
        "sortable": True,
    },
    "shifted_share_pct": {
        "name": "shifted_share_pct",
        "label": "% переносов",
        "field": "shifted_share_pct",
        "align": "center",
        "sortable": True,
    },
    "shifted_invoice_count": {
        "name": "shifted_invoice_count",
        "label": "Накладные",
        "field": "shifted_invoice_count",
        "align": "right",
        "sortable": True,
    },
    "term_shift_count": {
        "name": "term_shift_count",
        "label": "Кол-во переносов",
        "field": "term_shift_count",
        "align": "right",
        "sortable": True,
    },
    "repeated_shift_amount": {
        "name": "repeated_shift_amount",
        "label": "Повт. переносы",
        "field": "repeated_shift_amount",
        "align": "right",
        "sortable": True,
    },
    "repeated_shift_invoice_count": {
        "name": "repeated_shift_invoice_count",
        "label": "Кол-во повт. переносов",
        "field": "repeated_shift_invoice_count",
        "align": "right",
        "sortable": True,
    },
        "last_shift_date": {
        "name": "last_shift_date",
        "label": "Посл. перенос",
        "field": "last_shift_date_sort",
        "align": "center",
        "sortable": True,
    },
    "max_current_term_delta_days": {
        "name": "max_current_term_delta_days",
        "label": "Макс. рост",
        "field": "max_current_term_delta_days_fmt",
        "align": "right",
        "sortable": True,
    },
    "max_current_payment_term_days": {
        "name": "max_current_payment_term_days",
        "label": "Макс. срок",
        "field": "max_current_payment_term_days_fmt",
        "align": "right",
        "sortable": True,
    },
    "invoice_count": {
        "name": "invoice_count",
        "label": "Кол-во накладных",
        "field": "invoice_count_fmt",
        "align": "right",
        "sortable": True,
    },
    "debt_45_plus": {
        "name": "debt_45_plus",
        "label": "45+",
        "field": "debt_45_plus",
        "align": "right",
        "sortable": True,
    },
    "debt_60_plus": {
        "name": "debt_60_plus",
        "label": "60+",
        "field": "debt_60_plus",
        "align": "right",
        "sortable": True,
    },
    "debt_90_plus": {
        "name": "debt_90_plus",
        "label": "90+",
        "field": "debt_90_plus",
        "align": "right",
        "sortable": True,
    },
    "debt_120_plus": {
        "name": "debt_120_plus",
        "label": "120+",
        "field": "debt_120_plus",
        "align": "right",
        "sortable": True,
    },
    "green_45_plus_debt": {
        "name": "green_45_plus_debt",
        "label": "45+",
        "field": "green_45_plus_debt",
        "align": "right",
        "sortable": True,
    },

    "green_60_plus_debt": {
        "name": "green_60_plus_debt",
        "label": "60+",
        "field": "green_60_plus_debt",
        "align": "right",
        "sortable": True,
    },

    "green_90_plus_debt": {
        "name": "green_90_plus_debt",
        "label": "90+",
        "field": "green_90_plus_debt",
        "align": "right",
        "sortable": True,
    },

    "green_120_plus_debt": {
        "name": "green_120_plus_debt",
        "label": "120+",
        "field": "green_120_plus_debt",
        "align": "right",
        "sortable": True,
    },

    "max_payment_term_days": {
        "name": "max_payment_term_days",
        "label": "Макс. отсрочка",
        "field": "max_payment_term_days",
        "align": "right",
        "sortable": True,
    },
    "due_today_share_pct": {
    "name": "due_today_share_pct",
    "label": "% сегодня",
    "field": "due_today_share_pct",
    "align": "center",
    "sortable": True,
    },
    "due_soon_share_pct": {
    "name": "due_soon_share_pct",
    "label": "% ближайшие дни",
    "field": "due_soon_share_pct",
    "align": "center",
    "sortable": True,
    },
}


MONEY_COLUMNS = [
    "total_debt",
    "due_today",
    "due_soon_only",
    "normal_window_amount",
    "payment_attention_amount",
    "overdue_debt",
    "shifted_amount",
    "repeated_shift_amount",
    "debt_45_plus",
    "debt_60_plus",
    "debt_90_plus",
    "debt_120_plus",
    "green_45_plus_debt",
    "green_60_plus_debt",
    "green_90_plus_debt",
    "green_120_plus_debt",
]

PERCENT_COLUMNS = [
    "overdue_share_pct",
    "shifted_share_pct",
    "due_today_share_pct",
    "due_soon_share_pct",
]

INT_COLUMNS = [
    "contract_payment_term_days",
    "max_days_overdue",
    "shifted_invoice_count",
    "term_shift_count",
    "repeated_shift_invoice_count",
    "max_current_term_delta_days",
    "max_current_payment_term_days",
    "invoice_count",
    "max_payment_term_days",
]


def _money(value) -> str:
    if pd.isna(value):
        return "0"
    return f"{float(value):,.0f}".replace(",", " ")


def _percent(value) -> str:
    if pd.isna(value):
        return "0%"
    return f"{float(value):.1f}%"


def _int_fmt(value) -> str:
    if pd.isna(value):
        return "—"
    return str(int(value))


def _date_fmt(value) -> str:
    if pd.isna(value):
        return ""
    return pd.to_datetime(value).strftime("%d.%m.%Y")


def _term_shift_count_level(value) -> str:
    value = int(value or 0)
    if value >= 10:
        return "critical"
    if value >= 5:
        return "high"
    if value >= 3:
        return "medium"
    if value > 0:
        return "low"
    return "none"


def _term_growth_level(value) -> str:
    value = int(value or 0)
    if value >= 60:
        return "critical"
    if value >= 30:
        return "high"
    if value >= 14:
        return "medium"
    if value > 0:
        return "low"
    return "none"


def _payment_term_level(value) -> str:
    value = int(value or 0)
    if value >= 120:
        return "critical"
    if value >= 90:
        return "high"
    if value >= 60:
        return "medium"
    if value >= 45:
        return "low"
    return "none"


def _prepare_rows(
    clients: pd.DataFrame,
    *,
    search_value: str = "",
    from_route: str = "dashboard",
    use_operational_sort: bool = True,
) -> list[dict]:
    df = clients.copy()

    if df.empty:
        return []

    value = (search_value or "").strip().lower()

    if value:
        df = df[
            df["client_id"].astype(str).str.lower().str.contains(value, na=False)
            | df["client_name"].astype(str).str.lower().str.contains(value, na=False)
        ]

    if df.empty:
        return []

    for col in MONEY_COLUMNS:
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        df[f"{col}_fmt"] = df[col].apply(_money)

    for col in PERCENT_COLUMNS:
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        df[f"{col}_fmt"] = df[col].apply(_percent)

    for col in INT_COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA
        df[f"{col}_fmt"] = df[col].apply(_int_fmt)

    def _usual_window(row) -> str:
        usual_from = row.get("usual_from_days")
        usual_to = row.get("usual_to_days")

        if pd.isna(usual_from) or pd.isna(usual_to):
            return "—"

        return (
            f"{int(round(float(usual_from)))} дн. – "
            f"{int(round(float(usual_to)))} дн."
        )

    df["usual_payment_window_fmt"] = df.apply(_usual_window, axis=1)

    if "last_shift_date" not in df.columns:
        df["last_shift_date"] = pd.NaT

    last_shift_date_dt = pd.to_datetime(
        df["last_shift_date"],
        errors="coerce",
    )

    df["last_shift_date_fmt"] = last_shift_date_dt.apply(_date_fmt)

    df["last_shift_date_sort"] = last_shift_date_dt.apply(
        lambda value: "" if pd.isna(value)
        else value.strftime("%Y-%m-%d")
    )

    if "stars" not in df.columns:
        df["stars"] = pd.NA

    df["rating_html"] = df["stars"].apply(
        lambda value: rating_stars_html(int(value)) if pd.notna(value) else "—"
    )

    df["client_display"] = df.apply(
        lambda row: f"{row['client_id']} · {row['client_name']}",
        axis=1,
    )

    df["client_url"] = df["client_id"].apply(
        lambda value: f"/client/{quote(str(value))}?from={from_route}"
    )

    df["term_shift_count_level"] = df["term_shift_count"].apply(
        _term_shift_count_level
    )
    df["max_current_term_delta_days_level"] = df[
        "max_current_term_delta_days"
    ].apply(_term_growth_level)
    df["max_current_payment_term_days_level"] = df[
        "max_current_payment_term_days"
    ].apply(_payment_term_level)

    if "operational_status" not in df.columns:
        df["operational_status"] = "NORMAL"

    if use_operational_sort and "operational_sort_order" in df.columns:
        df = df.sort_values(
            by=[
                "operational_sort_order",
                "overdue_debt",
                "due_today",
                "due_soon_only",
                "payment_attention_amount",
                "shifted_amount",
                "total_debt",
            ],
            ascending=[True, False, False, False, False, False, False],
        )

    return df.to_dict("records")


def _build_columns(
    visible_columns: list[str] | None,
    *,
    show_branch: bool,
) -> list[dict]:
    keys = visible_columns or DEFAULT_VISIBLE_COLUMNS

    if not show_branch:
        keys = [key for key in keys if key != "client_group"]

    return [
        COLUMN_DEFS[key]
        for key in keys
        if key in COLUMN_DEFS
    ]


def render_clients_table(
    clients: pd.DataFrame,
    *,
    title: str = "Контрагенты",
    subtitle: str | None = None,
    visible_columns: list[str] | None = None,
    show_branch: bool = True,
    show_search: bool = False,
    from_route: str = "dashboard",
    default_sort_by: str | None = None,
    default_sort_descending: bool = True,
    preserve_input_order: bool = False,
):
    if clients.empty:
        return None

    ui.label(title).classes("text-xl font-bold mt-6 mb-1")

    if subtitle:
        ui.label(subtitle).classes("text-sm text-gray-500 mb-3")

    search_input = None

    if show_search:
        search_input = ui.input(
            placeholder="Поиск клиента по названию или коду..."
        ).props("clearable").classes("w-96 mb-3")

    pagination = {"rowsPerPage": 20}

    if default_sort_by is not None:
        pagination.update({
            "sortBy": default_sort_by,
            "descending": default_sort_descending,
        })

    table = ui.table(
        columns=_build_columns(
            visible_columns,
            show_branch=show_branch,
        ),
        rows=_prepare_rows(
            clients,
            search_value="",
            from_route=from_route,
            use_operational_sort=default_sort_by is None and not preserve_input_order,
        ),
        pagination=pagination,
    ).classes("w-full mb-6")

    table.props('rows-per-page-options="[20, 50, 100]"')

    table.add_slot(
        "body",
        """
        <q-tr
            :props="props"
            :class="{
                'bg-red-1': props.row.operational_status === 'OVERDUE',
                'bg-orange-1': props.row.operational_status === 'DUE_TODAY',
                'bg-yellow-1': props.row.operational_status === 'DUE_SOON'
            }"
        >
            <q-td v-for="col in props.cols" :key="col.name" :props="props">

                <template v-if="col.name === 'client_group'">
                    <q-btn
                        flat
                        dense
                        color="primary"
                        :label="props.row.client_group"
                        @click="$parent.$emit('branch_click', props.row.client_group)"
                    />
                </template>

                <template v-else-if="col.name === 'client'">
                    <q-btn
                        flat
                        dense
                        color="primary"
                        :label="props.row.client_display"
                        @click="$parent.$emit('client_click', props.row.client_id)"
                    />
                </template>

                <template v-else-if="col.name === 'rating'">
                    <span v-html="props.row.rating_html"></span>
                </template>

                <template v-else-if="['overdue_share_pct', 'shifted_share_pct', 'due_today_share_pct', 'due_soon_share_pct'].includes(col.name)">
                    <q-badge
                        :color="props.row[col.name] > 20 ? 'red' : props.row[col.name] > 0 ? 'orange' : 'green'"
                        :label="props.row[col.name + '_fmt']"
                    />
                </template>

                <template v-else-if="col.name === 'term_shift_count'">
                    <span
                        :class="{
                            'text-red-900 font-bold': props.row.term_shift_count_level === 'critical',
                            'text-red-700 font-bold': props.row.term_shift_count_level === 'high',
                            'text-orange-600 font-bold': props.row.term_shift_count_level === 'medium',
                            'text-yellow-700 font-bold': props.row.term_shift_count_level === 'low'
                        }"
                    >
                        {{ col.value }}
                    </span>
                </template>

                <template v-else-if="col.name === 'max_current_term_delta_days'">
                    <span
                        :class="{
                            'text-red-900 font-bold': props.row.max_current_term_delta_days_level === 'critical',
                            'text-red-700 font-bold': props.row.max_current_term_delta_days_level === 'high',
                            'text-orange-600 font-bold': props.row.max_current_term_delta_days_level === 'medium',
                            'text-yellow-700 font-bold': props.row.max_current_term_delta_days_level === 'low'
                        }"
                    >
                        {{ props.row.max_current_term_delta_days > 0 ? '+' + props.row.max_current_term_delta_days : col.value }}
                    </span>
                </template>

                <template v-else-if="col.name === 'max_current_payment_term_days'">
                    <span
                        :class="{
                            'text-red-900 font-bold': props.row.max_current_payment_term_days_level === 'critical',
                            'text-red-700 font-bold': props.row.max_current_payment_term_days_level === 'high',
                            'text-orange-600 font-bold': props.row.max_current_payment_term_days_level === 'medium',
                            'text-yellow-700 font-bold': props.row.max_current_payment_term_days_level === 'low'
                        }"
                    >
                        {{ col.value }}
                    </span>
                </template>

                <template v-else-if="[
                    'total_debt',
                    'due_today',
                    'due_soon_only',
                    'normal_window_amount',
                    'payment_attention_amount',
                    'overdue_debt',
                    'shifted_amount',
                    'repeated_shift_amount',
                    'debt_45_plus',
                    'debt_60_plus',
                    'debt_90_plus',
                    'debt_120_plus',
                    'green_45_plus_debt',
                    'green_60_plus_debt',
                    'green_90_plus_debt',
                    'green_120_plus_debt'
                ].includes(col.name)">
                    {{ props.row[col.name + '_fmt'] }}
                </template>

                <template v-else-if="col.name === 'last_shift_date'">
                    {{ props.row.last_shift_date_fmt }}
                </template>
                
                <template v-else>
                    {{ col.value }}
                </template>

            </q-td>
        </q-tr>
        """,
    )

    if search_input is not None:
        def apply_search():
            table.rows = _prepare_rows(
                clients,
                search_value=search_input.value or "",
                from_route=from_route,
                use_operational_sort=default_sort_by is None and not preserve_input_order,
            )
            table.update()

        search_input.on_value_change(lambda _: apply_search())

    def refresh(new_clients: pd.DataFrame):
        table.rows = _prepare_rows(
            new_clients,
            search_value=search_input.value or "" if search_input is not None else "",
            from_route=from_route,
            use_operational_sort=default_sort_by is None and not preserve_input_order,
        )
        table.update()

    table.refresh_clients = refresh
    
    return table
