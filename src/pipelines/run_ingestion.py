from pathlib import Path
import sys


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


def find_txt_files(raw_dir: Path) -> list[Path]:
    txt_files = sorted(raw_dir.glob("*.txt"))

    if not txt_files:
        raise FileNotFoundError("No TXT files found in data/raw")

    return txt_files


def ingest_one_file(source_file: Path) -> None:
    print("=" * 80)
    print(f"Using file: {source_file.name}")

    df, metadata = parse_receivables_txt(source_file)

    errors, warnings = validate_receivables_snapshot(df)
    print_validation_warnings(warnings)
    raise_if_validation_errors(errors)

    print("Parsed rows:", len(df))
    print("Metadata:", metadata)

    load_receivables_snapshot(df, metadata, source_file)

    print("Loaded to PostgreSQL successfully.")


def main():
    txt_files = find_txt_files(RAW_DIR)

    print(f"Found TXT files: {len(txt_files)}")

    for source_file in txt_files:
        ingest_one_file(source_file)

    print("=" * 80)
    print("Batch ingestion completed successfully.")


if __name__ == "__main__":
    main()