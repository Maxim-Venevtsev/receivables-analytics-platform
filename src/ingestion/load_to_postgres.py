from pathlib import Path
import os
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def get_engine():
    load_dotenv(PROJECT_ROOT / ".env")

    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    host = os.getenv("DB_HOST")
    port = os.getenv("DB_PORT")
    db = os.getenv("DB_NAME")

    url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"
    return create_engine(url)


def load_receivables_snapshot(df: pd.DataFrame, metadata: dict, source_path: Path):
    engine = get_engine()

    with engine.begin() as conn:
        conn.execute(
            text("""
                DELETE FROM core.receivables_snapshot_fact
                WHERE source_file_name = :source_file_name
            """),
            {"source_file_name": source_path.name}
        )

        conn.execute(
            text("""
                DELETE FROM raw.snapshot_loads
                WHERE source_file_name = :source_file_name
            """),
            {"source_file_name": source_path.name}
        )

        result = conn.execute(
            text("""
                INSERT INTO raw.snapshot_loads (
                    source_file_name,
                    source_file_path,
                    report_generated_date,
                    report_generated_time,
                    debt_asof_date_param,
                    client_group_filter,
                    analytics_filter,
                    row_count_loaded,
                    status
                )
                VALUES (
                    :source_file_name,
                    :source_file_path,
                    :report_generated_date,
                    :report_generated_time,
                    :debt_asof_date_param,
                    :client_group_filter,
                    :analytics_filter,
                    :row_count_loaded,
                    'loaded'
                )
                RETURNING load_id
            """),
            {
                "source_file_name": source_path.name,
                "source_file_path": str(source_path),
                "report_generated_date": metadata["report_generated_date"],
                "report_generated_time": metadata["report_generated_time"],
                "debt_asof_date_param": metadata["debt_asof_date_param"],
                "client_group_filter": metadata["client_group_filter"],
                "analytics_filter": metadata["analytics_filter"],
                "row_count_loaded": len(df),
            }
        )

        load_id = result.scalar()

    df = df.copy()
    df["load_id"] = load_id

    ordered_columns = [
        "load_id",
        "source_file_name",
        "report_generated_date",
        "report_generated_time",
        "debt_asof_date_param",
        "parent_org_id",
        "client_id",
        "client_name",
        "invoice_date",
        "order_number",
        "print_invoice_number",
        "system_invoice_number",
        "analytics_type",
        "invoice_amount",
        "currency_code",
        "due_date",
        "days_overdue_report_param",
        "overdue_amount_rub",
        "overdue_amount_eur",
        "client_group",
        "payment_term_days",
        "days_overdue_real",
        "days_until_due_real",
        "is_overdue_real",
        "is_due_today",
        "is_due_in_3_days",
        "is_due_in_7_days",
        "is_negative_document",
    ]

    df[ordered_columns].to_sql(
        name="receivables_snapshot_fact",
        con=engine,
        schema="core",
        if_exists="append",
        index=False,
        method="multi"
    )