-- Read-only production preflight for migration/rollback 038.
-- Save every result set before deployment. The rollback captures and restores
-- these values automatically; this output is independent verification evidence.

SELECT
    current_database() AS database_name,
    current_user AS current_user_name,
    current_setting('server_version') AS server_version,
    n.nspname AS schema_name,
    c.relname AS view_name,
    c.oid AS current_oid,
    pg_get_userbyid(c.relowner) AS owner_name,
    c.relacl::text AS raw_relation_acl,
    c.reloptions AS raw_reloptions,
    obj_description(c.oid, 'pg_class') AS view_comment,
    pg_get_viewdef(c.oid, true) AS view_definition
FROM pg_class c
JOIN pg_namespace n
    ON n.oid = c.relnamespace
WHERE n.nspname = 'core'
  AND c.relname = 'v_client_credit_quality_base'
  AND c.relkind = 'v';


SELECT
    options.option_name,
    options.option_value
FROM pg_class c
CROSS JOIN LATERAL pg_options_to_table(c.reloptions) options
WHERE c.oid = 'core.v_client_credit_quality_base'::regclass
ORDER BY options.option_name;


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


SELECT
    CASE
        WHEN EXISTS (
            SELECT 1
            FROM pg_attribute a
            LEFT JOIN pg_attrdef ad
                ON ad.adrelid = a.attrelid
               AND ad.adnum = a.attnum
            WHERE a.attrelid =
                  'core.v_client_credit_quality_base'::regclass
              AND a.attname IN (
                  'repeated_shift_invoice_count',
                  'heavy_repeated_shift_invoice_count'
              )
              AND (
                  a.attacl IS NOT NULL
                  OR col_description(a.attrelid, a.attnum) IS NOT NULL
                  OR ad.oid IS NOT NULL
                  OR COALESCE(cardinality(a.attoptions), 0) > 0
                  OR EXISTS (
                      SELECT 1
                      FROM pg_seclabel labels
                      WHERE labels.classoid = 'pg_class'::regclass
                        AND labels.objoid = a.attrelid
                        AND labels.objsubid = a.attnum
                  )
              )
        )
        THEN 'BLOCKED: P2A-only column metadata cannot survive column removal'
        ELSE 'OK'
    END AS rollback_removed_column_metadata_preflight;
