# src/app/components/green_debt_maturity.py

import pandas as pd
import plotly.graph_objects as go


GREEN_DEBT_BUCKET_ORDER = [
    "0–30",
    "31–45",
    "46–60",
    "61–90",
    "91–120",
    "120+",
]


GREEN_DEBT_BUCKET_COLORS = {
    "0–30": "#22c55e",
    "31–45": "#84cc16",
    "46–60": "#facc15",
    "61–90": "#f97316",
    "91–120": "#ef4444",
    "120+": "#991b1b",
}


def build_green_debt_maturity_chart(
    df: pd.DataFrame,
    *,
    title: str | None = None,
    height: int = 380,
) -> go.Figure:
    if df.empty:
        return go.Figure()

    pivot = (
        df.pivot_table(
            index="report_generated_date",
            columns="maturity_bucket",
            values="green_debt_amount",
            aggfunc="sum",
            fill_value=0,
        )
        .reindex(columns=GREEN_DEBT_BUCKET_ORDER, fill_value=0)
        .reset_index()
        .sort_values("report_generated_date")
    )

    fig = go.Figure()

    for bucket in GREEN_DEBT_BUCKET_ORDER:
        fig.add_trace(
            go.Scatter(
                x=pivot["report_generated_date"],
                y=pivot[bucket],
                mode="lines",
                stackgroup="one",
                name=bucket,
                line=dict(
                    width=0.5,
                    color=GREEN_DEBT_BUCKET_COLORS[bucket],
                ),
                fillcolor=GREEN_DEBT_BUCKET_COLORS[bucket],
            )
        )

    fig.update_layout(
        title=title,
        height=height,
        margin=dict(l=20, r=20, t=30, b=20),
        legend=dict(orientation="h", y=1.08, x=1, xanchor="right"),
        yaxis_title="Сумма",
        xaxis_title="Дата среза",
        hovermode="x unified",
    )

    return fig