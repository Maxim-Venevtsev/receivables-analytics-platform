CREATE TABLE IF NOT EXISTS core.client_rating_config (
    id integer PRIMARY KEY DEFAULT 1,
    rating_window_days integer NOT NULL,
    min_full_confidence_snapshot_days integer NOT NULL,
    updated_at timestamp DEFAULT now()
);

CREATE TABLE IF NOT EXISTS core.client_rating_rules (
    stars integer PRIMARY KEY,
    label text NOT NULL,
    max_overdue_occurrence_ratio numeric,
    max_avg_overdue_share_pct numeric,
    max_max_days_overdue integer,
    updated_at timestamp DEFAULT now()
);