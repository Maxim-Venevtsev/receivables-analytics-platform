from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw"

sys.path.append(str(PROJECT_ROOT))

from src.ingestion.parse_ascii import parse_receivables_txt
from src.ingestion.load_to_postgres import load_receivables_snapshot


SOURCE_FILE = RAW_DIR / "Челяб-Ирк-Каз_20.04.2029.txt"


def main():
    if not SOURCE_FILE.exists():
        raise FileNotFoundError(f"File not found: {SOURCE_FILE}")

    df, metadata = parse_receivables_txt(SOURCE_FILE)

    print("Parsed rows:", len(df))
    print("Metadata:", metadata)
    print(df.head())

    load_receivables_snapshot(df, metadata, SOURCE_FILE)

    print("Loaded to PostgreSQL successfully.")


if __name__ == "__main__":
    main()