from pathlib import Path
import os

from dotenv import load_dotenv

from src.ingestion.parse_ascii import parse_receivables_txt
from src.ingestion.load_to_postgres import load_receivables_snapshot


PROJECT_ROOT = Path(__file__).resolve().parents[2]

load_dotenv(PROJECT_ROOT / ".env")

RAW_DIR = PROJECT_ROOT / os.getenv("RAW_DIR", "data/raw")

def main():
    files = sorted(RAW_DIR.glob("*.txt"))

    if not files:
        print(f"No TXT files found in {RAW_DIR}")
        return

    print(f"Found {len(files)} TXT files")

    for path in files:
        try:
            print("-" * 60)
            print(f"Loading: {path.name}")

            df, metadata = parse_receivables_txt(path)

            print(f"Rows parsed: {len(df)}")
            print(f"Report date: {metadata['report_generated_date']}")
            print(f"Debt as-of param: {metadata['debt_asof_date_param']}")

            load_receivables_snapshot(df, metadata, path)

            print(f"SUCCESS: {path.name}")

        except Exception as e:
            print(f"ERROR: {path.name}")
            print(str(e))

    print("-" * 60)
    print("INGESTION FINISHED")


if __name__ == "__main__":
    main()