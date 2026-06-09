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
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
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
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
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
            line=dict(color=GREEN_DEBT_BUCKET_COLORS[bucket], width=0),
            fillcolor=GREEN_DEBT_BUCKET_COLORS[bucket],
        ))

    chart.update_layout(
        height=height,
        margin=dict(l=20, r=20, t=40, b=20),
        paper_bgcolor="white",
        plot_bgcolor="white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
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
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
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
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
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
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
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
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(title="", showgrid=False),
        yaxis=dict(title="", gridcolor="#e5e7eb", zeroline=False),
        hovermode="x unified",
    )

    return chart


def build_rating_migration_chart(summary_df: pd.DataFrame) -> go.Figure:
    chart = go.Figure()

    if summary_df.empty:
        return chart

    df = summary_df.copy().sort_values("sort_order")

    chart.add_trace(go.Bar(
        x=df["period_label"],
        y=df["upgraded_clients"],
        name="Повысились",
        marker_color="#22c55e",
    ))

    chart.add_trace(go.Bar(
        x=df["period_label"],
        y=df["downgraded_clients"],
        name="Понизились",
        marker_color="#dc2626",
    ))

    chart.add_trace(go.Bar(
        x=df["period_label"],
        y=df["unchanged_clients"],
        name="Без изменений",
        marker_color="#94a3b8",
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
        yaxis=dict(title="Клиентов", gridcolor="#e5e7eb", zeroline=False),
        hovermode="x unified",
    )

    return chart


CLIENT_RISK_COLORS = {
    "GREEN": "#22c55e",
    "ORANGE": "#f97316",
    "RED": "#dc2626",
}


CLIENT_RISK_LABELS = {
    "GREEN": "Без просрочки",
    "ORANGE": "Есть просрочка",
    "RED": "Высокая просрочка",
}


HIDDEN_RISK_COLORS = {
    "LOW": "#94a3b8",
    "MEDIUM": "#f59e0b",
    "HIGH": "#ef4444",
    "CRITICAL": "#7f1d1d",
}


HIDDEN_RISK_LABELS = {
    "LOW": "Низкий скрытый риск",
    "MEDIUM": "Есть 90+ непросрочено",
    "HIGH": "Высокая доля 90+",
    "CRITICAL": "120+ непросрочено",
}


def _bubble_sizeref(df: pd.DataFrame, size_column: str, max_marker_size: int = 70) -> float:
    if df.empty or size_column not in df.columns:
        return 1

    max_size = df[size_column].max()

    if pd.isna(max_size) or max_size <= 0:
        return 1

    return 2.0 * float(max_size) / (max_marker_size ** 2)


def _format_amount(value) -> str:
    if pd.isna(value):
        return "0"
    return f"{float(value):,.0f}".replace(",", " ")


def build_client_risk_bubble_chart(df: pd.DataFrame) -> go.Figure:
    chart = go.Figure()

    if df.empty:
        return chart

    data = df.copy()
    data = data[
        data["x_payment_term_days"].notna()
        & data["y_rating"].notna()
        & data["bubble_size"].notna()
    ]

    if data.empty:
        return chart

    sizeref = _bubble_sizeref(data, "bubble_size")

    for risk_level in ["GREEN", "ORANGE", "RED"]:
        group = data[data["color_group"] == risk_level].copy()

        if group.empty:
            continue

        chart.add_trace(go.Scatter(
            x=group["x_payment_term_days"],
            y=group["y_rating"],
            mode="markers",
            name=CLIENT_RISK_LABELS.get(risk_level, risk_level),
            marker=dict(
                size=group["bubble_size"],
                sizemode="area",
                sizeref=sizeref,
                sizemin=6,
                color=CLIENT_RISK_COLORS.get(risk_level, "#94a3b8"),
                opacity=0.68,
                line=dict(width=1, color="white"),
            ),
            customdata=group[[
                "client_id",
                "client_name",
                "client_group",
                "total_debt",
                "overdue_debt",
                "overdue_share_pct",
                "max_payment_term_days",
            ]],
            hovertemplate=(
                "<b>%{customdata[1]}</b><br>"
                "Клиент ID: %{customdata[0]}<br>"
                "Филиал: %{customdata[2]}<br>"
                "Рейтинг: %{y}★<br>"
                "Средневзвешенная отсрочка: %{x:.1f} дней<br>"
                "Макс. отсрочка: %{customdata[6]} дней<br>"
                "Общий долг: %{customdata[3]:,.0f}<br>"
                "Просрочено: %{customdata[4]:,.0f}<br>"
                "Доля просрочки: %{customdata[5]:.1f}%"
                "<extra></extra>"
            ),
        ))

    chart.update_layout(
        height=460,
        margin=dict(l=20, r=20, t=40, b=40),
        paper_bgcolor="white",
        plot_bgcolor="white",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
        xaxis=dict(
            title="Средневзвешенная отсрочка, дней",
            gridcolor="#e5e7eb",
            zeroline=False,
        ),
        yaxis=dict(
            title="Рейтинг клиента",
            range=[0.5, 5.5],
            tickmode="array",
            tickvals=[1, 2, 3, 4, 5],
            ticktext=["1★", "2★", "3★", "4★", "5★"],
            gridcolor="#e5e7eb",
            zeroline=False,
        ),
        hovermode="closest",
    )

    return chart


def build_hidden_risk_bubble_chart(df: pd.DataFrame) -> go.Figure:
    chart = go.Figure()

    if df.empty:
        return chart

    data = df.copy()
    data = data[
        data["x_green_90_share_pct"].notna()
        & data["y_rating"].notna()
        & data["bubble_size"].notna()
    ]

    if data.empty:
        return chart

    sizeref = _bubble_sizeref(data, "bubble_size")

    for risk_level in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]:
        group = data[data["color_group"] == risk_level].copy()

        if group.empty:
            continue

        chart.add_trace(go.Scatter(
            x=group["x_green_90_share_pct"],
            y=group["y_rating"],
            mode="markers",
            name=HIDDEN_RISK_LABELS.get(risk_level, risk_level),
            marker=dict(
                size=group["bubble_size"],
                sizemode="area",
                sizeref=sizeref,
                sizemin=6,
                color=HIDDEN_RISK_COLORS.get(risk_level, "#94a3b8"),
                opacity=0.68,
                line=dict(width=1, color="white"),
            ),
            customdata=group[[
                "client_id",
                "client_name",
                "client_group",
                "total_debt",
                "green_90_plus_debt",
                "green_120_plus_debt",
                "green_90_plus_share_of_total_pct",
                "max_payment_term_days",
            ]],
            hovertemplate=(
                "<b>%{customdata[1]}</b><br>"
                "Клиент ID: %{customdata[0]}<br>"
                "Филиал: %{customdata[2]}<br>"
                "Рейтинг: %{y}★<br>"
                "Доля 90+ непросрочено: %{x:.1f}%<br>"
                "Макс. отсрочка: %{customdata[7]} дней<br>"
                "Общий долг: %{customdata[3]:,.0f}<br>"
                "90+ непросрочено: %{customdata[4]:,.0f}<br>"
                "120+ непросрочено: %{customdata[5]:,.0f}<br>"
                "90+ / портфель клиента: %{customdata[6]:.1f}%"
                "<extra></extra>"
            ),
        ))

    chart.update_layout(
        height=460,
        margin=dict(l=20, r=20, t=40, b=40),
        paper_bgcolor="white",
        plot_bgcolor="white",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
        xaxis=dict(
            title="Доля 90+ непросроченной задолженности, %",
            gridcolor="#e5e7eb",
            zeroline=False,
        ),
        yaxis=dict(
            title="Рейтинг клиента",
            range=[0.5, 5.5],
            tickmode="array",
            tickvals=[1, 2, 3, 4, 5],
            ticktext=["1★", "2★", "3★", "4★", "5★"],
            gridcolor="#e5e7eb",
            zeroline=False,
        ),
        hovermode="closest",
    )

    return chart

def build_top_client_risk_bubble_chart(df: pd.DataFrame) -> go.Figure:
    chart = go.Figure()

    if df.empty:
        return chart

    data = (
        df.copy()
        .sort_values("bubble_size", ascending=False)
        .head(20)
    )

    data = data[
        data["x_payment_term_days"].notna()
        & data["y_rating"].notna()
        & data["bubble_size"].notna()
    ]

    if data.empty:
        return chart

    sizeref = _bubble_sizeref(data, "bubble_size", max_marker_size=90)

    for risk_level in ["GREEN", "ORANGE", "RED"]:
        group = data[data["color_group"] == risk_level].copy()

        if group.empty:
            continue

        chart.add_trace(go.Scatter(
            x=group["x_payment_term_days"],
            y=group["y_rating"],
            mode="markers+text",
            name=CLIENT_RISK_LABELS.get(risk_level, risk_level),
            text=group["client_name"],
            textposition="top center",
            textfont=dict(size=10),
            marker=dict(
                size=group["bubble_size"],
                sizemode="area",
                sizeref=sizeref,
                sizemin=10,
                color=CLIENT_RISK_COLORS.get(risk_level, "#94a3b8"),
                opacity=0.68,
                line=dict(width=1, color="white"),
            ),
            customdata=group[[
                "client_id",
                "client_name",
                "client_group",
                "total_debt",
                "overdue_debt",
                "overdue_share_pct",
                "max_payment_term_days",
            ]],
            hovertemplate=(
                "<b>%{customdata[1]}</b><br>"
                "Клиент ID: %{customdata[0]}<br>"
                "Филиал: %{customdata[2]}<br>"
                "Рейтинг: %{y}★<br>"
                "Средневзвешенная отсрочка: %{x:.1f} дней<br>"
                "Макс. отсрочка: %{customdata[6]} дней<br>"
                "Общий долг: %{customdata[3]:,.0f}<br>"
                "Просрочено: %{customdata[4]:,.0f}<br>"
                "Доля просрочки: %{customdata[5]:.1f}%"
                "<extra></extra>"
            ),
        ))

    chart.update_layout(
        height=520,
        margin=dict(l=20, r=20, t=40, b=40),
        paper_bgcolor="white",
        plot_bgcolor="white",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
        xaxis=dict(
            title="Средневзвешенная отсрочка, дней",
            gridcolor="#e5e7eb",
            zeroline=False,
        ),
        yaxis=dict(
            title="Рейтинг клиента",
            range=[0.5, 5.5],
            tickmode="array",
            tickvals=[1, 2, 3, 4, 5],
            ticktext=["1★", "2★", "3★", "4★", "5★"],
            gridcolor="#e5e7eb",
            zeroline=False,
        ),
        hovermode="closest",
    )

    return chart