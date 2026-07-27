-- Read-only post-rollback verification for migration 038.
-- The rollback itself compares captured metadata before COMMIT. Compare the
-- normalized result sets below with the saved preflight evidence as an
-- independent deployment record; OID equality is intentionally not required.

WITH expected_columns(ordinal_position, column_name, data_type) AS (
    VALUES
        (1, 'client_id', 'text'),
        (2, 'client_name', 'text'),
        (3, 'client_group', 'text'),
        (4, 'parent_org_id', 'text'),
        (5, 'base_stars', 'integer'),
        (6, 'base_rating_label', 'text'),
        (7, 'base_rating_display_label', 'text'),
        (8, 'confidence_level', 'text'),
        (9, 'total_debt', 'numeric'),
        (10, 'overdue_debt', 'numeric'),
        (11, 'green_debt', 'numeric'),
        (12, 'green_45_plus_debt', 'numeric'),
        (13, 'green_60_plus_debt', 'numeric'),
        (14, 'green_90_plus_debt', 'numeric'),
        (15, 'green_120_plus_debt', 'numeric'),
        (16, 'overdue_share_pct', 'numeric'),
        (17, 'green_90_plus_share_pct', 'numeric'),
        (18, 'green_120_plus_share_pct', 'numeric'),
        (19, 'weighted_avg_payment_term_days', 'numeric'),
        (20, 'max_payment_term_days', 'integer'),
        (21, 'max_days_overdue', 'integer'),
        (22, 'invoice_count', 'bigint'),
        (23, 'term_shift_count', 'numeric'),
        (24, 'max_invoice_term_shift_count', 'bigint'),
        (25, 'total_term_shift_delta_days', 'bigint'),
        (26, 'max_term_shift_delta_days', 'integer'),
        (27, 'exposure_segment', 'text'),
        (28, 'exposure_multiplier', 'numeric')
),
actual_columns AS (
    SELECT
        a.attnum::INTEGER AS ordinal_position,
        a.attname::TEXT AS column_name,
        format_type(a.atttypid, a.atttypmod) AS data_type
    FROM pg_attribute a
    WHERE a.attrelid = 'core.v_client_credit_quality_base'::regclass
      AND a.attnum > 0
      AND NOT a.attisdropped
),
column_differences AS (
    (
        SELECT * FROM expected_columns
        EXCEPT ALL
        SELECT * FROM actual_columns
    )
    UNION ALL
    (
        SELECT * FROM actual_columns
        EXCEPT ALL
        SELECT * FROM expected_columns
    )
)
SELECT
    (SELECT COUNT(*) FROM column_differences) AS column_signature_differences,
    CASE
        WHEN pg_get_viewdef(
            'core.v_client_credit_quality_base'::regclass,
            true
        ) LIKE '%repeated_shift_invoice_count%'
          OR pg_get_viewdef(
            'core.v_client_credit_quality_base'::regclass,
            true
        ) LIKE '%heavy_repeated_shift_invoice_count%'
        THEN 1 ELSE 0
    END AS unexpected_p2a_base_definition_matches,
    CASE
        WHEN pg_get_viewdef(
            'core.v_client_credit_quality_severity'::regclass,
            true
        ) NOT LIKE '%v_term_shift_invoice_summary%'
        THEN 1 ELSE 0
    END AS missing_restored_severity_expansion,
    to_regclass('core.v_client_credit_quality_severity') IS NOT NULL
        AS severity_view_exists,
    to_regclass('core.v_client_credit_quality_rating') IS NOT NULL
        AS rating_view_exists;


SELECT
    pg_get_userbyid(c.relowner) AS owner_name,
    c.relacl::text AS raw_relation_acl,
    c.reloptions AS raw_reloptions,
    obj_description(c.oid, 'pg_class') AS view_comment,
    pg_get_viewdef(c.oid, true) AS view_definition
FROM pg_class c
WHERE c.oid = 'core.v_client_credit_quality_base'::regclass;


SELECT
    pg_get_userbyid(acl.grantor) AS grantor,
    CASE
        WHEN acl.grantee = 0 THEN 'PUBLIC'
        ELSE pg_get_userbyid(acl.grantee)
    END AS grantee,
    acl.privilege_type,
    acl.is_grantable
FROM pg_class c
CROSS JOIN LATERAL aclexplode(c.relacl) acl
WHERE c.oid = 'core.v_client_credit_quality_base'::regclass
ORDER BY grantor, grantee, privilege_type, is_grantable;


SELECT
    a.attnum AS ordinal_position,
    a.attname AS column_name,
    format_type(a.atttypid, a.atttypmod) AS data_type,
    a.attacl::text AS raw_column_acl,
    col_description(a.attrelid, a.attnum) AS column_comment,
    pg_get_expr(ad.adbin, ad.adrelid) AS default_expression,
    a.attoptions AS column_options
FROM pg_attribute a
LEFT JOIN pg_attrdef ad
    ON ad.adrelid = a.attrelid
   AND ad.adnum = a.attnum
WHERE a.attrelid = 'core.v_client_credit_quality_base'::regclass
  AND a.attnum > 0
  AND NOT a.attisdropped
ORDER BY a.attnum;


SELECT
    a.attname AS column_name,
    pg_get_userbyid(acl.grantor) AS grantor,
    CASE
        WHEN acl.grantee = 0 THEN 'PUBLIC'
        ELSE pg_get_userbyid(acl.grantee)
    END AS grantee,
    acl.privilege_type,
    acl.is_grantable
FROM pg_attribute a
CROSS JOIN LATERAL aclexplode(a.attacl) acl
WHERE a.attrelid = 'core.v_client_credit_quality_base'::regclass
  AND a.attnum > 0
  AND NOT a.attisdropped
ORDER BY column_name, grantor, grantee, privilege_type, is_grantable;


SELECT option_name, option_value
FROM pg_class c
CROSS JOIN LATERAL pg_options_to_table(c.reloptions)
WHERE c.oid = 'core.v_client_credit_quality_base'::regclass
ORDER BY option_name;


SELECT
    labels.objsubid,
    attributes.attname AS column_name,
    labels.provider,
    labels.label
FROM pg_seclabel labels
LEFT JOIN pg_attribute attributes
    ON attributes.attrelid = labels.objoid
   AND attributes.attnum = labels.objsubid
WHERE labels.classoid = 'pg_class'::regclass
  AND labels.objoid = 'core.v_client_credit_quality_base'::regclass
ORDER BY labels.objsubid, labels.provider;


SELECT DISTINCT
    dependency.deptype,
    pg_describe_object(
        dependency.classid,
        dependency.objid,
        dependency.objsubid
    ) AS dependent_or_member_object,
    pg_describe_object(
        dependency.refclassid,
        dependency.refobjid,
        dependency.refobjsubid
    ) AS referenced_object
FROM pg_depend dependency
WHERE dependency.objid = 'core.v_client_credit_quality_base'::regclass
   OR dependency.refobjid = 'core.v_client_credit_quality_base'::regclass
ORDER BY dependent_or_member_object, referenced_object, dependency.deptype;


SELECT * FROM core.v_client_credit_quality_severity LIMIT 0;
SELECT * FROM core.v_client_credit_quality_rating LIMIT 0;
