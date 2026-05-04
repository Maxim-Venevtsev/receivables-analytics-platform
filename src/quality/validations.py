import pandas as pd


REQUIRED_COLUMNS = [
    "parent_org_id",
    "client_id",
    "client_name",
    "invoice_date",
    "invoice_amount",
    "currency_code",
    "due_date",
    "analytics_type",
    "client_group",
]


ALLOWED_CURRENCIES = {"RUR", "EUR"}


def validate_receivables_snapshot(df: pd.DataFrame) -> tuple[list[str], list[str]]:
    errors = []
    warnings = []

    if df.empty:
        errors.append("Parsed dataframe is empty.")
        return errors, warnings

    missing_columns = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_columns:
        errors.append(f"Missing required columns: {missing_columns}")
        return errors, warnings

    for col in REQUIRED_COLUMNS:
        missing_count = df[col].isna().sum()
        if missing_count > 0:
            errors.append(f"Column '{col}' has {missing_count} missing values.")

    invalid_currencies = sorted(set(df["currency_code"].dropna()) - ALLOWED_CURRENCIES)
    if invalid_currencies:
        errors.append(f"Invalid currencies found: {invalid_currencies}")

    negative_terms = df[df["payment_term_days"] < 0]
    if not negative_terms.empty:
        errors.append(
            f"Found {len(negative_terms)} rows where due_date is earlier than invoice_date."
        )

    very_long_terms = df[df["payment_term_days"] > 120]
    if not very_long_terms.empty:
        warnings.append(
            f"Found {len(very_long_terms)} rows with payment term > 120 days."
        )

    return errors, warnings


def print_validation_warnings(warnings: list[str]) -> None:
    if not warnings:
        return

    print("Validation warnings:")
    for warning in warnings:
        print(f"- {warning}")


def raise_if_validation_errors(errors: list[str]) -> None:
    if not errors:
        return

    message = "Validation failed:\n" + "\n".join(f"- {error}" for error in errors)
    raise ValueError(message)