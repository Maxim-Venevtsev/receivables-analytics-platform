from __future__ import annotations

import os
import uuid
from pathlib import Path

import psycopg2
import pytest
from psycopg2 import sql


ROOT = Path(__file__).resolve().parents[1]
FORWARD = ROOT / "sql" / "ddl" / "038_consolidate_credit_quality_term_shift.sql"
ROLLBACK = ROOT / "sql" / "rollback" / "038_consolidate_credit_quality_term_shift.sql"
PREFLIGHT = (
    ROOT / "sql" / "checks" / "038_credit_quality_base_metadata_preflight.sql"
)
POST_ROLLBACK = (
    ROOT
    / "sql"
    / "checks"
    / "038_credit_quality_base_post_rollback_verification.sql"
)
P2A_COLUMNS = {
    "repeated_shift_invoice_count",
    "heavy_repeated_shift_invoice_count",
}


@pytest.fixture(scope="module")
def disposable_connection():
    url = os.getenv("P2A_ROLLBACK_TEST_DATABASE_URL")
    confirmed = os.getenv("P2A_ROLLBACK_TEST_DB_DISPOSABLE")
    if not url or confirmed != "YES":
        pytest.skip(
            "Set P2A_ROLLBACK_TEST_DATABASE_URL and "
            "P2A_ROLLBACK_TEST_DB_DISPOSABLE=YES for a disposable PostgreSQL "
            "database containing the current project schema and fixtures."
        )

    connection = psycopg2.connect(url)
    connection.autocommit = True
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database()")
        database_name = cursor.fetchone()[0]
    if database_name == "debt_management_work":
        connection.close()
        pytest.fail("Refusing to run rollback metadata tests on the regular local database")

    try:
        yield connection
    finally:
        connection.close()


def execute_file(connection, path: Path):
    with connection.cursor() as cursor:
        cursor.execute(path.read_text(encoding="utf-8"))


def state(connection):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'core'
              AND table_name = 'v_client_credit_quality_base'
            """
        )
        columns = {row[0] for row in cursor.fetchall()}
        cursor.execute(
            "SELECT pg_get_viewdef("
            "'core.v_client_credit_quality_severity'::regclass, true)"
        )
        severity_definition = cursor.fetchone()[0]
    if P2A_COLUMNS.issubset(columns) and "v_term_shift_invoice_summary" not in severity_definition:
        return "new"
    if P2A_COLUMNS.isdisjoint(columns) and "v_term_shift_invoice_summary" in severity_definition:
        return "old"
    return "unknown"


def metadata_snapshot(connection, qualified_name="core.v_client_credit_quality_base"):
    schema_name, object_name = qualified_name.split(".", 1)
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                pg_get_userbyid(c.relowner),
                obj_description(c.oid, 'pg_class'),
                pg_get_viewdef(c.oid, true)
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = %s
              AND c.relname = %s
              AND c.relkind = 'v'
            """,
            (schema_name, object_name),
        )
        owner, relation_comment, definition = cursor.fetchone()

        cursor.execute(
            """
            SELECT
                pg_get_userbyid(x.grantor),
                CASE WHEN x.grantee = 0 THEN 'PUBLIC'
                     ELSE pg_get_userbyid(x.grantee) END,
                x.privilege_type,
                x.is_grantable
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            CROSS JOIN LATERAL aclexplode(c.relacl) x
            WHERE n.nspname = %s
              AND c.relname = %s
            ORDER BY 1, 2, 3, 4
            """,
            (schema_name, object_name),
        )
        relation_acl = cursor.fetchall()

        cursor.execute(
            """
            SELECT option_name, option_value
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            CROSS JOIN LATERAL pg_options_to_table(c.reloptions)
            WHERE n.nspname = %s
              AND c.relname = %s
            ORDER BY option_name
            """,
            (schema_name, object_name),
        )
        reloptions = cursor.fetchall()

        cursor.execute(
            """
            SELECT
                a.attnum,
                a.attname,
                format_type(a.atttypid, a.atttypmod),
                col_description(a.attrelid, a.attnum),
                pg_get_expr(ad.adbin, ad.adrelid),
                a.attoptions
            FROM pg_attribute a
            JOIN pg_class c ON c.oid = a.attrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            LEFT JOIN pg_attrdef ad
              ON ad.adrelid = a.attrelid
             AND ad.adnum = a.attnum
            WHERE n.nspname = %s
              AND c.relname = %s
              AND a.attnum > 0
              AND NOT a.attisdropped
            ORDER BY a.attnum
            """,
            (schema_name, object_name),
        )
        columns = cursor.fetchall()

        cursor.execute(
            """
            SELECT
                a.attname,
                pg_get_userbyid(x.grantor),
                CASE WHEN x.grantee = 0 THEN 'PUBLIC'
                     ELSE pg_get_userbyid(x.grantee) END,
                x.privilege_type,
                x.is_grantable
            FROM pg_attribute a
            JOIN pg_class c ON c.oid = a.attrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            CROSS JOIN LATERAL aclexplode(a.attacl) x
            WHERE n.nspname = %s
              AND c.relname = %s
              AND a.attnum > 0
              AND NOT a.attisdropped
            ORDER BY 1, 2, 3, 4, 5
            """,
            (schema_name, object_name),
        )
        column_acl = cursor.fetchall()

        cursor.execute(
            """
            SELECT
                s.objsubid,
                a.attname,
                s.provider,
                s.label
            FROM pg_seclabel s
            JOIN pg_class c ON c.oid = s.objoid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            LEFT JOIN pg_attribute a
              ON a.attrelid = s.objoid
             AND a.attnum = s.objsubid
            WHERE s.classoid = 'pg_class'::regclass
              AND n.nspname = %s
              AND c.relname = %s
            ORDER BY s.objsubid, s.provider
            """,
            (schema_name, object_name),
        )
        security_labels = cursor.fetchall()

    option_map = dict(reloptions)
    return {
        "qualified_name": qualified_name,
        "owner": owner,
        "relation_acl": relation_acl,
        "relation_comment": relation_comment,
        "columns": columns,
        "column_acl": column_acl,
        "reloptions": reloptions,
        "security_barrier": option_map.get("security_barrier"),
        "security_invoker": option_map.get("security_invoker"),
        "check_option": option_map.get("check_option"),
        "security_labels": security_labels,
        "view_definition": definition,
    }


def metadata_without_removed_columns(snapshot):
    result = dict(snapshot)
    result["columns"] = [
        row for row in snapshot["columns"] if row[1] not in P2A_COLUMNS
    ]
    result["column_acl"] = [
        row for row in snapshot["column_acl"] if row[0] not in P2A_COLUMNS
    ]
    result["security_labels"] = [
        row
        for row in snapshot["security_labels"]
        if row[1] is None or row[1] not in P2A_COLUMNS
    ]
    result.pop("view_definition")
    return result


def rating_parity(connection):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM (
                    SELECT * FROM p2a_rating_baseline
                    EXCEPT ALL
                    SELECT * FROM core.v_client_credit_quality_rating
                ) baseline_except_current),
                (SELECT COUNT(*) FROM (
                    SELECT * FROM core.v_client_credit_quality_rating
                    EXCEPT ALL
                    SELECT * FROM p2a_rating_baseline
                ) current_except_baseline)
            """
        )
        return cursor.fetchone()


def assert_no_persistent_helpers(connection):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relname LIKE 'p2a_base_%'
              AND c.relpersistence <> 't'
            """
        )
        assert cursor.fetchone()[0] == 0


def ensure_new_state(connection):
    if state(connection) != "new":
        execute_file(connection, FORWARD)
    assert state(connection) == "new"


def test_default_metadata_rollback_is_atomic_and_exact(disposable_connection):
    connection = disposable_connection
    ensure_new_state(connection)
    before = metadata_snapshot(connection)
    execute_file(connection, PREFLIGHT)

    with connection.cursor() as cursor:
        cursor.execute("DROP TABLE IF EXISTS p2a_rating_baseline")
        cursor.execute(
            "CREATE TEMP TABLE p2a_rating_baseline AS "
            "SELECT * FROM core.v_client_credit_quality_rating"
        )

    execute_file(connection, ROLLBACK)
    assert state(connection) == "old"
    execute_file(connection, POST_ROLLBACK)
    after = metadata_snapshot(connection)

    assert metadata_without_removed_columns(before) == metadata_without_removed_columns(
        after
    )
    assert rating_parity(connection) == (0, 0)
    assert_no_persistent_helpers(connection)

    execute_file(connection, FORWARD)
    assert state(connection) == "new"


def test_nondefault_metadata_is_preserved(disposable_connection):
    connection = disposable_connection
    ensure_new_state(connection)
    suffix = uuid.uuid4().hex[:10]
    role_prefix = os.getenv("P2A_TEST_ROLE_PREFIX", "p2a_metadata")
    owner = f"{role_prefix}_owner_{suffix}"
    reader = f"{role_prefix}_reader_{suffix}"
    grantor = f"{role_prefix}_grantor_{suffix}"
    downstream = f"{role_prefix}_downstream_{suffix}"
    roles = [owner, reader, grantor, downstream]

    with connection.cursor() as cursor:
        cursor.execute("SELECT session_user")
        administrative_role = cursor.fetchone()[0]
        for role in roles:
            cursor.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(role)))
        cursor.execute(
            sql.SQL("GRANT USAGE, CREATE ON SCHEMA core TO {}").format(
                sql.Identifier(owner)
            )
        )
        for role in (reader, grantor, downstream):
            cursor.execute(
                sql.SQL("GRANT USAGE ON SCHEMA core TO {}").format(
                    sql.Identifier(role)
                )
            )

    try:
        execute_file(connection, ROLLBACK)
        old_snapshot = metadata_snapshot(connection)
        execute_file(connection, FORWARD)

        with connection.cursor() as cursor:
            cursor.execute(
                sql.SQL(
                    "ALTER VIEW core.v_client_credit_quality_base OWNER TO {}"
                ).format(sql.Identifier(owner))
            )
            cursor.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(owner)))
            cursor.execute(
                sql.SQL(
                    "GRANT SELECT ON core.v_client_credit_quality_base TO {}"
                ).format(sql.Identifier(reader))
            )
            cursor.execute(
                sql.SQL(
                    "GRANT UPDATE ON core.v_client_credit_quality_base "
                    "TO {} WITH GRANT OPTION"
                ).format(sql.Identifier(grantor))
            )
            cursor.execute(
                "GRANT SELECT ON core.v_client_credit_quality_base TO PUBLIC"
            )
            cursor.execute(
                sql.SQL(
                    "GRANT SELECT (client_id) "
                    "ON core.v_client_credit_quality_base "
                    "TO {} WITH GRANT OPTION"
                ).format(sql.Identifier(reader))
            )
            cursor.execute(
                sql.SQL(
                    "GRANT UPDATE (client_name) "
                    "ON core.v_client_credit_quality_base TO {}"
                ).format(sql.Identifier(downstream))
            )
            cursor.execute("RESET ROLE")
            cursor.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(grantor)))
            cursor.execute(
                sql.SQL(
                    "GRANT UPDATE ON core.v_client_credit_quality_base TO {}"
                ).format(sql.Identifier(downstream))
            )
            cursor.execute("RESET ROLE")

            cursor.execute(
                "COMMENT ON VIEW core.v_client_credit_quality_base "
                "IS 'P2A owner''s \"quoted\" view comment'"
            )
            cursor.execute(
                "COMMENT ON COLUMN core.v_client_credit_quality_base.client_id "
                "IS 'original identifier'"
            )
            cursor.execute(
                "COMMENT ON COLUMN "
                "core.v_client_credit_quality_base.exposure_multiplier "
                "IS 'exposure multiplier comment'"
            )
            cursor.execute(
                "ALTER VIEW core.v_client_credit_quality_base SET "
                "(security_barrier=true, security_invoker=true)"
            )
            cursor.execute("DROP TABLE IF EXISTS p2a_rating_baseline")
            cursor.execute(
                "CREATE TEMP TABLE p2a_rating_baseline AS "
                "SELECT * FROM core.v_client_credit_quality_rating"
            )

        before = metadata_snapshot(connection)
        execute_file(connection, ROLLBACK)
        after = metadata_snapshot(connection)

        assert state(connection) == "old"
        assert after["view_definition"] == old_snapshot["view_definition"]
        assert [
            (row[0], row[1], row[2]) for row in after["columns"]
        ] == [
            (row[0], row[1], row[2]) for row in old_snapshot["columns"]
        ]
        assert metadata_without_removed_columns(before) == metadata_without_removed_columns(
            after
        )
        assert rating_parity(connection) == (0, 0)
        assert_no_persistent_helpers(connection)

        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM core.v_client_credit_quality_severity")
            assert cursor.fetchone()[0] > 0
            cursor.execute("SELECT COUNT(*) FROM core.v_client_credit_quality_rating")
            assert cursor.fetchone()[0] > 0
    finally:
        with connection.cursor() as cursor:
            cursor.execute("ROLLBACK")
        with connection.cursor() as cursor:
            cursor.execute("RESET ROLE")
            cursor.execute(
                sql.SQL(
                    "ALTER VIEW core.v_client_credit_quality_base OWNER TO {}"
                ).format(sql.Identifier(administrative_role))
            )
            cursor.execute(
                "REVOKE ALL PRIVILEGES ON core.v_client_credit_quality_base "
                "FROM PUBLIC"
            )
            cursor.execute(
                "ALTER VIEW core.v_client_credit_quality_base RESET "
                "(security_barrier, security_invoker)"
            )
            cursor.execute(
                "COMMENT ON VIEW core.v_client_credit_quality_base IS NULL"
            )
            cursor.execute(
                "COMMENT ON COLUMN core.v_client_credit_quality_base.client_id IS NULL"
            )
            cursor.execute(
                "COMMENT ON COLUMN "
                "core.v_client_credit_quality_base.exposure_multiplier IS NULL"
            )
            for role in roles:
                cursor.execute(
                    sql.SQL(
                        "REVOKE ALL PRIVILEGES ON TABLE "
                        "core.v_client_credit_quality_base FROM {} CASCADE"
                    ).format(sql.Identifier(role))
                )
                cursor.execute(
                    sql.SQL(
                        "REVOKE ALL PRIVILEGES "
                        "(client_id, client_name) ON TABLE "
                        "core.v_client_credit_quality_base FROM {} CASCADE"
                    ).format(sql.Identifier(role))
                )
                cursor.execute(
                    sql.SQL("DROP OWNED BY {} CASCADE").format(sql.Identifier(role))
                )
            for role in reversed(roles):
                cursor.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))
        ensure_new_state(connection)


def test_snapshot_helper_captures_all_supported_view_options(disposable_connection):
    connection = disposable_connection
    schema_name = "p2a_metadata_helper_" + uuid.uuid4().hex[:10]
    qualified_view = f"{schema_name}.option_view"
    with connection.cursor() as cursor:
        cursor.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema_name)))
        cursor.execute(
            sql.SQL("CREATE TABLE {}.source (id integer, value text)").format(
                sql.Identifier(schema_name)
            )
        )
        cursor.execute(
            sql.SQL(
                "CREATE VIEW {}.option_view "
                "WITH (security_barrier=true, security_invoker=true, "
                "check_option=local) AS "
                "SELECT id, value FROM {}.source WHERE id > 0"
            ).format(sql.Identifier(schema_name), sql.Identifier(schema_name))
        )
        cursor.execute(
            sql.SQL("COMMENT ON VIEW {}.option_view IS 'option helper'").format(
                sql.Identifier(schema_name)
            )
        )
        snapshot = metadata_snapshot(connection, qualified_view)
        cursor.execute(
            sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema_name))
        )

    assert snapshot["security_barrier"] == "true"
    assert snapshot["security_invoker"] == "true"
    assert snapshot["check_option"] == "local"
    assert snapshot["relation_comment"] == "option helper"


def test_removed_column_metadata_aborts_entire_rollback(disposable_connection):
    connection = disposable_connection
    ensure_new_state(connection)
    with connection.cursor() as cursor:
        cursor.execute(
            "COMMENT ON COLUMN "
            "core.v_client_credit_quality_base.repeated_shift_invoice_count "
            "IS 'cannot survive removal'"
        )
    before = metadata_snapshot(connection)

    with pytest.raises(
        psycopg2.Error,
        match="cannot preserve metadata attached to removed columns",
    ):
        execute_file(connection, ROLLBACK)
    with connection.cursor() as cursor:
        cursor.execute("ROLLBACK")

    after = metadata_snapshot(connection)
    assert state(connection) == "new"
    assert after == before
    assert_no_persistent_helpers(connection)

    with connection.cursor() as cursor:
        cursor.execute(
            "COMMENT ON COLUMN "
            "core.v_client_credit_quality_base.repeated_shift_invoice_count IS NULL"
        )


def test_unrestorable_grantor_identity_aborts_entire_rollback(
    disposable_connection,
):
    connection = disposable_connection
    ensure_new_state(connection)
    suffix = uuid.uuid4().hex[:10]
    role_prefix = os.getenv("P2A_TEST_ROLE_PREFIX", "p2a_metadata")
    rollback_owner = f"{role_prefix}_limited_owner_{suffix}"
    independent_grantor = f"{role_prefix}_independent_grantor_{suffix}"
    downstream = f"{role_prefix}_limited_downstream_{suffix}"
    roles = [rollback_owner, independent_grantor, downstream]
    rollback_password = uuid.uuid4().hex + uuid.uuid4().hex

    with connection.cursor() as cursor:
        cursor.execute("SELECT session_user")
        administrative_role = cursor.fetchone()[0]
        cursor.execute(
            sql.SQL("CREATE ROLE {} LOGIN PASSWORD %s").format(
                sql.Identifier(rollback_owner)
            ),
            (rollback_password,),
        )
        for role in (independent_grantor, downstream):
            cursor.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(role)))
        cursor.execute(
            sql.SQL("GRANT USAGE, CREATE ON SCHEMA core TO {}").format(
                sql.Identifier(rollback_owner)
            )
        )
        cursor.execute(
            sql.SQL("GRANT USAGE ON SCHEMA core TO {}, {}").format(
                sql.Identifier(independent_grantor),
                sql.Identifier(downstream),
            )
        )
        cursor.execute(
            sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA core TO {}").format(
                sql.Identifier(rollback_owner)
            )
        )
        cursor.execute(
            sql.SQL(
                "ALTER VIEW core.v_client_credit_quality_base OWNER TO {}"
            ).format(sql.Identifier(rollback_owner))
        )
        cursor.execute(
            sql.SQL(
                "ALTER VIEW core.v_client_credit_quality_severity OWNER TO {}"
            ).format(sql.Identifier(rollback_owner))
        )
        cursor.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(rollback_owner)))
        cursor.execute(
            sql.SQL(
                "GRANT UPDATE ON core.v_client_credit_quality_base "
                "TO {} WITH GRANT OPTION"
            ).format(sql.Identifier(independent_grantor))
        )
        cursor.execute("RESET ROLE")
        cursor.execute(
            sql.SQL("SET ROLE {}").format(sql.Identifier(independent_grantor))
        )
        cursor.execute(
            sql.SQL(
                "GRANT UPDATE ON core.v_client_credit_quality_base TO {}"
            ).format(sql.Identifier(downstream))
        )
        cursor.execute("RESET ROLE")

    before = metadata_snapshot(connection)
    limited_connection = psycopg2.connect(
        host=connection.info.host,
        port=connection.info.port,
        dbname=connection.info.dbname,
        user=rollback_owner,
        password=rollback_password,
    )
    limited_connection.autocommit = True

    try:
        with pytest.raises(
            psycopg2.Error,
            match="relation ACL or grantor identity",
        ):
            execute_file(limited_connection, ROLLBACK)
        with limited_connection.cursor() as cursor:
            cursor.execute("ROLLBACK")
        limited_connection.close()

        after = metadata_snapshot(connection)
        assert state(connection) == "new"
        assert after == before
        assert_no_persistent_helpers(connection)
    finally:
        if not limited_connection.closed:
            limited_connection.close()
        with connection.cursor() as cursor:
            cursor.execute("ROLLBACK")
            cursor.execute("RESET ROLE")
            cursor.execute(
                sql.SQL(
                    "ALTER VIEW core.v_client_credit_quality_severity OWNER TO {}"
                ).format(sql.Identifier(administrative_role))
            )
            cursor.execute(
                sql.SQL(
                    "ALTER VIEW core.v_client_credit_quality_base OWNER TO {}"
                ).format(sql.Identifier(administrative_role))
            )
            for role in roles:
                cursor.execute(
                    sql.SQL("DROP OWNED BY {} CASCADE").format(sql.Identifier(role))
                )
            for role in reversed(roles):
                cursor.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))


def test_security_label_restoration_when_provider_is_configured(
    disposable_connection,
):
    provider = os.getenv("P2A_TEST_SECURITY_LABEL_PROVIDER")
    label = os.getenv("P2A_TEST_SECURITY_LABEL_VALUE")
    if not provider or label is None:
        pytest.skip(
            "No test security-label provider/value is configured. PostgreSQL "
            "providers are backend modules with provider-specific label syntax "
            "and authorization; set P2A_TEST_SECURITY_LABEL_PROVIDER and "
            "P2A_TEST_SECURITY_LABEL_VALUE to exercise restoration."
        )

    connection = disposable_connection
    ensure_new_state(connection)
    with connection.cursor() as cursor:
        cursor.execute(
            sql.SQL(
                "SECURITY LABEL FOR {} ON VIEW "
                "core.v_client_credit_quality_base IS %s"
            ).format(sql.Identifier(provider)),
            (label,),
        )
    before = metadata_snapshot(connection)
    execute_file(connection, ROLLBACK)
    after = metadata_snapshot(connection)
    assert after["security_labels"] == before["security_labels"]
    execute_file(connection, FORWARD)
