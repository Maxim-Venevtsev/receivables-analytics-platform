import pandas as pd
from nicegui import ui


def _money_precise(value) -> str:
    if pd.isna(value):
        return "0,00"
    return f"{float(value):,.2f}".replace(",", " ").replace(".", ",")


def _date_fmt(value) -> str:
    if pd.isna(value):
        return ""
    return pd.to_datetime(value).strftime("%d.%m.%Y")

def _date_sort(value) -> str:
    if pd.isna(value):
        return ""
    return pd.to_datetime(value).strftime("%Y-%m-%d")

def _int_fmt(value) -> str:
    if pd.isna(value):
        return ""
    return str(int(value))


def _paid_behavior_label(row, behavior_metrics: dict) -> str:
    usual_from = behavior_metrics.get("usual_from")
    usual_to = behavior_metrics.get("usual_to")
    actual_days = row.get("actual_payment_term_days")

    if pd.isna(actual_days) or pd.isna(usual_from) or pd.isna(usual_to):
        return ""

    actual_days = float(actual_days)

    if actual_days < float(usual_from):
        return "Раньше обычного"

    if actual_days <= float(usual_to):
        return "Обычно"

    if actual_days <= float(usual_to) + 7:
        return "Позже обычного"

    return "Сильно позже"


def _paid_behavior_level(label: str) -> str:
    return {
        "Раньше обычного": "early",
        "Обычно": "normal",
        "Позже обычного": "late",
        "Сильно позже": "very_late",
    }.get(label, "")


def _payment_delay_fmt(value) -> str:
    if pd.isna(value):
        return ""
    value = int(value)
    return "В срок" if value <= 0 else f"+{value}"


def _payment_delay_level(value) -> str:
    if pd.isna(value):
        return ""
    value = int(value)

    if value <= 0:
        return "on_time"
    if value <= 3:
        return "small_delay"
    if value <= 14:
        return "delay"
    return "late"


def _prepare_rows(
    paid_invoices: pd.DataFrame,
    payment_behavior_metrics: dict,
) -> list[dict]:
    df = paid_invoices.copy().head(20)

    df["invoice_date_fmt"] = df["invoice_date"].apply(_date_fmt)
    df["due_date_fmt"] = df["due_date"].apply(_date_fmt)
    df["estimated_payment_date_fmt"] = df["estimated_payment_date"].apply(_date_fmt)

    df["invoice_date_sort"] = df["invoice_date"].apply(_date_sort)
    df["due_date_sort"] = df["due_date"].apply(_date_sort)
    df["estimated_payment_date_sort"] = df["estimated_payment_date"].apply(_date_sort)
    df["paid_amount_fmt"] = df["paid_amount_detected"].apply(_money_precise)
    df["payment_term_days_fmt"] = df["payment_term_days"].apply(_int_fmt)
    df["actual_payment_term_days_fmt"] = df["actual_payment_term_days"].apply(_int_fmt)

    df["days_vs_due_date"] = df["days_vs_due_date"].fillna(0).astype(int)
    df["payment_delay_fmt"] = df["days_vs_due_date"].apply(_payment_delay_fmt)
    df["payment_delay_level"] = df["days_vs_due_date"].apply(_payment_delay_level)
    df["is_payment_overdue"] = df["days_vs_due_date"] > 0

    df["term_shift_count"] = df["term_shift_count"].fillna(0).astype(int)
    df["term_shift_delta_days"] = df["term_shift_delta_days"].fillna(0).astype(int)

    df["term_shift_fmt"] = df.apply(
        lambda row: (
            f"{int(row['term_shift_count'])} / +{int(row['term_shift_delta_days'])}"
            if int(row["term_shift_count"]) > 0
            else "—"
        ),
        axis=1,
    )

    df["has_term_shift"] = df["term_shift_count"] > 0

    df["paid_behavior_label"] = df.apply(
        lambda row: _paid_behavior_label(row, payment_behavior_metrics),
        axis=1,
    )
    df["paid_behavior_level"] = df["paid_behavior_label"].apply(_paid_behavior_level)

    df["payment_event_type_label"] = df["payment_event_type"].map({
        "FULL": "Полная",
        "PARTIAL": "Частичная",
    }).fillna(df["payment_event_type"])

    return df.to_dict("records")


def render_paid_invoices_table(
    paid_invoices: pd.DataFrame,
    *,
    payment_behavior_metrics: dict | None = None,
    show_branch: bool = True,
    show_client: bool = True,
    title: str = "Последние оплаченные накладные",
):
    if paid_invoices.empty:
        return None

    if payment_behavior_metrics is None:
        payment_behavior_metrics = {"has_data": False}

    ui.label(title).classes("text-xl font-bold mt-6 mb-1")
    ui.label(
        "Расчетная дата оплаты восстановлена по исчезновению накладной из открытой дебиторки "
        "или по снижению открытого остатка между срезами."
    ).classes("text-sm text-gray-500 mb-3")

    columns = []

    if show_branch:
        columns.append({
            "name": "client_group",
            "label": "Филиал",
            "field": "client_group",
            "sortable": True,
            "align": "left",
        })

    if show_client:
        columns.append({
            "name": "client_name",
            "label": "Наименование",
            "field": "client_name",
            "sortable": True,
            "align": "left",
        })

    columns.extend([
        {"name": "invoice_date", "label": "Дата накладной", "field": "invoice_date_sort", "sortable": True},
        {"name": "order_number", "label": "Номер заказа", "field": "order_number", "sortable": True},
        {"name": "print_invoice_number", "label": "Номер накладной", "field": "print_invoice_number", "sortable": True},
        {"name": "analytics_type", "label": "Аналитика", "field": "analytics_type", "sortable": True},
        {"name": "due_date", "label": "Оплатить до", "field": "due_date_sort", "sortable": True},
        {"name": "payment_term_days", "label": "Отсрочка", "field": "payment_term_days", "align": "center", "sortable": True},
        {"name": "estimated_payment_date", "label": "Дата оплаты", "field": "estimated_payment_date_sort", "sortable": True},
        {"name": "actual_payment_term_days", "label": "Возраст", "field": "actual_payment_term_days", "align": "right", "sortable": True},
        {"name": "paid_behavior", "label": "Дисциплина", "field": "paid_behavior_label", "align": "center", "sortable": True},
        {"name": "payment_delay", "label": "Просрочка", "field": "days_vs_due_date", "align": "center", "sortable": True},
        {"name": "term_shift_fmt", "label": "Переносы", "field": "term_shift_fmt", "align": "center"},
        {"name": "paid_amount", "label": "Оплачено", "field": "paid_amount_detected", "align": "right", "sortable": True},
        {"name": "payment_event_type", "label": "Тип", "field": "payment_event_type_label", "align": "center", "sortable": True},
    ])

    table = ui.table(
        columns=columns,
        rows=_prepare_rows(paid_invoices, payment_behavior_metrics),
        pagination={"rowsPerPage": 20},
    ).classes("w-full")

    table.add_slot(
        "body",
        """
        <q-tr :props="props"
            :class="props.row.is_payment_overdue ? 'bg-red-100' : ''">
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

                <template v-else-if="col.name === 'client_name'">
                    <q-btn
                        flat
                        dense
                        color="primary"
                        :label="props.row.client_id + ' · ' + props.row.client_name"
                        @click="$parent.$emit('client_click', props.row.client_id)"
                    />
                </template>

                <template v-else-if="col.name === 'paid_behavior'">
                    <q-badge
                        v-if="col.value"
                        :color="
                            props.row.paid_behavior_level === 'early'
                                ? 'green'
                                : props.row.paid_behavior_level === 'normal'
                                    ? 'blue'
                                    : props.row.paid_behavior_level === 'late'
                                        ? 'orange'
                                        : 'red'
                        "
                        :label="col.value"
                    />
                    <span v-else></span>
                </template>

                <template v-else-if="col.name === 'payment_delay'">
                    <q-badge
                        :color="
                            props.row.payment_delay_level === 'on_time'
                                ? 'green'
                                : props.row.payment_delay_level === 'small_delay'
                                    ? 'orange'
                                    : props.row.payment_delay_level === 'delay'
                                        ? 'red'
                                        : 'dark'
                        "
                        :label="props.row.payment_delay_fmt"
                    />
                </template>

                <template v-else-if="col.name === 'term_shift_fmt'">
                    <q-badge
                        v-if="props.row.has_term_shift"
                        color="red"
                        :label="col.value"
                    />
                    <span v-else class="text-grey-6">—</span>
                </template>

                <template v-else-if="col.name === 'payment_event_type'">
                    <q-badge
                        :color="props.row.payment_event_type === 'FULL' ? 'green' : 'blue'"
                        :label="col.value"
                    />
                </template>

                <template v-else-if="col.name === 'invoice_date'">
                    {{ props.row.invoice_date_fmt }}
                </template>

                <template v-else-if="col.name === 'due_date'">
                    {{ props.row.due_date_fmt }}
                </template>

                <template v-else-if="col.name === 'estimated_payment_date'">
                    {{ props.row.estimated_payment_date_fmt }}
                </template>

                <template v-else-if="col.name === 'payment_term_days'">
                    {{ props.row.payment_term_days_fmt }}
                </template>

                <template v-else-if="col.name === 'actual_payment_term_days'">
                    {{ props.row.actual_payment_term_days_fmt }}
                </template>

                <template v-else-if="col.name === 'paid_amount'">
                    {{ props.row.paid_amount_fmt }}
                </template>

                <template v-else>
                    {{ col.value }}
                </template>

            </q-td>
        </q-tr>
        """,
    )

    return table