from pathlib import Path
import os

import yaml
from dotenv import load_dotenv
from sqlalchemy import create_engine, text


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

RULES_PATH = PROJECT_ROOT / "configs" / "client_rating_rules.yaml"


def get_engine():
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    host = os.getenv("DB_HOST")
    port = os.getenv("DB_PORT")
    db = os.getenv("DB_NAME")

    url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"
    return create_engine(url)


def load_rules() -> dict:
    with RULES_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main():
    rules = load_rules()
    engine = get_engine()

    rating_window_days = rules["rating_window_days"]
    min_full_confidence_snapshot_days = rules["min_full_confidence_snapshot_days"]

    with engine.begin() as conn:
        conn.execute(text("DELETE FROM core.client_rating_rules"))
        conn.execute(text("DELETE FROM core.client_rating_config"))

        conn.execute(
            text("""
                INSERT INTO core.client_rating_config (
                    id,
                    rating_window_days,
                    min_full_confidence_snapshot_days,
                    updated_at
                )
                VALUES (
                    1,
                    :rating_window_days,
                    :min_full_confidence_snapshot_days,
                    now()
                )
            """),
            {
                "rating_window_days": rating_window_days,
                "min_full_confidence_snapshot_days": min_full_confidence_snapshot_days,
            },
        )

        for stars, rule in rules["ratings"].items():
            conn.execute(
                text("""
                    INSERT INTO core.client_rating_rules (
                        stars,
                        label,
                        max_overdue_occurrence_ratio,
                        max_avg_overdue_share_pct,
                        max_max_days_overdue,
                        updated_at
                    )
                    VALUES (
                        :stars,
                        :label,
                        :max_overdue_occurrence_ratio,
                        :max_avg_overdue_share_pct,
                        :max_max_days_overdue,
                        now()
                    )
                """),
                {
                    "stars": int(stars),
                    "label": rule["label"],
                    "max_overdue_occurrence_ratio": rule.get("max_overdue_occurrence_ratio"),
                    "max_avg_overdue_share_pct": rule.get("max_avg_overdue_share_pct"),
                    "max_max_days_overdue": rule.get("max_max_days_overdue"),
                },
            )

    print("Client rating rules loaded successfully")
    print(f"Rules file: {RULES_PATH}")
    print(f"Rating window days: {rating_window_days}")
    print(f"Min full confidence snapshot days: {min_full_confidence_snapshot_days}")
    print(f"Ratings loaded: {len(rules['ratings'])}")


if __name__ == "__main__":
    main()