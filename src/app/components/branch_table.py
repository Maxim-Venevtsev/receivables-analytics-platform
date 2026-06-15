import pandas as pd
from nicegui import ui

from src.app.components.clients_table import (
    COLUMN_DEFS,
    MONEY_COLUMNS,
    PERCENT_COLUMNS,
    INT_COLUMNS,
    _money,
    _percent,
    _int_fmt,
    _date_fmt,
)
from src.app.components.kpi_cards import percent
from src.app.components.rating_stars import rating_stars_html


BRANCH_VISIBLE_COLUMNS = [
    "client_group",
    "rating",
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


def _num(value, default: float = 0) -> float:
    if pd.isna(value):
        return default
    return float(value)


def _build_columns(visible_columns: list[str]) -> list[dict]:
    columns = []

    for key in visible_columns:
        if key not in COLUMN_DEFS:
            continue

        column = COLUMN_DEFS[key].copy()

        if key == "repeated_shift_invoice_count":
            column["label"] = "Кол-во повторных переносов"

        if key == "last_shift_date":
            column["field"] = "last_shift_date_sort"

        columns.append(column)

    return columns


def _make_json_safe_rows(df: pd.DataFrame) -> list[dict]:
    safe = df.copy()

    for col in safe.columns:
        if pd.api.types.is_datetime64_any_dtype(safe[col]):
            safe[col] = safe[col].apply(
                lambda value: None if pd.isna(value) else pd.to_datetime(value).isoformat()
            )

    safe = safe.astype(object).where(pd.notna(safe), None)

    return safe.to_dict("records")


def _prepare_branch_rows(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()

    if "total_debt" not in result.columns:
        result["total_debt"] = 0

    result["total_debt"] = pd.to_numeric(
        result["total_debt"],
        errors="coerce",
    ).fillna(0)

    result = result[result["total_debt"] >= 1].copy()

    for col in MONEY_COLUMNS:
        if col not in result.columns:
            result[col] = 0
        result[col] = pd.to_numeric(result[col], errors="coerce").fillna(0)
        result[f"{col}_fmt"] = result[col].apply(_money)

    for col in PERCENT_COLUMNS:
        if col not in result.columns:
            result[col] = 0
        result[col] = pd.to_numeric(result[col], errors="coerce").fillna(0)
        result[f"{col}_fmt"] = result[col].apply(_percent)

    for col in INT_COLUMNS:
        if col not in result.columns:
            result[col] = pd.NA
        result[f"{col}_fmt"] = result[col].apply(_int_fmt)

    if "last_shift_date" not in result.columns:
        result["last_shift_date"] = pd.NaT

    result["last_shift_date_dt"] = pd.to_datetime(
        result["last_shift_date"],
        errors="coerce",
    )

    result["last_shift_date_fmt"] = result["last_shift_date_dt"].apply(_date_fmt)

    result["last_shift_date_sort"] = result["last_shift_date_dt"].apply(
        lambda value: "" if pd.isna(value) else value.strftime("%Y-%m-%d")
    )

    stars_source = (
        pd.to_numeric(result["stars"], errors="coerce")
        if "stars" in result.columns
        else pd.Series([pd.NA] * len(result), index=result.index)
    )

    needs_rating_fallback = stars_source.isna() | (stars_source <= 0)

    if "weighted_rating" in result.columns:
        fallback_stars = (
            pd.to_numeric(result["weighted_rating"], errors="coerce")
            .round()
            .clip(lower=1, upper=5)
        )
    elif "weighted_credit_quality_rating" in result.columns:
        fallback_stars = (
            pd.to_numeric(result["weighted_credit_quality_rating"], errors="coerce")
            .round()
            .clip(lower=1, upper=5)
        )
    else:
        fallback_stars = pd.Series([pd.NA] * len(result), index=result.index)

    result["stars"] = stars_source.where(~needs_rating_fallback, fallback_stars)

    result["rating_html"] = result["stars"].apply(
        lambda value: rating_stars_html(int(value)) if pd.notna(value) else "—"
    )

    if "is_selected" not in result.columns:
        result["is_selected"] = False

    if "is_dimmed" not in result.columns:
        result["is_dimmed"] = False

    return result


def _prepare_branch_table_df(
    branches: pd.DataFrame,
    *,
    selected_branches: list[str] | None = None,
) -> pd.DataFrame:
    selected_branches = selected_branches or []

    df = branches.copy()
    df["is_selected"] = df["client_group"].isin(selected_branches)
    df["is_dimmed"] = bool(selected_branches) & ~df["is_selected"]

    return _prepare_branch_rows(df)


def get_worst_branch(branches: pd.DataFrame) -> pd.Series | None:
    if branches.empty:
        return None

    filtered = branches.copy()

    if "total_debt" in filtered.columns:
        filtered["total_debt"] = pd.to_numeric(
            filtered["total_debt"],
            errors="coerce",
        ).fillna(0)
        filtered = filtered[filtered["total_debt"] >= 1].copy()

    if filtered.empty:
        return None

    sort_cols = [
        col for col in [
            "overdue_share_pct",
            "green_90_plus_share_pct",
            "green_120_plus_share_pct",
            "severity_portfolio_penalty",
            "total_debt",
        ]
        if col in filtered.columns
    ]

    if not sort_cols:
        return filtered.iloc[0]

    return (
        filtered
        .sort_values(sort_cols, ascending=False)
        .iloc[0]
    )


def worst_branch_signal_text(branch: pd.Series) -> str:
    return (
        f"{branch['client_group']} · "
        f"просрочка {percent(_num(branch.get('overdue_share_pct')))}, "
        f"90+ непросрочено {percent(_num(branch.get('green_90_plus_share_pct')))}"
    )


def render_branch_table(
    branches: pd.DataFrame,
    *,
    title: str = "Филиалы",
    subtitle: str | None = None,
    mode: str = "executive",
    selected_branches: list[str] | None = None,
    rows_per_page: int = 20,
    visible_columns: list[str] | None = None,
):
    if branches.empty:
        ui.label("Нет данных по филиалам.").classes("text-lg text-gray-500")
        return None

    visible_columns = visible_columns or BRANCH_VISIBLE_COLUMNS

    df = _prepare_branch_table_df(
        branches,
        selected_branches=selected_branches,
    )

    if df.empty:
        ui.label("Нет филиалов с задолженностью от 1 рубля.").classes("text-lg text-gray-500")
        return None

    ui.label(title).classes("text-xl font-bold mt-6 mb-1")

    if subtitle:
        ui.label(subtitle).classes("text-sm text-gray-500 mb-3")

    columns = _build_columns(visible_columns)

    columns = [
        col for col in columns
        if col["field"] in df.columns or col["name"] == "client_group"
    ]

    table = ui.table(
        columns=columns,
        rows=_make_json_safe_rows(df),
        pagination={"rowsPerPage": rows_per_page},
    ).classes("w-full mb-6")

    table.props('rows-per-page-options="[20, 50, 100]"')

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

            <q-btn
                dense
                flat
                color="primary"
                icon="open_in_new"
                class="ml-2"
                @click.stop="$parent.$emit('branch_open', props.row.client_group)"
            />
        </q-td>
        """,
    )

    table.add_slot(
        "body-cell-rating",
        """
        <q-td :props="props" class="text-center" :style="props.row.is_dimmed ? 'opacity:0.45;' : ''">
            <span v-html="props.row.rating_html"></span>
        </q-td>
        """,
    )

    for col in MONEY_COLUMNS:
        if col in df.columns:
            table.add_slot(
                f"body-cell-{col}",
                f"""
                <q-td :props="props" class="text-right" :style="props.row.is_dimmed ? 'opacity:0.45;' : ''">
                    {{{{ props.row.{col}_fmt }}}}
                </q-td>
                """,
            )

    for col in PERCENT_COLUMNS:
        if col in df.columns:
            table.add_slot(
                f"body-cell-{col}",
                f"""
                <q-td :props="props" class="text-center" :style="props.row.is_dimmed ? 'opacity:0.45;' : ''">
                    <q-badge
                        :color="props.row.{col} > 20 ? 'red' : props.row.{col} > 0 ? 'orange' : 'green'"
                        :label="props.row.{col}_fmt"
                    />
                </q-td>
                """,
            )

    for col in INT_COLUMNS:
        if col in df.columns:
            table.add_slot(
                f"body-cell-{col}",
                f"""
                <q-td :props="props" class="text-right" :style="props.row.is_dimmed ? 'opacity:0.45;' : ''">
                    {{{{ props.row.{col}_fmt }}}}
                </q-td>
                """,
            )

    table.add_slot(
        "body-cell-last_shift_date",
        """
        <q-td :props="props" class="text-center" :style="props.row.is_dimmed ? 'opacity:0.45;' : ''">
            {{ props.row.last_shift_date_fmt }}
        </q-td>
        """,
    )

    def refresh_branches(
        new_branches: pd.DataFrame,
        *,
        selected_branches: list[str] | None = None,
    ):
        new_df = _prepare_branch_table_df(
            new_branches,
            selected_branches=selected_branches,
        )
        table.rows = _make_json_safe_rows(new_df)
        table.update()

    table.refresh_branches = refresh_branches

    return table