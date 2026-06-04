import pandas as pd
import plotly.graph_objects as go


def build_client_debt_history_chart(history_df: pd.DataFrame) -> go.Figure:
    chart = go.Figure()

    chart.add_trace(go.Scatter(
        x=history_df["report_generated_date"],
        y=history_df["total_debt"],
        mode="lines",
        name="Общий долг",
        line=dict(color="#2563eb", width=4, shape="spline", smoothing=0.6),
    ))

    chart.add_trace(go.Scatter(
        x=history_df["report_generated_date"],
        y=history_df["overdue_debt"],
        mode="lines",
        name="Просрочено",
        line=dict(color="#dc2626", width=4, shape="spline", smoothing=0.6),
    ))

    chart.update_layout(
        height=320,
        margin=dict(l=20, r=20, t=40, b=20),
        paper_bgcolor="white",
        plot_bgcolor="white",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
        xaxis=dict(title="", showgrid=False),
        yaxis=dict(title="", gridcolor="#e5e7eb", zeroline=False),
        hovermode="x unified",
    )

    return chart


def build_client_debt_structure_chart(history_df: pd.DataFrame) -> go.Figure:
    chart = go.Figure()

    chart.add_trace(go.Scatter(
        x=history_df["report_generated_date"],
        y=history_df["normal_debt"],
        mode="lines",
        name="Не просрочено",
        stackgroup="one",
        line=dict(color="#22c55e", width=0),
        fillcolor="#22c55e",
    ))

    chart.add_trace(go.Scatter(
        x=history_df["report_generated_date"],
        y=history_df["due_soon_only"],
        mode="lines",
        name="К оплате в ближайшие дни",
        stackgroup="one",
        line=dict(color="#fde68a", width=0),
        fillcolor="#fde68a",
    ))

    chart.add_trace(go.Scatter(
        x=history_df["report_generated_date"],
        y=history_df["due_today"],
        mode="lines",
        name="К оплате сегодня",
        stackgroup="one",
        line=dict(color="#f59e0b", width=0),
        fillcolor="#f59e0b",
    ))

    chart.add_trace(go.Scatter(
        x=history_df["report_generated_date"],
        y=history_df["overdue_debt"],
        mode="lines",
        name="Просрочено",
        stackgroup="one",
        line=dict(color="#dc2626", width=0),
        fillcolor="#dc2626",
    ))

    chart.update_layout(
        height=320,
        margin=dict(l=20, r=20, t=40, b=20),
        paper_bgcolor="white",
        plot_bgcolor="white",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
        xaxis=dict(title="", showgrid=False),
        yaxis=dict(title="", gridcolor="#e5e7eb", zeroline=False),
        hovermode="x unified",
    )

    return chart

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
    height: int = 320,
) -> go.Figure:
    chart = go.Figure()

    if df.empty:
        return chart

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

    for bucket in GREEN_DEBT_BUCKET_ORDER:
        chart.add_trace(go.Scatter(
            x=pivot["report_generated_date"],
            y=pivot[bucket],
            mode="lines",
            name=bucket,
            stackgroup="one",
            line=dict(
                color=GREEN_DEBT_BUCKET_COLORS[bucket],
                width=0,
            ),
            fillcolor=GREEN_DEBT_BUCKET_COLORS[bucket],
        ))

    chart.update_layout(
        height=height,
        margin=dict(l=20, r=20, t=40, b=20),
        paper_bgcolor="white",
        plot_bgcolor="white",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
        xaxis=dict(title="", showgrid=False),
        yaxis=dict(title="", gridcolor="#e5e7eb", zeroline=False),
        hovermode="x unified",
    )

    return chart

def build_portfolio_debt_history_chart(history_df: pd.DataFrame) -> go.Figure:
    return build_client_debt_history_chart(history_df)


def build_portfolio_debt_structure_chart(history_df: pd.DataFrame) -> go.Figure:
    return build_client_debt_structure_chart(history_df)


def build_debt_quality_chart(history_df: pd.DataFrame) -> go.Figure:
    chart = go.Figure()

    chart.add_trace(go.Scatter(
        x=history_df["report_generated_date"],
        y=history_df["reliable_debt"],
        mode="lines",
        name="Надежная задолженность",
        stackgroup="one",
        line=dict(color="#22c55e", width=0),
        fillcolor="#22c55e",
    ))

    chart.add_trace(go.Scatter(
        x=history_df["report_generated_date"],
        y=history_df["control_required_debt"],
        mode="lines",
        name="Требует контроля",
        stackgroup="one",
        line=dict(color="#f97316", width=0),
        fillcolor="#f97316",
    ))

    chart.update_layout(
        height=320,
        margin=dict(l=20, r=20, t=40, b=20),
        paper_bgcolor="white",
        plot_bgcolor="white",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
        xaxis=dict(title="", showgrid=False),
        yaxis=dict(title="", gridcolor="#e5e7eb", zeroline=False),
        hovermode="x unified",
    )

    return chart


def build_weighted_payment_term_chart(history_df: pd.DataFrame) -> go.Figure:
    chart = go.Figure()

    chart.add_trace(go.Scatter(
        x=history_df["report_generated_date"],
        y=history_df["weighted_avg_payment_term_days"],
        mode="lines",
        name="Средневзвешенная отсрочка",
        line=dict(color="#2563eb", width=4, shape="spline", smoothing=0.6),
    ))

    chart.add_trace(go.Scatter(
        x=history_df["report_generated_date"],
        y=history_df["weighted_avg_green_payment_term_days"],
        mode="lines",
        name="Средневзвешенная отсрочка непросроченного долга",
        line=dict(color="#f97316", width=4, shape="spline", smoothing=0.6),
    ))

    chart.update_layout(
        height=320,
        margin=dict(l=20, r=20, t=40, b=20),
        paper_bgcolor="white",
        plot_bgcolor="white",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
        xaxis=dict(title="", showgrid=False),
        yaxis=dict(title="Дней", gridcolor="#e5e7eb", zeroline=False),
        hovermode="x unified",
    )

    return chart


def build_long_green_exposure_chart(history_df: pd.DataFrame) -> go.Figure:
    chart = go.Figure()

    chart.add_trace(go.Scatter(
        x=history_df["report_generated_date"],
        y=history_df["green_90_plus_debt"],
        mode="lines",
        name="90+ непросрочено",
        line=dict(color="#f97316", width=4, shape="spline", smoothing=0.6),
    ))

    chart.add_trace(go.Scatter(
        x=history_df["report_generated_date"],
        y=history_df["green_120_plus_debt"],
        mode="lines",
        name="120+ непросрочено",
        line=dict(color="#dc2626", width=4, shape="spline", smoothing=0.6),
    ))

    chart.update_layout(
        height=320,
        margin=dict(l=20, r=20, t=40, b=20),
        paper_bgcolor="white",
        plot_bgcolor="white",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
        xaxis=dict(title="", showgrid=False),
        yaxis=dict(title="", gridcolor="#e5e7eb", zeroline=False),
        hovermode="x unified",
    )

    return chart


def build_rating_exposure_chart(rating_df: pd.DataFrame) -> go.Figure:
    chart = go.Figure()

    if rating_df.empty:
        return chart

    df = rating_df.copy()
    df["stars_label"] = df["stars"].fillna(0).astype(int).astype(str) + "★"
    df = df.sort_values("stars")

    chart.add_trace(go.Bar(
        x=df["stars_label"],
        y=df["total_debt"],
        name="Общий долг",
        marker_color="#2563eb",
    ))

    chart.add_trace(go.Bar(
        x=df["stars_label"],
        y=df["overdue_debt"],
        name="Просрочено",
        marker_color="#dc2626",
    ))

    chart.update_layout(
        height=320,
        margin=dict(l=20, r=20, t=40, b=20),
        paper_bgcolor="white",
        plot_bgcolor="white",
        barmode="group",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
        xaxis=dict(title="", showgrid=False),
        yaxis=dict(title="", gridcolor="#e5e7eb", zeroline=False),
        hovermode="x unified",
    )

    return chart