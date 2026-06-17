-- ODS (Operational Data Store) layer
-- Builds on top of staging layer
-- Adds business logic, filters and enrichment
-- This is the clean, analytics-ready version of our data

{{ config(materialized='table') }}

-- What 'materialized=table' means:
-- dbt creates a physical TABLE in PostgreSQL
-- Data is actually stored — not recalculated every query
-- Good for ODS because it's queried frequently by ML and dashboard

WITH source AS (
    -- Reference staging model using dbt ref()
    -- ref() tells dbt this model depends on stg_flights
    -- dbt builds a dependency graph automatically
    SELECT * FROM {{ ref('stg_flights') }}
),

cleaned AS (
    SELECT
        id,
        airline_name,
        flight_number,
        origin_city,
        destination_city,
        origin_airport_code,
        destination_airport_code,
        duration_hours,
        price,
        currency,
        num_stops,
        travel_class,
        days_until_departure,
        departure_delay_mins,
        arrival_delay_mins,
        distance_miles,
        is_cancelled,
        flight_status,
        data_source,
        conflict_flag,
        ingested_at,

        -- Classify flight as domestic or international
        -- Indian dataset = domestic Indian flights
        -- US dataset = domestic US flights
        -- API = international flights
        CASE
            WHEN data_source = 'kaggle_indian' THEN 'domestic_india'
            WHEN data_source = 'kaggle_us' THEN 'domestic_us'
            WHEN data_source = 'aviationstack_api' THEN 'international'
            ELSE 'unknown'
        END AS flight_type,

        -- Classify price into budget/mid/premium
        -- Only for Indian flights which have price data
        CASE
            WHEN price IS NULL THEN 'unknown'
            WHEN price < 5000 THEN 'budget'
            WHEN price BETWEEN 5000 AND 15000 THEN 'mid'
            WHEN price > 15000 THEN 'premium'
            ELSE 'unknown'
        END AS price_category,

        -- Classify duration into short/medium/long
        CASE
            WHEN duration_hours IS NULL THEN 'unknown'
            WHEN duration_hours < 2 THEN 'short'
            WHEN duration_hours BETWEEN 2 AND 5 THEN 'medium'
            WHEN duration_hours > 5 THEN 'long'
            ELSE 'unknown'
        END AS duration_category,

        -- Classify delay severity
        CASE
            WHEN departure_delay_mins IS NULL THEN 'unknown'
            WHEN departure_delay_mins <= 0 THEN 'on_time'
            WHEN departure_delay_mins BETWEEN 1 AND 30 THEN 'minor_delay'
            WHEN departure_delay_mins BETWEEN 31 AND 120 THEN 'major_delay'
            WHEN departure_delay_mins > 120 THEN 'severe_delay'
            ELSE 'unknown'
        END AS delay_category,

        -- Flag routes that have both price and delay data
        -- These are the most valuable rows for ML
        CASE
            WHEN price IS NOT NULL AND departure_delay_mins IS NOT NULL THEN TRUE
            ELSE FALSE
        END AS has_full_data

    FROM source

    -- Filter out rows where both origin and destination are null
    WHERE origin_city IS NOT NULL
    AND destination_city IS NOT NULL
)

SELECT * FROM cleaned