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


def _invoice_age_days(invoice_date, as_of_date) -> int | None:
    if pd.isna(invoice_date) or pd.isna(as_of_date):
        return None

    from datetime import date

    return (
        pd.Timestamp(date.today()).normalize()
        - pd.to_datetime(invoice_date).normalize()
    ).days


def _payment_expectation_signal(row, behavior_metrics: dict, as_of_date) -> dict:
    if row.get("is_overdue_real"):
        return {
            "label": "Просрочено",
            "level": "overdue",
            "age_days": _invoice_age_days(row.get("invoice_date"), as_of_date),
        }

    if not behavior_metrics.get("has_data"):
        return {
            "label": "Нет профиля",
            "level": "no_data",
            "age_days": _invoice_age_days(row.get("invoice_date"), as_of_date),
        }

    usual_from = behavior_metrics.get("usual_from")
    usual_to = behavior_metrics.get("usual_to")
    invoice_count = int(behavior_metrics.get("invoice_count", 0))

    if pd.isna(usual_from) or pd.isna(usual_to):
        return {
            "label": "Нет профиля",
            "level": "no_data",
            "age_days": _invoice_age_days(row.get("invoice_date"), as_of_date),
        }

    age_days = _invoice_age_days(row.get("invoice_date"), as_of_date)

    if age_days is None:
        return {
            "label": "Нет даты",
            "level": "no_data",
            "age_days": None,
        }

    term_shift_count = int(row.get("term_shift_count", 0) or 0)
    payment_term_days = row.get("payment_term_days")
    due_date = row.get("due_date")

    if (
        term_shift_count >= 1
        and pd.notna(payment_term_days)
        and float(payment_term_days) > float(usual_to)
        and pd.notna(due_date)
    ):
        days_to_due = int(
            (
                pd.to_datetime(due_date).normalize()
                - pd.to_datetime(as_of_date).normalize()
            ).days
        )

        if days_to_due > 3:
            return {
                "label": "-",
                "level": "usual_window",
                "age_days": age_days,
            }

        if days_to_due >= 0:
            return {
                "label": "Пора напомнить",
                "level": "reminder",
                "age_days": age_days,
            }

        return {
            "label": "Просрочено",
            "level": "overdue",
            "age_days": age_days,
        }

    if age_days < float(usual_from):
        return {
            "label": "-",
            "level": "normal",
            "age_days": age_days,
        }

    if age_days <= float(usual_to):
        return {
            "label": "Обычный срок",
            "level": "usual_window",
            "age_days": age_days,
        }

    if invoice_count < 5:
        return {
            "label": "Пора напомнить?",
            "level": "reminder_low_confidence",
            "age_days": age_days,
        }

    return {
        "label": "Пора напомнить",
        "level": "reminder",
        "age_days": age_days,
    }


def _overdue_bucket(row) -> str:
    if not bool(row.get("is_overdue_real", False)):
        return "Не просрочено"

    days = int(row.get("days_overdue_real") or 0)

    if days <= 7:
        return "1–7 дней"
    if days <= 30:
        return "8–30 дней"
    return "31+ дней"


def _baseline_payment_term(row, baseline_payment_term, baseline_by_analytics) -> int | None:
    analytics_type = row.get("analytics_type")

    if pd.isna(analytics_type):
        analytics_type = "—"

    return baseline_by_analytics.get(
        str(analytics_type),
        baseline_payment_term,
    )


def _prepare_rows(
    invoices: pd.DataFrame,
    *,
    behavior_metrics: dict,
    as_of_date,
    baseline_payment_term,
    baseline_by_analytics: dict,
) -> list[dict]:
    df = invoices.copy()

    signals = df.apply(
        lambda row: _payment_expectation_signal(
            row,
            behavior_metrics,
            as_of_date,
        ),
        axis=1,
    )

    df["attention_label"] = signals.apply(lambda value: value["label"])
    df["attention_level"] = signals.apply(lambda value: value["level"])
    df["invoice_age_days"] = signals.apply(lambda value: value["age_days"])

    df["payment_term_baseline_days"] = df.apply(
        lambda row: _baseline_payment_term(
            row,
            baseline_payment_term,
            baseline_by_analytics,
        ),
        axis=1,
    )

    df["is_long_payment_term"] = df["payment_term_days"].apply(
        lambda value: False if pd.isna(value) else int(value) >= 45
    )

    df["is_above_baseline_payment_term"] = df.apply(
        lambda row: (
            False
            if pd.isna(row["payment_term_days"])
            or row["payment_term_baseline_days"] is None
            else int(row["payment_term_days"])
            >= int(row["payment_term_baseline_days"]) + 2
        ),
        axis=1,
    )

    df["payment_term_alert_level"] = df.apply(
        lambda row: (
            "critical"
            if row["is_long_payment_term"]
            else "warning"
            if row["is_above_baseline_payment_term"]
            else "normal"
        ),
        axis=1,
    )

    df["invoice_date_fmt"] = df["invoice_date"].apply(_date_fmt)
    df["due_date_fmt"] = df["due_date"].apply(_date_fmt)
    df["invoice_amount_fmt"] = df["invoice_amount"].apply(_money_precise)

    df["invoice_date_fmt"] = df["invoice_date"].apply(_date_fmt)
    df["due_date_fmt"] = df["due_date"].apply(_date_fmt)

    df["invoice_date_sort"] = df["invoice_date"].apply(_date_sort)
    df["due_date_sort"] = df["due_date"].apply(_date_sort)

    df["invoice_amount_fmt"] = df["invoice_amount"].apply(_money_precise)

    df["payment_term_days_fmt"] = df["payment_term_days"].apply(_int_fmt)
    df["invoice_age_days_fmt"] = df["invoice_age_days"].apply(_int_fmt)
    df["days_overdue_real_fmt"] = df["days_overdue_real"].apply(_int_fmt)

    df["term_shift_count"] = df.get("term_shift_count", 0).fillna(0).astype(int)
    df["term_shift_delta_days"] = df.get("term_shift_delta_days", 0).fillna(0).astype(int)

    df["term_shift_fmt"] = df.apply(
        lambda row: (
            f"{int(row['term_shift_count'])} / +{int(row['term_shift_delta_days'])}"
            if int(row["term_shift_count"]) > 0
            else "—"
        ),
        axis=1,
    )

    df["has_term_shift"] = df["term_shift_count"] > 0
    df["overdue_bucket"] = df.apply(_overdue_bucket, axis=1)

    return df.to_dict("records")


def render_work_invoices_table(
    invoices: pd.DataFrame,
    *,
    show_branch: bool = True,
    show_client: bool = True,
    title: str = "Накладные в работе",
    behavior_metrics: dict | None = None,
    as_of_date=None,
):
    ui.label(title).classes("text-xl font-bold mt-6 mb-2")

    if invoices.empty:
        ui.label("Нет накладных в работе.").classes("text-sm text-gray-500")
        return None

    if as_of_date is None:
        as_of_date = pd.Timestamp.today().normalize()

    if behavior_metrics is None:
        behavior_metrics = {"has_data": False}

    payment_terms = invoices[
        invoices["payment_term_days"].notna()
    ][["analytics_type", "payment_term_days"]].copy()

    payment_terms["analytics_type"] = payment_terms["analytics_type"].fillna("—")

    if not payment_terms.empty:
        payment_terms["payment_term_days"] = payment_terms["payment_term_days"].astype(int)

        baseline_payment_term = int(payment_terms["payment_term_days"].mode().iloc[0])

        baseline_by_analytics = (
            payment_terms
            .groupby("analytics_type")["payment_term_days"]
            .agg(lambda s: int(s.mode().iloc[0]))
            .to_dict()
        )
    else:
        baseline_payment_term = None
        baseline_by_analytics = {}

    source_rows = _prepare_rows(
        invoices,
        behavior_metrics=behavior_metrics,
        as_of_date=as_of_date,
        baseline_payment_term=baseline_payment_term,
        baseline_by_analytics=baseline_by_analytics,
    )

    only_overdue = {"value": False}

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
        {"name": "invoice_age_days", "label": "Возраст", "field": "invoice_age_days", "align": "right", "sortable": True},
        {"name": "attention_label", "label": "Ожидание оплаты", "field": "attention_label", "align": "center", "sortable": True},
        {"name": "term_shift_fmt", "label": "Переносы", "field": "term_shift_fmt", "align": "center"},
        {"name": "invoice_amount", "label": "Сумма", "field": "invoice_amount", "align": "right", "sortable": True},
        {"name": "days_overdue_real", "label": "Просрочка (дни)", "field": "days_overdue_real", "align": "right", "sortable": True},
    ])

    def filtered_rows():
        if not only_overdue["value"]:
            return source_rows
        return [row for row in source_rows if row.get("is_overdue_real")]

    with ui.row().classes("mb-4"):
        toggle = ui.toggle(
            options={
                "all": "ВСЕ",
                "overdue": "ТОЛЬКО ПРОСРОЧЕННЫЕ",
            },
            value="all",
        ).props("unelevated")

    table = ui.table(
        columns=columns,
        rows=filtered_rows(),
        pagination={
            "rowsPerPage": 20,
            "rowsPerPageOptions": [10, 20, 50, 100],
        },
    ).classes("w-full")

    def apply_filter():
        only_overdue["value"] = toggle.value == "overdue"
        table.rows = filtered_rows()
        table.update()

    toggle.on_value_change(lambda _: apply_filter())

    table.add_slot(
        "body",
        """
        <q-tr :props="props"
            :class="
                props.row.is_overdue_real
                    ? 'bg-red-100'
                    : props.row.is_due_today
                        ? 'bg-orange-100'
                        : props.row.is_due_in_3_days
                            ? 'bg-yellow-100'
                            : ''
            ">
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

                <template v-else-if="col.name === 'payment_term_days'">
                    <q-badge
                        :color="
                            props.row.payment_term_alert_level === 'critical'
                                ? 'red'
                                : props.row.payment_term_alert_level === 'warning'
                                    ? 'orange'
                                    : 'grey'
                        "
                        :label="props.row.payment_term_days_fmt"
                    />
                </template>

                <template v-else-if="col.name === 'attention_label'">
                    <q-badge
                        v-if="col.value"
                        :color="
                            props.row.attention_level === 'overdue'
                                ? 'red'
                                : props.row.attention_level === 'reminder'
                                    ? 'orange'
                                    : props.row.attention_level === 'reminder_low_confidence'
                                        ? 'amber'
                                        : props.row.attention_level === 'usual_window'
                                            ? 'blue'
                                            : 'grey'
                        "
                        :label="col.value"
                    />
                    <span v-else></span>
                </template>

                <template v-else-if="col.name === 'term_shift_fmt'">
                    <q-badge
                        v-if="props.row.has_term_shift"
                        color="red"
                        :label="col.value"
                    />
                    <span v-else class="text-grey-6">—</span>
                </template>

                <template v-else-if="col.name === 'invoice_date'">
                    {{ props.row.invoice_date_fmt }}
                </template>

                <template v-else-if="col.name === 'due_date'">
                    {{ props.row.due_date_fmt }}
                </template>

                <template v-else-if="col.name === 'invoice_age_days'">
                    {{ props.row.invoice_age_days_fmt }}
                </template>

                <template v-else-if="col.name === 'invoice_amount'">
                    {{ props.row.invoice_amount_fmt }}
                </template>

                <template v-else-if="col.name === 'days_overdue_real'">
                    {{ props.row.days_overdue_real_fmt }}
                </template>

                <template v-else>
                    {{ col.value }}
                </template>

            </q-td>
        </q-tr>
        """,
    )

    return table