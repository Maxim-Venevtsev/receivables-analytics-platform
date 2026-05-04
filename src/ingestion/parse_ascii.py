from pathlib import Path
import re
import pandas as pd


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

    parsed = pd.to_datetime(value, format="%d.%m.%Y", errors="coerce")

    if pd.isna(parsed):
        return None

    return parsed.date()


def read_txt_file(path: Path) -> list[str]:
    for encoding in ["cp1251", "utf-8-sig", "utf-8"]:
        try:
            return path.read_text(encoding=encoding).splitlines()
        except UnicodeDecodeError:
            continue

    raise UnicodeError("Could not read file with cp1251/utf-8 encodings")


def extract_metadata(lines: list[str]) -> dict:
    metadata = {
        "report_generated_date": None,
        "report_generated_time": None,
        "debt_asof_date_param": None,
        "client_group_filter": None,
        "analytics_filter": None,
    }

    for line in lines[:30]:
        parts = [p.strip() for p in line.split("\t")]

        if line.startswith("ООО"):
            for part in parts:
                if re.match(r"\d{2}\.\d{2}\.\d{4}", part):
                    metadata["report_generated_date"] = parse_date(part)
                if re.match(r"\d{2}:\d{2}:\d{2}", part):
                    metadata["report_generated_time"] = part

        if len(parts) >= 2 and parts[0] == "Группа клиентов":
            metadata["client_group_filter"] = parts[1]

        if len(parts) >= 2 and parts[0] == "Для целей НО":
            metadata["analytics_filter"] = parts[1]

        if len(parts) >= 2 and parts[0] == "Задолженность на дату":
            metadata["debt_asof_date_param"] = parse_date(parts[1])

    return metadata


def parse_receivables_txt(path: Path) -> tuple[pd.DataFrame, dict]:
    lines = read_txt_file(path)
    metadata = extract_metadata(lines)

    rows = []

    for line in lines:
        parts = [p.strip() for p in line.split("\t")]

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