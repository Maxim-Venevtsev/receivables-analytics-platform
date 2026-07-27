-- Roll back 038_consolidate_credit_quality_term_shift.sql.
-- Restore the Credit Quality base and severity definitions from migrations 023 and 024.
-- Intentionally one-shot: metadata is captured from the P2A base view and
-- restored to the newly created pre-P2A base view in this transaction.

BEGIN;

CREATE TEMP TABLE p2a_base_relation_metadata
ON COMMIT DROP
AS
SELECT
    c.relowner AS owner_oid,
    pg_get_userbyid(c.relowner) AS owner_name,
    c.relacl IS NULL AS relacl_was_null,
    c.reloptions,
    obj_description(c.oid, 'pg_class') AS relation_comment
FROM pg_class c
JOIN pg_namespace n
    ON n.oid = c.relnamespace
WHERE n.nspname = 'core'
  AND c.relname = 'v_client_credit_quality_base'
  AND c.relkind = 'v';

DO $metadata_capture$
BEGIN
    IF (SELECT COUNT(*) FROM pg_temp.p2a_base_relation_metadata) <> 1 THEN
        RAISE EXCEPTION
            'P2A rollback metadata capture failed: expected core.v_client_credit_quality_base';
    END IF;
END
$metadata_capture$;

CREATE TEMP TABLE p2a_base_relation_acl
ON COMMIT DROP
AS
SELECT
    x.grantor AS grantor_oid,
    pg_get_userbyid(x.grantor) AS grantor_name,
    x.grantee AS grantee_oid,
    CASE
        WHEN x.grantee = 0 THEN NULL
        ELSE pg_get_userbyid(x.grantee)
    END AS grantee_name,
    x.privilege_type,
    x.is_grantable,
    FALSE AS restored
FROM pg_class c
CROSS JOIN LATERAL aclexplode(c.relacl) x
WHERE c.oid = 'core.v_client_credit_quality_base'::regclass;

CREATE TEMP TABLE p2a_base_columns
ON COMMIT DROP
AS
SELECT
    a.attnum,
    a.attname AS column_name,
    format_type(a.atttypid, a.atttypmod) AS formatted_type,
    a.attacl,
    a.attoptions,
    col_description(a.attrelid, a.attnum) AS column_comment,
    pg_get_expr(ad.adbin, ad.adrelid) AS default_expression
FROM pg_attribute a
LEFT JOIN pg_attrdef ad
    ON ad.adrelid = a.attrelid
   AND ad.adnum = a.attnum
WHERE a.attrelid = 'core.v_client_credit_quality_base'::regclass
  AND a.attnum > 0
  AND NOT a.attisdropped
ORDER BY a.attnum;

CREATE TEMP TABLE p2a_base_column_acl
ON COMMIT DROP
AS
SELECT
    a.attnum,
    a.attname AS column_name,
    x.grantor AS grantor_oid,
    pg_get_userbyid(x.grantor) AS grantor_name,
    x.grantee AS grantee_oid,
    CASE
        WHEN x.grantee = 0 THEN NULL
        ELSE pg_get_userbyid(x.grantee)
    END AS grantee_name,
    x.privilege_type,
    x.is_grantable,
    FALSE AS restored
FROM pg_attribute a
CROSS JOIN LATERAL aclexplode(a.attacl) x
WHERE a.attrelid = 'core.v_client_credit_quality_base'::regclass
  AND a.attnum > 0
  AND NOT a.attisdropped;

CREATE TEMP TABLE p2a_base_reloptions
ON COMMIT DROP
AS
SELECT
    option_name,
    option_value
FROM pg_class c
CROSS JOIN LATERAL pg_options_to_table(c.reloptions)
WHERE c.oid = 'core.v_client_credit_quality_base'::regclass;

CREATE TEMP TABLE p2a_base_security_labels
ON COMMIT DROP
AS
SELECT
    s.objsubid,
    a.attname AS column_name,
    s.provider,
    s.label
FROM pg_seclabel s
LEFT JOIN pg_attribute a
    ON a.attrelid = s.objoid
   AND a.attnum = s.objsubid
WHERE s.classoid = 'pg_class'::regclass
  AND s.objoid = 'core.v_client_credit_quality_base'::regclass;

CREATE TEMP TABLE p2a_base_extension_membership
ON COMMIT DROP
AS
SELECT e.extname
FROM pg_depend d
JOIN pg_extension e
    ON e.oid = d.refobjid
WHERE d.classid = 'pg_class'::regclass
  AND d.objid = 'core.v_client_credit_quality_base'::regclass
  AND d.objsubid = 0
  AND d.refclassid = 'pg_extension'::regclass
  AND d.deptype = 'e';

DO $metadata_preflight$
DECLARE
    unsupported_columns TEXT;
    unsupported_objects TEXT;
BEGIN
    SELECT string_agg(column_name, ', ' ORDER BY column_name)
    INTO unsupported_columns
    FROM pg_temp.p2a_base_columns
    WHERE column_name IN (
        'repeated_shift_invoice_count',
        'heavy_repeated_shift_invoice_count'
    )
      AND (
          attacl IS NOT NULL
          OR column_comment IS NOT NULL
          OR default_expression IS NOT NULL
          OR COALESCE(cardinality(attoptions), 0) > 0
      );

    IF unsupported_columns IS NOT NULL THEN
        RAISE EXCEPTION
            'P2A rollback cannot preserve metadata attached to removed columns'
            USING DETAIL = format(
                'Remove or archive metadata for these P2A-only columns before rollback: %s',
                unsupported_columns
            );
    END IF;

    SELECT string_agg(
        format('%s:%s', provider, column_name),
        ', '
        ORDER BY provider, column_name
    )
    INTO unsupported_columns
    FROM pg_temp.p2a_base_security_labels
    WHERE column_name IN (
        'repeated_shift_invoice_count',
        'heavy_repeated_shift_invoice_count'
    );

    IF unsupported_columns IS NOT NULL THEN
        RAISE EXCEPTION
            'P2A rollback cannot preserve security labels attached to removed columns'
            USING DETAIL = unsupported_columns;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_init_privs p
        WHERE p.classoid = 'pg_class'::regclass
          AND p.objoid = 'core.v_client_credit_quality_base'::regclass
    ) THEN
        RAISE EXCEPTION
            'P2A rollback cannot safely recreate pg_init_privs metadata';
    END IF;

    SELECT string_agg(object_name, ', ' ORDER BY object_name)
    INTO unsupported_objects
    FROM (
        SELECT format('rule %I', r.rulename) AS object_name
        FROM pg_rewrite r
        WHERE r.ev_class = 'core.v_client_credit_quality_base'::regclass
          AND r.rulename <> '_RETURN'

        UNION ALL

        SELECT format('trigger %I', t.tgname)
        FROM pg_trigger t
        WHERE t.tgrelid = 'core.v_client_credit_quality_base'::regclass
          AND NOT t.tgisinternal
    ) attached_objects;

    IF unsupported_objects IS NOT NULL THEN
        RAISE EXCEPTION
            'P2A rollback cannot safely recreate attached rules or triggers'
            USING DETAIL = unsupported_objects;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_temp.p2a_base_columns
        WHERE COALESCE(cardinality(attoptions), 0) > 0
    ) THEN
        RAISE EXCEPTION
            'P2A rollback cannot safely recreate column attoptions metadata';
    END IF;
END
$metadata_preflight$;

DO $metadata_temp_access$
DECLARE
    original_owner TEXT;
    table_name TEXT;
BEGIN
    SELECT owner_name
    INTO STRICT original_owner
    FROM pg_temp.p2a_base_relation_metadata;

    FOREACH table_name IN ARRAY ARRAY[
        'p2a_base_relation_metadata',
        'p2a_base_relation_acl',
        'p2a_base_columns',
        'p2a_base_column_acl',
        'p2a_base_reloptions',
        'p2a_base_security_labels',
        'p2a_base_extension_membership'
    ]
    LOOP
        EXECUTE format(
            'GRANT SELECT ON TABLE pg_temp.%I TO %I',
            table_name,
            original_owner
        );
    END LOOP;
EXCEPTION
    WHEN OTHERS THEN
        RAISE EXCEPTION
            'P2A rollback metadata capture failed: temporary snapshot access'
            USING DETAIL = SQLERRM;
END
$metadata_temp_access$;

ALTER VIEW core.v_client_credit_quality_base
    RENAME TO v_client_credit_quality_base_p2a;

CREATE VIEW core.v_client_credit_quality_base AS
WITH term_shift AS (
    SELECT
        client_id,
        SUM(COALESCE(term_shift_count, 0)) AS term_shift_count,
        MAX(COALESCE(term_shift_count, 0)) AS max_invoice_term_shift_count,
        SUM(COALESCE(current_term_delta_days, 0)) AS total_term_shift_delta_days,
        MAX(COALESCE(current_term_delta_days, 0)) AS max_term_shift_delta_days
    FROM core.v_term_shift_invoice_summary
    GROUP BY client_id
)

SELECT
    b.client_id,
    b.client_name,
    b.client_group,
    b.parent_org_id,

    r.stars AS base_stars,
    r.rating_label AS base_rating_label,
    r.rating_display_label AS base_rating_display_label,
    r.confidence_level,

    b.total_debt,
    b.overdue_debt,
    b.green_debt,
    b.green_45_plus_debt,
    b.green_60_plus_debt,
    b.green_90_plus_debt,
    b.green_120_plus_debt,

    b.overdue_share_pct,
    b.green_90_plus_share_of_total_pct AS green_90_plus_share_pct,
    b.green_120_plus_share_of_total_pct AS green_120_plus_share_pct,

    b.weighted_avg_payment_term_days,
    b.max_payment_term_days,
    b.max_days_overdue,
    b.invoice_count,

    COALESCE(ts.term_shift_count, 0) AS term_shift_count,
    COALESCE(ts.max_invoice_term_shift_count, 0) AS max_invoice_term_shift_count,
    COALESCE(ts.total_term_shift_delta_days, 0) AS total_term_shift_delta_days,
    COALESCE(ts.max_term_shift_delta_days, 0) AS max_term_shift_delta_days,

    CASE
        WHEN
            b.total_debt <= (
                SELECT max_total_debt
                FROM core.credit_quality_exposure_segments
                WHERE segment_name = 'small'
            )
            AND b.weighted_avg_payment_term_days <= (
                SELECT max_weighted_payment_term_days
                FROM core.credit_quality_exposure_segments
                WHERE segment_name = 'small'
            )
        THEN 'small'

        WHEN
            b.total_debt <= (
                SELECT max_total_debt
                FROM core.credit_quality_exposure_segments
                WHERE segment_name = 'medium'
            )
            OR b.weighted_avg_payment_term_days <= (
                SELECT max_weighted_payment_term_days
                FROM core.credit_quality_exposure_segments
                WHERE segment_name = 'medium'
            )
        THEN 'medium'

        ELSE 'large'
    END AS exposure_segment,

    CASE
        WHEN
            b.total_debt <= (
                SELECT max_total_debt
                FROM core.credit_quality_exposure_segments
                WHERE segment_name = 'small'
            )
            AND b.weighted_avg_payment_term_days <= (
                SELECT max_weighted_payment_term_days
                FROM core.credit_quality_exposure_segments
                WHERE segment_name = 'small'
            )
        THEN (
            SELECT multiplier
            FROM core.credit_quality_exposure_segments
            WHERE segment_name = 'small'
        )

        WHEN
            b.total_debt <= (
                SELECT max_total_debt
                FROM core.credit_quality_exposure_segments
                WHERE segment_name = 'medium'
            )
            OR b.weighted_avg_payment_term_days <= (
                SELECT max_weighted_payment_term_days
                FROM core.credit_quality_exposure_segments
                WHERE segment_name = 'medium'
            )
        THEN (
            SELECT multiplier
            FROM core.credit_quality_exposure_segments
            WHERE segment_name = 'medium'
        )

        ELSE (
            SELECT multiplier
            FROM core.credit_quality_exposure_segments
            WHERE segment_name = 'large'
        )
    END AS exposure_multiplier

FROM core.v_executive_client_risk_bubble_base b

LEFT JOIN core.v_client_rating r
    ON b.client_id = r.client_id

LEFT JOIN term_shift ts
    ON b.client_id = ts.client_id;


CREATE OR REPLACE VIEW core.v_client_credit_quality_severity AS
WITH repeated_shift AS (
    SELECT
        client_id,

        COUNT(*) FILTER (
            WHERE COALESCE(term_shift_count, 0) >= 2
        ) AS repeated_shift_invoice_count,

        COUNT(*) FILTER (
            WHERE COALESCE(term_shift_count, 0) >= 3
        ) AS heavy_repeated_shift_invoice_count

    FROM core.v_term_shift_invoice_summary
    GROUP BY client_id
),

scored AS (
    SELECT
        b.*,

        COALESCE(rs.repeated_shift_invoice_count, 0) AS repeated_shift_invoice_count,
        COALESCE(rs.heavy_repeated_shift_invoice_count, 0) AS heavy_repeated_shift_invoice_count,

        COALESCE((
            SELECT MAX(severity_points)
            FROM core.credit_quality_severity_rules r
            WHERE r.metric_name = 'weighted_avg_payment_term_days'
              AND b.weighted_avg_payment_term_days >= r.threshold
        ), 0) AS weighted_avg_payment_term_points,

        COALESCE((
            SELECT MAX(severity_points)
            FROM core.credit_quality_severity_rules r
            WHERE r.metric_name = 'max_payment_term_days'
              AND b.max_payment_term_days >= r.threshold
        ), 0) AS max_payment_term_points,

        COALESCE((
            SELECT MAX(severity_points)
            FROM core.credit_quality_severity_rules r
            WHERE r.metric_name = 'green_90_plus_share_pct'
              AND b.green_90_plus_share_pct >= r.threshold
        ), 0) AS green_90_plus_share_points,

        COALESCE((
            SELECT MAX(severity_points)
            FROM core.credit_quality_severity_rules r
            WHERE r.metric_name = 'green_120_plus_debt'
              AND b.green_120_plus_debt >= r.threshold
        ), 0) AS green_120_plus_debt_points,

        COALESCE((
            SELECT MAX(severity_points)
            FROM core.credit_quality_severity_rules r
            WHERE r.metric_name = 'term_shift_count'
              AND b.term_shift_count >= r.threshold
        ), 0) AS term_shift_count_points,

        COALESCE((
            SELECT MAX(severity_points)
            FROM core.credit_quality_repeated_shift_rules r
            WHERE r.metric_name = 'max_invoice_term_shift_count'
              AND b.max_invoice_term_shift_count >= r.threshold
        ), 0) AS max_invoice_term_shift_points,

        COALESCE((
            SELECT MAX(severity_points)
            FROM core.credit_quality_repeated_shift_rules r
            WHERE r.metric_name = 'repeated_shift_invoice_count'
              AND COALESCE(rs.repeated_shift_invoice_count, 0) >= r.threshold
        ), 0) AS repeated_shift_invoice_points

    FROM core.v_client_credit_quality_base b

    LEFT JOIN repeated_shift rs
        ON b.client_id = rs.client_id
),

aggregated AS (
    SELECT
        *,

        (
            weighted_avg_payment_term_points
            + max_payment_term_points
            + green_90_plus_share_points
            + green_120_plus_debt_points
            + term_shift_count_points
            + max_invoice_term_shift_points
            + repeated_shift_invoice_points
        ) AS raw_severity_points,

        ROUND(
            (
                weighted_avg_payment_term_points
                + max_payment_term_points
                + green_90_plus_share_points
                + green_120_plus_debt_points
                + term_shift_count_points
                + max_invoice_term_shift_points
                + repeated_shift_invoice_points
            ) * exposure_multiplier,
            2
        ) AS weighted_severity_points

    FROM scored
)

SELECT
    *,

    ARRAY_REMOVE(ARRAY[
        CASE
            WHEN weighted_avg_payment_term_points > 0
            THEN 'длинная средневзвешенная отсрочка'
        END,
        CASE
            WHEN max_payment_term_points > 0
            THEN 'аномально длинная максимальная отсрочка'
        END,
        CASE
            WHEN green_90_plus_share_points > 0
            THEN 'высокая доля 90+ непросроченного долга'
        END,
        CASE
            WHEN green_120_plus_debt_points > 0
            THEN 'есть 120+ непросроченный долг'
        END,
        CASE
            WHEN term_shift_count_points > 0
            THEN 'переносы сроков оплаты'
        END,
        CASE
            WHEN max_invoice_term_shift_points > 0
            THEN 'повторные переносы по одной накладной'
        END,
        CASE
            WHEN repeated_shift_invoice_points > 0
            THEN 'повторные переносы по нескольким накладным'
        END
    ], NULL) AS severity_reasons,

    CASE
        WHEN weighted_severity_points >= 6 THEN 'CRITICAL'
        WHEN weighted_severity_points >= 4 THEN 'HIGH'
        WHEN weighted_severity_points >= 2 THEN 'MEDIUM'
        WHEN weighted_severity_points > 0 THEN 'LOW'
        ELSE 'NONE'
    END AS severity_level,

    COALESCE((
        SELECT penalty
        FROM core.credit_quality_penalty_mapping p
        WHERE aggregated.weighted_severity_points >= p.min_severity_points
        ORDER BY p.min_severity_points DESC
        LIMIT 1
    ), 0) AS severity_penalty

FROM aggregated;

DROP VIEW core.v_client_credit_quality_base_p2a;

DO $clear_creation_acl$
DECLARE
    acl_record RECORD;
    grantee_sql TEXT;
BEGIN
    FOR acl_record IN
        SELECT DISTINCT
            x.grantee,
            CASE
                WHEN x.grantee = 0 THEN NULL
                ELSE pg_get_userbyid(x.grantee)
            END AS grantee_name
        FROM pg_class c
        CROSS JOIN LATERAL aclexplode(c.relacl) x
        WHERE c.oid = 'core.v_client_credit_quality_base'::regclass
    LOOP
        grantee_sql := CASE
            WHEN acl_record.grantee = 0 THEN 'PUBLIC'
            ELSE format('%I', acl_record.grantee_name)
        END;

        EXECUTE format(
            'REVOKE ALL PRIVILEGES ON TABLE %I.%I FROM %s',
            'core',
            'v_client_credit_quality_base',
            grantee_sql
        );
    END LOOP;
EXCEPTION
    WHEN OTHERS THEN
        RAISE EXCEPTION
            'P2A rollback metadata restoration failed: creation-time ACL cleanup'
            USING DETAIL = SQLERRM;
END
$clear_creation_acl$;

DO $restore_owner$
DECLARE
    original_owner TEXT;
BEGIN
    SELECT owner_name
    INTO STRICT original_owner
    FROM pg_temp.p2a_base_relation_metadata;

    EXECUTE format(
        'ALTER VIEW %I.%I OWNER TO %I',
        'core',
        'v_client_credit_quality_base',
        original_owner
    );
EXCEPTION
    WHEN OTHERS THEN
        RAISE EXCEPTION
            'P2A rollback metadata restoration failed: owner'
            USING DETAIL = SQLERRM;
END
$restore_owner$;

DO $restore_relation_acl$
DECLARE
    acl_record RECORD;
    pass_number INTEGER;
    pending_count INTEGER;
    progress_made BOOLEAN;
    grant_applied BOOLEAN;
    grantee_sql TEXT;
    grant_option_sql TEXT;
BEGIN
    SELECT COUNT(*)
    INTO pending_count
    FROM pg_temp.p2a_base_relation_acl
    WHERE NOT restored;

    FOR pass_number IN 1..GREATEST(pending_count + 1, 1)
    LOOP
        progress_made := FALSE;

        FOR acl_record IN
            SELECT *
            FROM pg_temp.p2a_base_relation_acl
            WHERE NOT restored
            ORDER BY
                is_grantable DESC,
                grantor_name,
                grantee_name NULLS FIRST,
                privilege_type
        LOOP
            IF acl_record.privilege_type NOT IN (
                'SELECT',
                'INSERT',
                'UPDATE',
                'DELETE',
                'TRUNCATE',
                'REFERENCES',
                'TRIGGER',
                'MAINTAIN'
            ) THEN
                RAISE EXCEPTION
                    'Unsupported relation privilege type: %',
                    acl_record.privilege_type;
            END IF;

            grantee_sql := CASE
                WHEN acl_record.grantee_oid = 0 THEN 'PUBLIC'
                ELSE format('%I', acl_record.grantee_name)
            END;
            grant_option_sql := CASE
                WHEN acl_record.is_grantable THEN ' WITH GRANT OPTION'
                ELSE ''
            END;

            BEGIN
                EXECUTE format(
                    'SET LOCAL ROLE %I',
                    acl_record.grantor_name
                );
                EXECUTE format(
                    'GRANT %s ON TABLE %I.%I TO %s%s',
                    acl_record.privilege_type,
                    'core',
                    'v_client_credit_quality_base',
                    grantee_sql,
                    grant_option_sql
                );
                EXECUTE 'RESET ROLE';
            EXCEPTION
                WHEN insufficient_privilege THEN
                    EXECUTE 'RESET ROLE';
            END;

            SELECT EXISTS (
                SELECT 1
                FROM pg_class c
                CROSS JOIN LATERAL aclexplode(c.relacl) x
                WHERE c.oid = 'core.v_client_credit_quality_base'::regclass
                  AND x.grantor = acl_record.grantor_oid
                  AND x.grantee = acl_record.grantee_oid
                  AND x.privilege_type = acl_record.privilege_type
                  AND x.is_grantable = acl_record.is_grantable
            )
            INTO grant_applied;

            IF grant_applied THEN
                UPDATE pg_temp.p2a_base_relation_acl
                SET restored = TRUE
                WHERE grantor_oid = acl_record.grantor_oid
                  AND grantee_oid = acl_record.grantee_oid
                  AND privilege_type = acl_record.privilege_type
                  AND is_grantable = acl_record.is_grantable;
                progress_made := TRUE;
            END IF;
        END LOOP;

        EXIT WHEN NOT EXISTS (
            SELECT 1
            FROM pg_temp.p2a_base_relation_acl
            WHERE NOT restored
        );
        EXIT WHEN NOT progress_made;
    END LOOP;

    IF EXISTS (
        SELECT 1
        FROM pg_temp.p2a_base_relation_acl
        WHERE NOT restored
    ) THEN
        RAISE EXCEPTION
            'P2A rollback metadata restoration failed: relation ACL or grantor identity'
            USING DETAIL = (
                SELECT string_agg(
                    format(
                        'grantor=%I grantee=%s privilege=%s grantable=%s',
                        grantor_name,
                        CASE
                            WHEN grantee_oid = 0 THEN 'PUBLIC'
                            ELSE format('%I', grantee_name)
                        END,
                        privilege_type,
                        is_grantable
                    ),
                    '; '
                    ORDER BY grantor_name, grantee_name, privilege_type
                )
                FROM pg_temp.p2a_base_relation_acl
                WHERE NOT restored
            );
    END IF;
EXCEPTION
    WHEN OTHERS THEN
        IF SQLERRM LIKE 'P2A rollback metadata restoration failed:%' THEN
            RAISE;
        END IF;
        RAISE EXCEPTION
            'P2A rollback metadata restoration failed: relation ACL'
            USING DETAIL = SQLERRM;
END
$restore_relation_acl$;

DO $restore_column_acl$
DECLARE
    acl_record RECORD;
    pass_number INTEGER;
    pending_count INTEGER;
    progress_made BOOLEAN;
    grant_applied BOOLEAN;
    grantee_sql TEXT;
    grant_option_sql TEXT;
BEGIN
    SELECT COUNT(*)
    INTO pending_count
    FROM pg_temp.p2a_base_column_acl
    WHERE column_name NOT IN (
        'repeated_shift_invoice_count',
        'heavy_repeated_shift_invoice_count'
    )
      AND NOT restored;

    FOR pass_number IN 1..GREATEST(pending_count + 1, 1)
    LOOP
        progress_made := FALSE;

        FOR acl_record IN
            SELECT *
            FROM pg_temp.p2a_base_column_acl
            WHERE column_name NOT IN (
                'repeated_shift_invoice_count',
                'heavy_repeated_shift_invoice_count'
            )
              AND NOT restored
            ORDER BY
                is_grantable DESC,
                grantor_name,
                grantee_name NULLS FIRST,
                column_name,
                privilege_type
        LOOP
            IF acl_record.privilege_type NOT IN (
                'SELECT',
                'INSERT',
                'UPDATE',
                'REFERENCES'
            ) THEN
                RAISE EXCEPTION
                    'Unsupported column privilege type: %',
                    acl_record.privilege_type;
            END IF;

            grantee_sql := CASE
                WHEN acl_record.grantee_oid = 0 THEN 'PUBLIC'
                ELSE format('%I', acl_record.grantee_name)
            END;
            grant_option_sql := CASE
                WHEN acl_record.is_grantable THEN ' WITH GRANT OPTION'
                ELSE ''
            END;

            BEGIN
                EXECUTE format(
                    'SET LOCAL ROLE %I',
                    acl_record.grantor_name
                );
                EXECUTE format(
                    'GRANT %s (%I) ON TABLE %I.%I TO %s%s',
                    acl_record.privilege_type,
                    acl_record.column_name,
                    'core',
                    'v_client_credit_quality_base',
                    grantee_sql,
                    grant_option_sql
                );
                EXECUTE 'RESET ROLE';
            EXCEPTION
                WHEN insufficient_privilege THEN
                    EXECUTE 'RESET ROLE';
            END;

            SELECT EXISTS (
                SELECT 1
                FROM pg_attribute a
                CROSS JOIN LATERAL aclexplode(a.attacl) x
                WHERE a.attrelid =
                      'core.v_client_credit_quality_base'::regclass
                  AND a.attname = acl_record.column_name
                  AND x.grantor = acl_record.grantor_oid
                  AND x.grantee = acl_record.grantee_oid
                  AND x.privilege_type = acl_record.privilege_type
                  AND x.is_grantable = acl_record.is_grantable
            )
            INTO grant_applied;

            IF grant_applied THEN
                UPDATE pg_temp.p2a_base_column_acl
                SET restored = TRUE
                WHERE column_name = acl_record.column_name
                  AND grantor_oid = acl_record.grantor_oid
                  AND grantee_oid = acl_record.grantee_oid
                  AND privilege_type = acl_record.privilege_type
                  AND is_grantable = acl_record.is_grantable;
                progress_made := TRUE;
            END IF;
        END LOOP;

        EXIT WHEN NOT EXISTS (
            SELECT 1
            FROM pg_temp.p2a_base_column_acl
            WHERE column_name NOT IN (
                'repeated_shift_invoice_count',
                'heavy_repeated_shift_invoice_count'
            )
              AND NOT restored
        );
        EXIT WHEN NOT progress_made;
    END LOOP;

    IF EXISTS (
        SELECT 1
        FROM pg_temp.p2a_base_column_acl
        WHERE column_name NOT IN (
            'repeated_shift_invoice_count',
            'heavy_repeated_shift_invoice_count'
        )
          AND NOT restored
    ) THEN
        RAISE EXCEPTION
            'P2A rollback metadata restoration failed: column ACL or grantor identity'
            USING DETAIL = (
                SELECT string_agg(
                    format(
                        'column=%I grantor=%I grantee=%s privilege=%s grantable=%s',
                        column_name,
                        grantor_name,
                        CASE
                            WHEN grantee_oid = 0 THEN 'PUBLIC'
                            ELSE format('%I', grantee_name)
                        END,
                        privilege_type,
                        is_grantable
                    ),
                    '; '
                    ORDER BY
                        column_name,
                        grantor_name,
                        grantee_name,
                        privilege_type
                )
                FROM pg_temp.p2a_base_column_acl
                WHERE column_name NOT IN (
                    'repeated_shift_invoice_count',
                    'heavy_repeated_shift_invoice_count'
                )
                  AND NOT restored
            );
    END IF;
EXCEPTION
    WHEN OTHERS THEN
        IF SQLERRM LIKE 'P2A rollback metadata restoration failed:%' THEN
            RAISE;
        END IF;
        RAISE EXCEPTION
            'P2A rollback metadata restoration failed: column ACL'
            USING DETAIL = SQLERRM;
END
$restore_column_acl$;

DO $restore_reloptions$
DECLARE
    option_record RECORD;
    original_owner TEXT;
BEGIN
    SELECT owner_name
    INTO STRICT original_owner
    FROM pg_temp.p2a_base_relation_metadata;

    EXECUTE format('SET LOCAL ROLE %I', original_owner);

    FOR option_record IN
        SELECT option_name
        FROM pg_class c
        CROSS JOIN LATERAL pg_options_to_table(c.reloptions)
        WHERE c.oid = 'core.v_client_credit_quality_base'::regclass
        ORDER BY option_name
    LOOP
        EXECUTE format(
            'ALTER VIEW %I.%I RESET (%I)',
            'core',
            'v_client_credit_quality_base',
            option_record.option_name
        );
    END LOOP;

    FOR option_record IN
        SELECT option_name, option_value
        FROM pg_temp.p2a_base_reloptions
        ORDER BY option_name
    LOOP
        EXECUTE format(
            'ALTER VIEW %I.%I SET (%I = %L)',
            'core',
            'v_client_credit_quality_base',
            option_record.option_name,
            option_record.option_value
        );
    END LOOP;

    EXECUTE 'RESET ROLE';
EXCEPTION
    WHEN OTHERS THEN
        RAISE EXCEPTION
            'P2A rollback metadata restoration failed: reloptions and security settings'
            USING DETAIL = SQLERRM;
END
$restore_reloptions$;

DO $restore_comments_and_defaults$
DECLARE
    column_record RECORD;
    original_owner TEXT;
    original_relation_comment TEXT;
BEGIN
    SELECT metadata.owner_name, metadata.relation_comment
    INTO STRICT original_owner, original_relation_comment
    FROM pg_temp.p2a_base_relation_metadata metadata;

    EXECUTE format('SET LOCAL ROLE %I', original_owner);

    EXECUTE format(
        'COMMENT ON VIEW %I.%I IS %L',
        'core',
        'v_client_credit_quality_base',
        original_relation_comment
    );

    FOR column_record IN
        SELECT
            column_name,
            column_comment,
            default_expression
        FROM pg_temp.p2a_base_columns
        WHERE column_name NOT IN (
            'repeated_shift_invoice_count',
            'heavy_repeated_shift_invoice_count'
        )
        ORDER BY attnum
    LOOP
        EXECUTE format(
            'COMMENT ON COLUMN %I.%I.%I IS %L',
            'core',
            'v_client_credit_quality_base',
            column_record.column_name,
            column_record.column_comment
        );

        IF column_record.default_expression IS NOT NULL THEN
            EXECUTE format(
                'ALTER VIEW %I.%I ALTER COLUMN %I SET DEFAULT %s',
                'core',
                'v_client_credit_quality_base',
                column_record.column_name,
                column_record.default_expression
            );
        END IF;
    END LOOP;

    EXECUTE 'RESET ROLE';
EXCEPTION
    WHEN OTHERS THEN
        RAISE EXCEPTION
            'P2A rollback metadata restoration failed: comments or column defaults'
            USING DETAIL = SQLERRM;
END
$restore_comments_and_defaults$;

DO $restore_security_labels$
DECLARE
    label_record RECORD;
    original_owner TEXT;
    session_is_superuser BOOLEAN;
BEGIN
    SELECT owner_name
    INTO STRICT original_owner
    FROM pg_temp.p2a_base_relation_metadata;

    SELECT rolsuper
    INTO STRICT session_is_superuser
    FROM pg_roles
    WHERE rolname = session_user;

    IF NOT session_is_superuser THEN
        EXECUTE format('SET LOCAL ROLE %I', original_owner);
    END IF;

    FOR label_record IN
        SELECT objsubid, column_name, provider, label
        FROM pg_temp.p2a_base_security_labels
        WHERE column_name IS NULL
           OR column_name NOT IN (
               'repeated_shift_invoice_count',
               'heavy_repeated_shift_invoice_count'
           )
        ORDER BY objsubid, provider
    LOOP
        IF label_record.objsubid = 0 THEN
            EXECUTE format(
                'SECURITY LABEL FOR %I ON VIEW %I.%I IS %L',
                label_record.provider,
                'core',
                'v_client_credit_quality_base',
                label_record.label
            );
        ELSE
            EXECUTE format(
                'SECURITY LABEL FOR %I ON COLUMN %I.%I.%I IS %L',
                label_record.provider,
                'core',
                'v_client_credit_quality_base',
                label_record.column_name,
                label_record.label
            );
        END IF;
    END LOOP;

    IF NOT session_is_superuser THEN
        EXECUTE 'RESET ROLE';
    END IF;
EXCEPTION
    WHEN OTHERS THEN
        RAISE EXCEPTION
            'P2A rollback metadata restoration failed: security labels'
            USING DETAIL = (
                SQLERRM
                || '. The original provider must be loaded and the rollback role '
                || 'must be authorized by that provider.'
            );
END
$restore_security_labels$;

DO $restore_extension_membership$
DECLARE
    extension_record RECORD;
BEGIN
    FOR extension_record IN
        SELECT extname
        FROM pg_temp.p2a_base_extension_membership
        ORDER BY extname
    LOOP
        EXECUTE format(
            'ALTER EXTENSION %I ADD VIEW %I.%I',
            extension_record.extname,
            'core',
            'v_client_credit_quality_base'
        );
    END LOOP;
EXCEPTION
    WHEN OTHERS THEN
        RAISE EXCEPTION
            'P2A rollback metadata restoration failed: extension membership'
            USING DETAIL = SQLERRM;
END
$restore_extension_membership$;

DO $verify_restored_metadata$
DECLARE
    expected_owner TEXT;
    actual_owner TEXT;
    expected_comment TEXT;
    actual_comment TEXT;
BEGIN
    SELECT owner_name, relation_comment
    INTO STRICT expected_owner, expected_comment
    FROM pg_temp.p2a_base_relation_metadata;

    SELECT
        pg_get_userbyid(c.relowner),
        obj_description(c.oid, 'pg_class')
    INTO STRICT actual_owner, actual_comment
    FROM pg_class c
    WHERE c.oid = 'core.v_client_credit_quality_base'::regclass;

    IF actual_owner IS DISTINCT FROM expected_owner THEN
        RAISE EXCEPTION
            'P2A rollback metadata verification failed: owner'
            USING DETAIL = format(
                'expected=%L actual=%L',
                expected_owner,
                actual_owner
            );
    END IF;

    IF actual_comment IS DISTINCT FROM expected_comment THEN
        RAISE EXCEPTION
            'P2A rollback metadata verification failed: view comment';
    END IF;

    IF EXISTS (
        (
            SELECT
                x.grantor,
                x.grantee,
                x.privilege_type,
                x.is_grantable
            FROM pg_class c
            CROSS JOIN LATERAL aclexplode(c.relacl) x
            WHERE c.oid = 'core.v_client_credit_quality_base'::regclass

            EXCEPT ALL

            SELECT
                grantor_oid,
                grantee_oid,
                privilege_type,
                is_grantable
            FROM pg_temp.p2a_base_relation_acl
        )
        UNION ALL
        (
            SELECT
                grantor_oid,
                grantee_oid,
                privilege_type,
                is_grantable
            FROM pg_temp.p2a_base_relation_acl

            EXCEPT ALL

            SELECT
                x.grantor,
                x.grantee,
                x.privilege_type,
                x.is_grantable
            FROM pg_class c
            CROSS JOIN LATERAL aclexplode(c.relacl) x
            WHERE c.oid = 'core.v_client_credit_quality_base'::regclass
        )
    ) THEN
        RAISE EXCEPTION
            'P2A rollback metadata verification failed: relation ACL';
    END IF;

    IF EXISTS (
        (
            SELECT option_name, option_value
            FROM pg_class c
            CROSS JOIN LATERAL pg_options_to_table(c.reloptions)
            WHERE c.oid = 'core.v_client_credit_quality_base'::regclass

            EXCEPT ALL

            SELECT option_name, option_value
            FROM pg_temp.p2a_base_reloptions
        )
        UNION ALL
        (
            SELECT option_name, option_value
            FROM pg_temp.p2a_base_reloptions

            EXCEPT ALL

            SELECT option_name, option_value
            FROM pg_class c
            CROSS JOIN LATERAL pg_options_to_table(c.reloptions)
            WHERE c.oid = 'core.v_client_credit_quality_base'::regclass
        )
    ) THEN
        RAISE EXCEPTION
            'P2A rollback metadata verification failed: reloptions';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_temp.p2a_base_columns expected
        JOIN pg_attribute actual_attribute
          ON actual_attribute.attrelid =
             'core.v_client_credit_quality_base'::regclass
         AND actual_attribute.attname = expected.column_name
         AND actual_attribute.attnum > 0
         AND NOT actual_attribute.attisdropped
        LEFT JOIN pg_attrdef actual_default
          ON actual_default.adrelid = actual_attribute.attrelid
         AND actual_default.adnum = actual_attribute.attnum
        WHERE expected.column_name NOT IN (
            'repeated_shift_invoice_count',
            'heavy_repeated_shift_invoice_count'
        )
          AND (
              col_description(
                  actual_attribute.attrelid,
                  actual_attribute.attnum
              ) IS DISTINCT FROM expected.column_comment
              OR pg_get_expr(
                  actual_default.adbin,
                  actual_default.adrelid
              ) IS DISTINCT FROM expected.default_expression
          )
    ) THEN
        RAISE EXCEPTION
            'P2A rollback metadata verification failed: column comments or defaults';
    END IF;

    IF EXISTS (
        (
            SELECT
                a.attname,
                x.grantor,
                x.grantee,
                x.privilege_type,
                x.is_grantable
            FROM pg_attribute a
            CROSS JOIN LATERAL aclexplode(a.attacl) x
            WHERE a.attrelid =
                  'core.v_client_credit_quality_base'::regclass
              AND a.attnum > 0
              AND NOT a.attisdropped

            EXCEPT ALL

            SELECT
                column_name,
                grantor_oid,
                grantee_oid,
                privilege_type,
                is_grantable
            FROM pg_temp.p2a_base_column_acl
            WHERE column_name NOT IN (
                'repeated_shift_invoice_count',
                'heavy_repeated_shift_invoice_count'
            )
        )
        UNION ALL
        (
            SELECT
                column_name,
                grantor_oid,
                grantee_oid,
                privilege_type,
                is_grantable
            FROM pg_temp.p2a_base_column_acl
            WHERE column_name NOT IN (
                'repeated_shift_invoice_count',
                'heavy_repeated_shift_invoice_count'
            )

            EXCEPT ALL

            SELECT
                a.attname,
                x.grantor,
                x.grantee,
                x.privilege_type,
                x.is_grantable
            FROM pg_attribute a
            CROSS JOIN LATERAL aclexplode(a.attacl) x
            WHERE a.attrelid =
                  'core.v_client_credit_quality_base'::regclass
              AND a.attnum > 0
              AND NOT a.attisdropped
        )
    ) THEN
        RAISE EXCEPTION
            'P2A rollback metadata verification failed: column ACL';
    END IF;

    IF EXISTS (
        (
            SELECT
                s.objsubid,
                a.attname,
                s.provider,
                s.label
            FROM pg_seclabel s
            LEFT JOIN pg_attribute a
              ON a.attrelid = s.objoid
             AND a.attnum = s.objsubid
            WHERE s.classoid = 'pg_class'::regclass
              AND s.objoid =
                  'core.v_client_credit_quality_base'::regclass

            EXCEPT ALL

            SELECT objsubid, column_name, provider, label
            FROM pg_temp.p2a_base_security_labels
            WHERE column_name IS NULL
               OR column_name NOT IN (
                   'repeated_shift_invoice_count',
                   'heavy_repeated_shift_invoice_count'
               )
        )
        UNION ALL
        (
            SELECT objsubid, column_name, provider, label
            FROM pg_temp.p2a_base_security_labels
            WHERE column_name IS NULL
               OR column_name NOT IN (
                   'repeated_shift_invoice_count',
                   'heavy_repeated_shift_invoice_count'
               )

            EXCEPT ALL

            SELECT
                s.objsubid,
                a.attname,
                s.provider,
                s.label
            FROM pg_seclabel s
            LEFT JOIN pg_attribute a
              ON a.attrelid = s.objoid
             AND a.attnum = s.objsubid
            WHERE s.classoid = 'pg_class'::regclass
              AND s.objoid =
                  'core.v_client_credit_quality_base'::regclass
        )
    ) THEN
        RAISE EXCEPTION
            'P2A rollback metadata verification failed: security labels';
    END IF;
END
$verify_restored_metadata$;

COMMIT;
