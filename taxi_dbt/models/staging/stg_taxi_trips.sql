-- ============================================================
-- Model      : stg_taxi_trips
-- Layer      : Staging
-- Description: Cleans and standardizes raw Chicago taxi data.
--              Applies basic filters and type casts.
--              1:1 with source — no joins or aggregations here.
-- Owner      : Data Engineering
-- ============================================================

WITH source AS (
    SELECT * FROM {{ source('chicago_taxi', 'taxi_trips') }}
    WHERE trip_start_timestamp >= '2023-01-01'
    LIMIT 10000    -- remove in production
),

cleaned AS (
    SELECT
        unique_key,
        trip_start_timestamp,
        trip_end_timestamp,

        -- cast and clean numerics
        CAST(trip_seconds AS FLOAT64)                    AS trip_seconds,
        CAST(trip_miles   AS FLOAT64)                    AS trip_miles,
        CAST(fare         AS FLOAT64)                    AS fare,
        CAST(tips         AS FLOAT64)                    AS tips,
        CAST(trip_total   AS FLOAT64)                    AS trip_total,

        -- standardize payment type
        INITCAP(TRIM(payment_type))                      AS payment_type,
        TRIM(company)                                    AS company,

        -- derived columns
        DATE(trip_start_timestamp)                       AS trip_date,
        TIMESTAMP_DIFF(
            trip_end_timestamp,
            trip_start_timestamp,
            MINUTE
        )                                                AS trip_duration_minutes

    FROM source

    -- contract-equivalent filters (dbt style)
    WHERE fare         >= 0
      AND trip_miles   >= 0
      AND unique_key   IS NOT NULL
)

SELECT * FROM cleaned