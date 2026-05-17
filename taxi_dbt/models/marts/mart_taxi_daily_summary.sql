-- ============================================================
-- Model      : mart_taxi_daily_summary
-- Layer      : Marts
-- Description: Daily aggregated taxi metrics.
--              Business-level table consumed by dashboards.
-- Owner      : Data Engineering
-- ============================================================

WITH daily AS (
    SELECT
        trip_date,
        company,
        payment_type,

        -- volume metrics
        COUNT(*)                        AS total_trips,
        COUNT(DISTINCT unique_key)      AS unique_trips,

        -- revenue metrics
        ROUND(SUM(fare), 2)             AS total_fare,
        ROUND(AVG(fare), 2)             AS avg_fare,
        ROUND(MIN(fare), 2)             AS min_fare,
        ROUND(MAX(fare), 2)             AS max_fare,
        ROUND(SUM(tips), 2)             AS total_tips,
        ROUND(SUM(trip_total), 2)       AS total_revenue,

        -- distance + duration metrics
        ROUND(AVG(trip_miles), 2)       AS avg_trip_miles,
        ROUND(AVG(trip_duration_minutes), 2) AS avg_trip_duration_minutes

    FROM {{ ref('stg_taxi_trips') }}     -- ref() declares dependency on staging
    GROUP BY trip_date, company, payment_type
)

SELECT * FROM daily
ORDER BY trip_date DESC, total_trips DESC