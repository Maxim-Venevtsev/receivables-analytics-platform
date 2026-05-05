from pathlib import Path
import sys

def find_latest_file(raw_dir: Path) -> Path:
    txt_files = list(raw_dir.glob("*.txt"))

    if not txt_files:
        raise FileNotFoundError("No TXT files found in data/raw")

    # берем самый свежий по дате изменения
    latest_file = max(txt_files, key=lambda p: p.stat().st_mtime)

    return latest_file

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw"

sys.path.append(str(PROJECT_ROOT))

from src.ingestion.parse_ascii import parse_receivables_txt
from src.ingestion.load_to_postgres import load_receivables_snapshot
from src.quality.validations import (
    validate_receivables_snapshot,
    raise_if_validation_errors,
    print_validation_warnings,
)

def main():
    source_file = find_latest_file(RAW_DIR)

    print(f"Using file: {source_file.name}")

    df, metadata = parse_receivables_txt(source_file)
    
    errors, warnings = validate_receivables_snapshot(df)
    print_validation_warnings(warnings)
    raise_if_validation_errors(errors)

    print("Parsed rows:", len(df))
    print("Metadata:", metadata)
    print(df.head())

    load_receivables_snapshot(df, metadata, source_file)

    print("Loaded to PostgreSQL successfully.")


if __name__ == "__main__":
    main()