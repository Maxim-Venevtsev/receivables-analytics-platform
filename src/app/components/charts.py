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