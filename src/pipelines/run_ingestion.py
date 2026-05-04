from pathlib import Path
import re
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw"

SOURCE_FILE = RAW_DIR / "Челяб-Ирк-Каз_20.04.2029.txt"


def parse_russian_number(value):
    if pd.isna(value):
        return None

    value = str(value).strip()

    if value == "":
        return None

    value = value.replace(" ", "").replace(",", ".")

    try:
        return float(value)
    except ValueError:
        return None


def parse_date(value):
    if pd.isna(value):
        return None

    value = str(value).strip()

    if value == "":
        return None

    return pd.to_datetime(value, format="%d.%m.%Y", errors="coerce").date()


def read_txt_file(path: Path) -> list[str]:
    for encoding in ["cp1251", "utf-8-sig", "utf-8"]:
        try:
            return path.read_text(encoding=encoding).splitlines()
        except UnicodeDecodeError:
            continue

    raise UnicodeDecodeError("Could not read file with cp1251/utf-8 encodings")


def extract_metadata(lines: list[str]) -> dict:
    metadata = {
        "report_generated_date": None,
        "report_generated_time": None,
        "debt_asof_date_param": None,
        "client_group_filter": None,
        "analytics_filter": None,
    }

    for line in lines[:20]:
        parts = [p.strip() for p in line.split("\t")]

        if line.startswith("ООО"):
            # Пример:
            # ООО "АРС" ... 20.04.2026 14:46:58 Страница 1
            for part in parts:
                if re.match(r"\d{2}\.\d{2}\.\d{4}", part):
                    metadata["report_generated_date"] = parse_date(part)
                if re.match(r"\d{2}:\d{2}:\d{2}", part):
                    metadata["report_generated_time"] = part

        if parts[0] == "Группа клиентов":
            metadata["client_group_filter"] = parts[1] if len(parts) > 1 else None

        if parts[0] == "Для целей НО":
            metadata["analytics_filter"] = parts[1] if len(parts) > 1 else None

        if parts[0] == "Задолженность на дату":
            metadata["debt_asof_date_param"] = parse_date(parts[1]) if len(parts) > 1 else None

    return metadata


def parse_receivables_txt(path: Path) -> tuple[pd.DataFrame, dict]:
    lines = read_txt_file(path)
    metadata = extract_metadata(lines)

    rows = []

    for line in lines:
        parts = [p.strip() for p in line.split("\t")]

        # Нужные строки начинаются с кода вышестоящей и кода клиента
        if len(parts) < 15:
            continue

        if not parts[0].isdigit():
            continue

        if not parts[1].isdigit():
            continue

        rows.append(parts[:15])

    columns = [
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
    ]

    df = pd.DataFrame(rows, columns=columns)

    df["invoice_date"] = df["invoice_date"].apply(parse_date)
    df["due_date"] = df["due_date"].apply(parse_date)

    df["invoice_amount"] = df["invoice_amount"].apply(parse_russian_number)
    df["overdue_amount_rub"] = df["overdue_amount_rub"].apply(parse_russian_number)
    df["overdue_amount_eur"] = df["overdue_amount_eur"].apply(parse_russian_number)

    df["days_overdue_report_param"] = pd.to_numeric(
        df["days_overdue_report_param"],
        errors="coerce"
    ).astype("Int64")

    df["source_file_name"] = path.name
    df["report_generated_date"] = metadata["report_generated_date"]
    df["report_generated_time"] = metadata["report_generated_time"]
    df["debt_asof_date_param"] = metadata["debt_asof_date_param"]

    # Наши реальные расчетные поля
    report_date = metadata["report_generated_date"]

    df["payment_term_days"] = (
        pd.to_datetime(df["due_date"]) - pd.to_datetime(df["invoice_date"])
    ).dt.days

    df["days_overdue_real"] = (
        pd.to_datetime(report_date) - pd.to_datetime(df["due_date"])
    ).dt.days.clip(lower=0)

    df["days_until_due_real"] = (
        pd.to_datetime(df["due_date"]) - pd.to_datetime(report_date)
    ).dt.days

    df["is_overdue_real"] = df["days_overdue_real"] > 0
    df["is_due_today"] = df["days_until_due_real"] == 0
    df["is_due_in_3_days"] = df["days_until_due_real"].between(0, 3)
    df["is_due_in_7_days"] = df["days_until_due_real"].between(0, 7)
    df["is_negative_document"] = df["invoice_amount"] < 0

    return df, metadata


def get_engine():
    load_dotenv(PROJECT_ROOT / ".env")

    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    host = os.getenv("DB_HOST")
    port = os.getenv("DB_PORT")
    db = os.getenv("DB_NAME")

    url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"
    return create_engine(url)


def load_to_postgres(df: pd.DataFrame, metadata: dict, source_path: Path):
    engine = get_engine()

    with engine.begin() as conn:
        # Чтобы можно было безопасно перезапускать загрузку этого же файла
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


def main():
    if not SOURCE_FILE.exists():
        raise FileNotFoundError(f"File not found: {SOURCE_FILE}")

    df, metadata = parse_receivables_txt(SOURCE_FILE)

    print("Parsed rows:", len(df))
    print("Metadata:", metadata)
    print(df.head())

    load_to_postgres(df, metadata, SOURCE_FILE)

    print("Loaded to PostgreSQL successfully.")


if __name__ == "__main__":
    main()