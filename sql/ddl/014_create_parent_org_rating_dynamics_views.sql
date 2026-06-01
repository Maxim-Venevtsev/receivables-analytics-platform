CREATE OR REPLACE VIEW core.v_parent_org_rating_dynamics AS
WITH current_clients AS (
    SELECT
        parent_org_id,
        client_id,
        client_name,
        client_group,
        SUM(invoice_amount) AS total_debt
    FROM core.v_receivables_current_snapshot
    GROUP BY
        parent_org_id,
        client_id,
        client_name,
        client_group
),

rating_latest AS (
    SELECT
        client_id,
        stars,
        previous_stars,
        rating_delta,
        rating_change_status,
        snapshot_date,
        previous_snapshot_date
    FROM core.v_client_rating_latest_dynamics
),

joined AS (
    SELECT
        c.parent_org_id,
        c.client_id,
        c.client_name,
        c.client_group,
        c.total_debt,

        r.stars,
        r.previous_stars,
        r.rating_delta,
        r.rating_change_status,
        r.snapshot_date,
        r.previous_snapshot_date,

        CASE
            WHEN c.total_debt > 0 AND r.stars IS NOT NULL
            THEN c.total_debt
            ELSE 0
        END AS rating_weight

    FROM current_clients c
    LEFT JOIN rating_latest r
        ON c.client_id = r.client_id
),

aggregated AS (
    SELECT
        parent_org_id,

        MAX(snapshot_date) AS snapshot_date,
        MAX(previous_snapshot_date) AS previous_snapshot_date,

        COUNT(DISTINCT client_id) AS clients_total,

        COUNT(DISTINCT CASE WHEN stars IS NOT NULL THEN client_id END) AS clients_with_rating,

        SUM(total_debt) AS total_debt,

        CASE
            WHEN SUM(rating_weight) = 0 THEN NULL
            ELSE ROUND(
                SUM(stars * rating_weight) / NULLIF(SUM(rating_weight), 0),
                2
            )
        END AS weighted_rating,

        COUNT(DISTINCT CASE WHEN rating_change_status = 'IMPROVED' THEN client_id END) AS clients_improved,
        COUNT(DISTINCT CASE WHEN rating_change_status = 'WORSENED' THEN client_id END) AS clients_worsened,
        COUNT(DISTINCT CASE WHEN rating_change_status = 'STABLE' THEN client_id END) AS clients_stable,
        COUNT(DISTINCT CASE WHEN rating_change_status = 'NEW' THEN client_id END) AS clients_new,

        SUM(CASE WHEN rating_change_status = 'IMPROVED' THEN total_debt ELSE 0 END) AS improved_debt,
        SUM(CASE WHEN rating_change_status = 'WORSENED' THEN total_debt ELSE 0 END) AS worsened_debt

    FROM joined
    GROUP BY parent_org_id
)

SELECT
    *,

    CASE
        WHEN clients_worsened > clients_improved THEN 'WORSENED'
        WHEN clients_improved > clients_worsened THEN 'IMPROVED'
        WHEN clients_new = clients_with_rating THEN 'NEW'
        ELSE 'STABLE'
    END AS portfolio_change_status,

    CASE
        WHEN clients_worsened > clients_improved THEN 'Портфель ухудшается'
        WHEN clients_improved > clients_worsened THEN 'Портфель улучшается'
        WHEN clients_new = clients_with_rating THEN 'Первая фиксация рейтингов'
        ELSE 'Портфель стабилен'
    END AS portfolio_change_label

FROM aggregated;