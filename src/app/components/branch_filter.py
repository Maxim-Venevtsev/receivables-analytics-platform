from collections.abc import Callable

import pandas as pd
from nicegui import ui


def _money(value) -> str:
    if pd.isna(value):
        return "0"
    return f"{float(value):,.0f}".replace(",", " ")


def _percent(value) -> str:
    if pd.isna(value):
        return "0%"
    return f"{float(value):.1f}%"


def _normalize_numeric_columns(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    for col in [
        "total_debt",
        "overdue_debt",
        "overdue_share_pct",
        "due_today",
        "due_soon_only",
        "clients_to_control",
    ]:
        if col in result.columns:
            result[col] = result[col].astype(float)
    return result


DEFAULT_COLUMNS = [
    {"name": "client_group", "label": "Филиал", "field": "client_group", "align": "left", "sortable": True},
    {"name": "total_debt", "label": "Весь долг", "field": "total_debt", "align": "right", "sortable": True},
    {"name": "due_today", "label": "К оплате сегодня", "field": "due_today", "align": "right", "sortable": True},
    {"name": "due_soon_only", "label": "К оплате в ближайшие дни", "field": "due_soon_only", "align": "right", "sortable": True},
    {"name": "overdue_debt", "label": "Просрочка", "field": "overdue_debt", "align": "right", "sortable": True},
    {"name": "overdue_share_pct", "label": "% просрочки", "field": "overdue_share_pct", "align": "right", "sortable": True},
]


class BranchFilterComponent:
    """Reusable multi-select branch filter table for operational pages."""

    def __init__(
        self,
        branches: pd.DataFrame,
        selected_branches: list[str],
        on_change: Callable[[], None] | None = None,
        columns: list[dict] | None = None,
        title: str = "Филиалы",
    ):
        self.branches = branches
        self.selected_branches = selected_branches
        self.on_change = on_change
        self.columns = columns or DEFAULT_COLUMNS
        self.title = title
        self.selected_branch_label = None
        self.branch_table = None

    def render(self) -> "BranchFilterComponent":
        ui.separator().classes("my-4")

        with ui.row().classes("items-center gap-4"):
            self.selected_branch_label = ui.label(
                self._selected_label_text()
            ).classes("text-sm text-gray-500")
            ui.button(
                "ВСЕ ФИЛИАЛЫ",
                on_click=self.reset,
            ).props("flat color=primary")

        ui.label(self.title).classes("text-xl mt-6")

        self.branch_table = ui.table(
            columns=self.columns,
            rows=self.prepare_rows(),
        ).classes("w-full")

        self._add_slots()
        self.branch_table.on("branch_click", self.toggle)
        return self

    def prepare_rows(self) -> list[dict]:
        df = _normalize_numeric_columns(self.branches)

        df["is_selected"] = df["client_group"].isin(self.selected_branches)
        df["is_dimmed"] = bool(self.selected_branches) & ~df["is_selected"]

        if "total_debt" in df.columns:
            df["total_debt_fmt"] = df["total_debt"].apply(_money)
        if "due_today" in df.columns:
            df["due_today_fmt"] = df["due_today"].apply(_money)
        if "due_soon_only" in df.columns:
            df["due_soon_only_fmt"] = df["due_soon_only"].apply(_money)
        if "overdue_debt" in df.columns:
            df["overdue_debt_fmt"] = df["overdue_debt"].apply(_money)
        if "overdue_share_pct" in df.columns:
            df["overdue_share_fmt"] = df["overdue_share_pct"].apply(_percent)
        if "clients_to_control" in df.columns:
            df["clients_to_control_fmt"] = df["clients_to_control"].astype(int).astype(str)

        return df.to_dict("records")

    def update(self):
        if self.selected_branch_label is not None:
            self.selected_branch_label.text = self._selected_label_text()
            self.selected_branch_label.update()

        if self.branch_table is not None:
            self.branch_table.rows = self.prepare_rows()
            self.branch_table.update()

    def toggle(self, event):
        branch = event.args

        if branch in self.selected_branches:
            self.selected_branches.remove(branch)
        else:
            self.selected_branches.append(branch)

        if self.on_change:
            self.on_change()
        else:
            self.update()

    def reset(self):
        self.selected_branches.clear()

        if self.on_change:
            self.on_change()
        else:
            self.update()

    def _selected_label_text(self) -> str:
        if self.selected_branches:
            return f"Фильтр: {', '.join(self.selected_branches)}"
        return "Показаны все филиалы"

    def _add_slots(self):
        self.branch_table.add_slot(
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

        self.branch_table.add_slot(
            "body-cell-total_debt",
            """
            <q-td :props="props" class="text-right" :style="props.row.is_dimmed ? 'opacity:0.45;' : ''">
                {{ props.row.total_debt_fmt }}
            </q-td>
            """,
        )

        self.branch_table.add_slot(
            "body-cell-due_today",
            """
            <q-td :props="props" class="text-right" :style="props.row.is_dimmed ? 'opacity:0.45;' : ''">
                <span style="color:#f59e0b; font-weight:600;">
                    {{ props.row.due_today_fmt }}
                </span>
            </q-td>
            """,
        )

        self.branch_table.add_slot(
            "body-cell-due_soon_only",
            """
            <q-td :props="props" class="text-right" :style="props.row.is_dimmed ? 'opacity:0.45;' : ''">
                <span style="color:#ca8a04; font-weight:600;">
                    {{ props.row.due_soon_only_fmt }}
                </span>
            </q-td>
            """,
        )

        self.branch_table.add_slot(
            "body-cell-overdue_debt",
            """
            <q-td :props="props" class="text-right" :style="props.row.is_dimmed ? 'opacity:0.45;' : ''">
                {{ props.row.overdue_debt_fmt }}
            </q-td>
            """,
        )

        self.branch_table.add_slot(
            "body-cell-overdue_share_pct",
            """
            <q-td :props="props" :style="props.row.is_dimmed ? 'opacity:0.45;' : ''">
                <q-badge
                    :color="props.row.overdue_share_pct > 20 ? 'red' : props.row.overdue_share_pct > 0 ? 'orange' : 'green'"
                    :label="props.row.overdue_share_fmt"
                />
            </q-td>
            """,
        )

        self.branch_table.add_slot(
            "body-cell-clients_to_control",
            """
            <q-td :props="props" class="text-right" :style="props.row.is_dimmed ? 'opacity:0.45;' : ''">
                {{ props.row.clients_to_control_fmt }}
            </q-td>
            """,
        )


def create_branch_filter(
    branches: pd.DataFrame,
    selected_branches: list[str],
    on_change: Callable[[], None] | None = None,
    columns: list[dict] | None = None,
    title: str = "Филиалы",
) -> BranchFilterComponent:
    return BranchFilterComponent(
        branches=branches,
        selected_branches=selected_branches,
        on_change=on_change,
        columns=columns,
        title=title,
    ).render()
