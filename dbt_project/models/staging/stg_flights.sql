-- Staging model for raw flights
-- This is the first transformation layer
-- We clean, cast and standardize data types here
-- No business logic yet — just making data usable

{{ config(materialized='view') }}

-- What 'materialized=view' means:
-- dbt creates a VIEW in PostgreSQL, not a physical table
-- A view is like a saved query — no data is stored
-- Every time you query it, it runs the SQL fresh
-- Good for staging because we always want latest raw data

SELECT
    id,

    -- Clean airline name — trim whitespace
    TRIM(airline_name)                          AS airline_name,

    -- Clean flight number — cast to text for consistency
    -- Indian dataset has text like 'SG-8709'
    -- US dataset has integers like 98
    -- We cast everything to text so they match
    CAST(flight_number AS VARCHAR)              AS flight_number,

    -- Clean city names — trim and proper case
    TRIM(origin_city)                           AS origin_city,
    TRIM(destination_city)                      AS destination_city,

    -- Airport codes — uppercase for consistency
    UPPER(TRIM(origin_airport_code))            AS origin_airport_code,
    UPPER(TRIM(destination_airport_code))       AS destination_airport_code,

    -- Duration — round to 2 decimal places
    ROUND(CAST(duration_hours AS NUMERIC), 2)   AS duration_hours,

    -- Price — cast to numeric, keep nulls
    CAST(price AS NUMERIC)                      AS price,

    -- Currency — uppercase
    UPPER(TRIM(currency))                       AS currency,

    -- Stops — clean text
    TRIM(num_stops)                             AS num_stops,

    -- Travel class — proper case
    TRIM(travel_class)                          AS travel_class,

    -- Days until departure — keep as integer
    CAST(days_until_departure AS INTEGER)       AS days_until_departure,

    -- Delay columns — keep as numeric
    CAST(departure_delay_mins AS NUMERIC)       AS departure_delay_mins,
    CAST(arrival_delay_mins AS NUMERIC)         AS arrival_delay_mins,

    -- Distance — keep as numeric
    CAST(distance_miles AS NUMERIC)             AS distance_miles,

    -- Cancelled flag — convert to boolean
    CASE
        WHEN is_cancelled = 1 THEN TRUE
        WHEN is_cancelled = 0 THEN FALSE
        ELSE NULL
    END                                         AS is_cancelled,

    -- Flight status from API
    TRIM(flight_status)                         AS flight_status,

    -- Data source — always keep this for lineage
    data_source,

    -- Conflict flag — default to false if not present
    FALSE AS conflict_flag,

    -- When this row was ingested
    ingested_at

FROM {{ source('flight_raw', 'raw_flights') }}

-- Filter out test rows
WHERE data_source != 'test'