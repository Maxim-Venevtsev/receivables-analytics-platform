import pandas as pd


def portfolio_denominator(
    branch_df: pd.DataFrame,
    *,
    branch_filter_active: bool,
) -> float:
    if branch_df.empty:
        return 0
    if branch_filter_active:
        return float(branch_df["total_debt"].sum())
    return float(branch_df["portfolio_total_debt"].iloc[0])


def overdue_portfolio_subtitle(
    overdue_debt: float,
    total_debt: float,
) -> str:
    return f"{overdue_share_percent(overdue_debt, total_debt):.1f}% портфеля"


def overdue_share_percent(
    overdue_debt: float,
    total_debt: float,
) -> float:
    return overdue_debt / total_debt * 100 if total_debt else 0
