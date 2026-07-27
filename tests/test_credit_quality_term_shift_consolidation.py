from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
FORWARD = ROOT / "sql" / "ddl" / "038_consolidate_credit_quality_term_shift.sql"
ROLLBACK = ROOT / "sql" / "rollback" / "038_consolidate_credit_quality_term_shift.sql"


def aggregate_term_shifts(rows):
    values = [
        (
            0 if row.get("term_shift_count") is None else row["term_shift_count"],
            0
            if row.get("current_term_delta_days") is None
            else row["current_term_delta_days"],
        )
        for row in rows
    ]
    if not values:
        return (0, 0, 0, 0, 0, 0)
    counts = [value[0] for value in values]
    deltas = [value[1] for value in values]
    return (
        sum(counts),
        max(counts),
        sum(deltas),
        max(deltas),
        sum(value >= 2 for value in counts),
        sum(value >= 3 for value in counts),
    )


@pytest.mark.parametrize(
    ("rows", "expected"),
    [
        ([], (0, 0, 0, 0, 0, 0)),
        ([{"term_shift_count": 1, "current_term_delta_days": 5}], (1, 1, 5, 5, 0, 0)),
        ([{"term_shift_count": 2, "current_term_delta_days": 8}], (2, 2, 8, 8, 1, 0)),
        ([{"term_shift_count": 3, "current_term_delta_days": 13}], (3, 3, 13, 13, 1, 1)),
        (
            [
                {"term_shift_count": 1, "current_term_delta_days": 5},
                {"term_shift_count": 2, "current_term_delta_days": 8},
                {"term_shift_count": 4, "current_term_delta_days": 21},
            ],
            (7, 4, 34, 21, 2, 1),
        ),
        (
            [
                {"term_shift_count": None, "current_term_delta_days": None},
                {},
            ],
            (0, 0, 0, 0, 0, 0),
        ),
    ],
)
def test_term_shift_fixture_semantics(rows, expected):
    assert aggregate_term_shifts(rows) == expected


def points(value, thresholds):
    return max((score for threshold, score in thresholds if value >= threshold), default=0)


@pytest.mark.parametrize(
    ("value", "expected"),
    [(0, 0), (1, 0), (2, 1), (3, 1), (4, 2), (5, 2), (6, 3)],
)
def test_total_shift_severity_boundaries(value, expected):
    assert points(value, [(2, 1), (4, 2), (6, 3)]) == expected


@pytest.mark.parametrize(
    ("metric", "value", "expected"),
    [
        ("max_invoice", 1, 0),
        ("max_invoice", 2, 1),
        ("max_invoice", 3, 2),
        ("repeated_invoices", 1, 0),
        ("repeated_invoices", 2, 1),
        ("repeated_invoices", 4, 2),
    ],
)
def test_repeated_shift_severity_boundaries(metric, value, expected):
    rules = {
        "max_invoice": [(2, 1), (3, 2)],
        "repeated_invoices": [(2, 1), (4, 2)],
    }
    assert points(value, rules[metric]) == expected


@pytest.mark.parametrize(
    ("thresholds", "boundary", "expected"),
    [
        ([(45, 1), (60, 2), (90, 3)], 45, 1),
        ([(45, 1), (60, 2), (90, 3)], 60, 2),
        ([(45, 1), (60, 2), (90, 3)], 90, 3),
        ([(90, 1), (120, 2)], 90, 1),
        ([(90, 1), (120, 2)], 120, 2),
        ([(10, 1), (25, 2), (50, 3)], 10, 1),
        ([(10, 1), (25, 2), (50, 3)], 25, 2),
        ([(10, 1), (25, 2), (50, 3)], 50, 3),
        ([(1, 2)], 1, 2),
        ([(2, 1), (4, 2), (6, 3)], 2, 1),
        ([(2, 1), (4, 2), (6, 3)], 4, 2),
        ([(2, 1), (4, 2), (6, 3)], 6, 3),
        ([(2, 1), (3, 2)], 2, 1),
        ([(2, 1), (3, 2)], 3, 2),
        ([(2, 1), (4, 2)], 2, 1),
        ([(2, 1), (4, 2)], 4, 2),
    ],
)
def test_every_configured_severity_threshold_boundary(thresholds, boundary, expected):
    assert points(boundary - 1, thresholds) < expected
    assert points(boundary, thresholds) == expected


@pytest.mark.parametrize(
    ("weighted_points", "expected"),
    [(0, "NONE"), (0.01, "LOW"), (2, "MEDIUM"), (4, "HIGH"), (6, "CRITICAL")],
)
def test_severity_level_boundaries(weighted_points, expected):
    if weighted_points >= 6:
        actual = "CRITICAL"
    elif weighted_points >= 4:
        actual = "HIGH"
    elif weighted_points >= 2:
        actual = "MEDIUM"
    elif weighted_points > 0:
        actual = "LOW"
    else:
        actual = "NONE"
    assert actual == expected


@pytest.mark.parametrize(
    ("base_stars", "weighted_points", "expected_stars", "downgraded"),
    [
        (5, 0, 5, False),
        (5, 1.99, 5, False),
        (5, 2, 4, True),
        (5, 4, 4, True),
        (5, 6, 3, True),
        (1, 6, 1, False),
    ],
)
def test_penalty_boundaries_and_downgrade(
    base_stars, weighted_points, expected_stars, downgraded
):
    penalty = points(weighted_points, [(0, 0), (2, 0.5), (4, 1), (6, 2)])
    final_stars = max(1, int(base_stars - penalty))
    assert final_stars == expected_stars
    assert (final_stars < base_stars) is downgraded


def test_forward_migration_has_one_term_shift_expansion():
    sql = FORWARD.read_text(encoding="utf-8")
    base_sql, severity_sql = sql.split(
        "CREATE OR REPLACE VIEW core.v_client_credit_quality_severity AS", 1
    )
    assert sql.count("FROM core.v_term_shift_invoice_summary") == 1
    assert "FROM core.v_term_shift_invoice_summary" in base_sql
    assert "FROM core.v_term_shift_invoice_summary" not in severity_sql
    assert "WITH repeated_shift AS" not in severity_sql
    assert "LEFT JOIN repeated_shift" not in severity_sql
    assert "b.repeated_shift_invoice_count >= r.threshold" in severity_sql


def test_forward_migration_preserves_exact_repeated_shift_thresholds():
    sql = FORWARD.read_text(encoding="utf-8")
    assert "WHERE COALESCE(term_shift_count, 0) >= 2" in sql
    assert "WHERE COALESCE(term_shift_count, 0) >= 3" in sql


def test_rollback_restores_two_expansions_and_prior_join():
    sql = ROLLBACK.read_text(encoding="utf-8")
    assert sql.count("FROM core.v_term_shift_invoice_summary") == 2
    assert "WITH repeated_shift AS" in sql
    assert "LEFT JOIN repeated_shift rs" in sql
    assert "RENAME TO v_client_credit_quality_base_p2a" in sql
    assert "DROP VIEW core.v_client_credit_quality_base_p2a" in sql


def test_rollback_restores_exact_prior_view_definitions():
    migration_023 = (ROOT / "sql" / "ddl" / "023_credit_quality_rating_v2.sql").read_text(
        encoding="utf-8"
    )
    migration_024 = (
        ROOT / "sql" / "ddl" / "024_rating_v2_term_shift_severity.sql"
    ).read_text(encoding="utf-8")
    rollback = ROLLBACK.read_text(encoding="utf-8")

    old_base = migration_023.split(
        "CREATE OR REPLACE VIEW core.v_client_credit_quality_base AS", 1
    )[1].split(
        "CREATE OR REPLACE VIEW core.v_client_credit_quality_severity AS", 1
    )[0]
    restored_base = rollback.split(
        "CREATE VIEW core.v_client_credit_quality_base AS", 1
    )[1].split(
        "CREATE OR REPLACE VIEW core.v_client_credit_quality_severity AS", 1
    )[0]

    old_severity = migration_024.split(
        "CREATE OR REPLACE VIEW core.v_client_credit_quality_severity AS", 1
    )[1].split(
        "CREATE OR REPLACE VIEW core.v_client_credit_quality_rating AS", 1
    )[0]
    restored_severity = rollback.split(
        "CREATE OR REPLACE VIEW core.v_client_credit_quality_severity AS", 1
    )[1].split("DROP VIEW core.v_client_credit_quality_base_p2a", 1)[0]

    normalize = lambda sql: " ".join(sql.split())
    assert normalize(restored_base) == normalize(old_base)
    assert normalize(restored_severity) == normalize(old_severity)


def test_client_aggregation_is_unique_by_client_id():
    rows = [
        {"client_id": 1, "term_shift_count": 1, "current_term_delta_days": 5},
        {"client_id": 1, "term_shift_count": 3, "current_term_delta_days": 9},
        {"client_id": 2, "term_shift_count": None, "current_term_delta_days": None},
    ]
    client_ids = {row["client_id"] for row in rows}
    result = {
        client_id: aggregate_term_shifts(
            [row for row in rows if row["client_id"] == client_id]
        )
        for client_id in client_ids
    }
    assert set(result) == {1, 2}
    assert len(result) == len(set(result))
