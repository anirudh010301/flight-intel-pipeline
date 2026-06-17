-- Marts layer
-- Builds on top of ODS layer
-- Creates analytics-ready aggregations
-- This is what the dashboard and ML model will use

{{ config(materialized='table') }}

WITH ods AS (
    SELECT * FROM {{ ref('ods_flights') }}
),

-- Aggregation 1 — Route level stats
-- For each route, calculate average price, duration and delay
route_stats AS (
    SELECT
        origin_city,
        destination_city,
        data_source,
        flight_type,
        COUNT(*)                                    AS total_flights,
        ROUND(AVG(price)::NUMERIC, 2)               AS avg_price,
        ROUND(MIN(price)::NUMERIC, 2)               AS min_price,
        ROUND(MAX(price)::NUMERIC, 2)               AS max_price,
        ROUND(AVG(duration_hours)::NUMERIC, 2)      AS avg_duration_hours,
        ROUND(AVG(departure_delay_mins)::NUMERIC, 2) AS avg_delay_mins,
        COUNT(CASE WHEN is_cancelled = TRUE THEN 1 END) AS cancelled_flights,
        COUNT(CASE WHEN has_full_data = TRUE THEN 1 END) AS ml_ready_rows
    FROM ods
    GROUP BY
        origin_city,
        destination_city,
        data_source,
        flight_type
),

-- Aggregation 2 — Airline level stats
airline_stats AS (
    SELECT
        airline_name,
        data_source,
        COUNT(*)                                        AS total_flights,
        ROUND(AVG(price)::NUMERIC, 2)                  AS avg_price,
        ROUND(AVG(duration_hours)::NUMERIC, 2)         AS avg_duration_hours,
        ROUND(AVG(departure_delay_mins)::NUMERIC, 2)   AS avg_delay_mins,
        COUNT(CASE WHEN delay_category = 'on_time' THEN 1 END) AS on_time_flights,
        COUNT(CASE WHEN delay_category = 'severe_delay' THEN 1 END) AS severe_delay_flights
    FROM ods
    GROUP BY
        airline_name,
        data_source
),

-- Final mart — join route and airline stats back to flight level
final AS (
    SELECT
        o.id,
        o.airline_name,
        o.flight_number,
        o.origin_city,
        o.destination_city,
        o.origin_airport_code,
        o.destination_airport_code,
        o.duration_hours,
        o.price,
        o.currency,
        o.num_stops,
        o.travel_class,
        o.days_until_departure,
        o.departure_delay_mins,
        o.arrival_delay_mins,
        o.distance_miles,
        o.is_cancelled,
        o.flight_status,
        o.flight_type,
        o.price_category,
        o.duration_category,
        o.delay_category,
        o.has_full_data,
        o.data_source,
        o.conflict_flag,
        o.ingested_at,

        -- Route level enrichment
        rs.total_flights        AS route_total_flights,
        rs.avg_price            AS route_avg_price,
        rs.min_price            AS route_min_price,
        rs.max_price            AS route_max_price,
        rs.avg_duration_hours   AS route_avg_duration,
        rs.avg_delay_mins       AS route_avg_delay,
        rs.cancelled_flights    AS route_cancelled_flights,
        rs.ml_ready_rows        AS route_ml_ready_rows,

        -- Airline level enrichment
        als.total_flights       AS airline_total_flights,
        als.avg_price           AS airline_avg_price,
        als.avg_delay_mins      AS airline_avg_delay,
        als.on_time_flights     AS airline_on_time_flights,
        als.severe_delay_flights AS airline_severe_delay_flights

    FROM ods o
    LEFT JOIN route_stats rs
        ON o.origin_city = rs.origin_city
        AND o.destination_city = rs.destination_city
        AND o.data_source = rs.data_source
    LEFT JOIN airline_stats als
        ON o.airline_name = als.airline_name
        AND o.data_source = als.data_source
)

SELECT * FROM final