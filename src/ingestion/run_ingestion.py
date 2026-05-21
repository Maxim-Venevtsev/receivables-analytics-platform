from pathlib import Path
import os
import shutil
from datetime import datetime

from dotenv import load_dotenv
from sqlalchemy import text

from src.ingestion.parse_ascii import parse_receivables_txt
from src.ingestion.load_to_postgres import load_receivables_snapshot, get_engine


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

RAW_DIR = PROJECT_ROOT / os.getenv("RAW_DIR", "data/raw")
ARCHIVE_DIR = PROJECT_ROOT / os.getenv("ARCHIVE_DIR", "data/archive")
FAILED_DIR = PROJECT_ROOT / os.getenv("FAILED_DIR", "data/failed")


def ensure_dirs():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    FAILED_DIR.mkdir(parents=True, exist_ok=True)


def already_loaded(source_file_name: str) -> bool:
    engine = get_engine()

    with engine.connect() as conn:
        result = conn.execute(
            text("""
                SELECT EXISTS (
                    SELECT 1
                    FROM raw.snapshot_loads
                    WHERE source_file_name = :source_file_name
                      AND status = 'loaded'
                )
            """),
            {"source_file_name": source_file_name},
        )

        return bool(result.scalar())


def safe_move(source_path: Path, target_dir: Path) -> Path:
    target_path = target_dir / source_path.name

    if target_path.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target_path = target_dir / f"{source_path.stem}_{timestamp}{source_path.suffix}"

    shutil.move(str(source_path), str(target_path))
    return target_path


def main():
    ensure_dirs()

    files = sorted(RAW_DIR.glob("*.txt"))

    if not files:
        print(f"No TXT files found in {RAW_DIR}")
        return

    print(f"Found {len(files)} TXT files")
    print(f"RAW_DIR: {RAW_DIR}")
    print(f"ARCHIVE_DIR: {ARCHIVE_DIR}")
    print(f"FAILED_DIR: {FAILED_DIR}")

    loaded_count = 0
    skipped_count = 0
    failed_count = 0

    for path in files:
        print("-" * 60)
        print(f"Processing: {path.name}")

        try:
            if already_loaded(path.name):
                print(f"SKIPPED: already loaded: {path.name}")
                safe_move(path, ARCHIVE_DIR)
                skipped_count += 1
                continue

            df, metadata = parse_receivables_txt(path)

            print(f"Rows parsed: {len(df)}")
            print(f"Report date: {metadata['report_generated_date']}")
            print(f"Debt as-of param: {metadata['debt_asof_date_param']}")

            load_receivables_snapshot(df, metadata, path)

            archived_path = safe_move(path, ARCHIVE_DIR)

            print(f"SUCCESS: {path.name}")
            print(f"Archived to: {archived_path}")

            loaded_count += 1

        except Exception as e:
            failed_path = safe_move(path, FAILED_DIR)

            print(f"ERROR: {path.name}")
            print(str(e))
            print(f"Moved to failed: {failed_path}")

            failed_count += 1

    print("-" * 60)
    print("INGESTION FINISHED")
    print(f"Loaded: {loaded_count}")
    print(f"Skipped: {skipped_count}")
    print(f"Failed: {failed_count}")


if __name__ == "__main__":
    main()