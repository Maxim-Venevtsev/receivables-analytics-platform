from pathlib import Path
import os
import random

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

OUTPUT_DIR = PROJECT_ROOT / "data" / "demo"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_CSV = OUTPUT_DIR / "receivables_snapshot_demo.csv"
OUTPUT_XLSX = OUTPUT_DIR / "receivables_snapshot_demo.xlsx"

engine = create_engine(
    f"postgresql+psycopg2://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@"
    f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)


CLIENT_NAMES = [
    "NordAuto", "Prime Service", "Vector Trade", "AutoPoint", "TransitOil",
    "MotorHub", "Velocity Parts", "DriveLine", "East Motors", "City Truck",
    "Titan Auto", "Progress Trade", "Global Parts", "Alliance Service", "Sigma Auto",
]

BRANCH_NAMES = [
    "BRANCH_VOLGA",
    "BRANCH_URAL",
    "BRANCH_CENTER",
    "BRANCH_SIBERIA",
    "BRANCH_SOUTH",
]

ANALYTICS_TYPES = [
    "STANDARD",
    "CORPORATE",
    "FLEET",
    "WHOLESALE",
    "REGIONAL",
]


def synthetic_number(prefix: str, index: int) -> str:
    return f"{prefix}{index:07d}"


def main():
    print("Loading normalized snapshot from PostgreSQL...")

    df = pd.read_sql(
        text("""
            SELECT *
            FROM core.v_invoice_detail
            ORDER BY report_generated_date, client_id, due_date
        """),
        engine,
    )

    print(f"Loaded rows: {len(df)}")

    if df.empty:
        raise ValueError("No data found in core.v_invoice_detail")

    unique_clients = sorted(df["client_id"].dropna().unique())
    unique_parent_orgs = sorted(df["parent_org_id"].dropna().unique())
    unique_branches = sorted(df["client_group"].dropna().unique())

    client_id_mapping = {
        old_id: 10000 + i
        for i, old_id in enumerate(unique_clients, start=1)
    }

    client_name_mapping = {
        old_id: f"{CLIENT_NAMES[i % len(CLIENT_NAMES)]}_{i + 1:03d}"
        for i, old_id in enumerate(unique_clients)
    }

    parent_mapping = {
        old_id: f"HOLDING_{i:03d}"
        for i, old_id in enumerate(unique_parent_orgs, start=1)
    }

    branch_mapping = {
        old_branch: BRANCH_NAMES[i % len(BRANCH_NAMES)]
        for i, old_branch in enumerate(unique_branches)
    }

    df["client_name"] = df["client_id"].map(client_name_mapping)
    df["client_id"] = df["client_id"].map(client_id_mapping)

    df["parent_org_id"] = df["parent_org_id"].map(parent_mapping)
    df["client_group"] = df["client_group"].map(branch_mapping)

    if "analytics_type" in df.columns:
        df["analytics_type"] = [
            random.choice(ANALYTICS_TYPES)
            for _ in range(len(df))
        ]

    if "order_number" in df.columns:
        df["order_number"] = [
            synthetic_number("ORD", i)
            for i in range(1, len(df) + 1)
        ]

    if "print_invoice_number" in df.columns:
        df["print_invoice_number"] = [
            synthetic_number("INV", i)
            for i in range(1, len(df) + 1)
        ]

    if "system_invoice_number" in df.columns:
        df["system_invoice_number"] = [
            synthetic_number("SYS", i)
            for i in range(1, len(df) + 1)
        ]

    if "source_file_name" in df.columns:
        df["source_file_name"] = "demo_receivables_snapshot.txt"

    df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    df.to_excel(OUTPUT_XLSX, index=False)

    print()
    print("Sanitized demo dataset created:")
    print(f"- {OUTPUT_CSV}")
    print(f"- {OUTPUT_XLSX}")


if __name__ == "__main__":
    main()