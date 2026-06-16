-- Create raw flights table
-- This is where all 3 sources land before any processing
CREATE TABLE IF NOT EXISTS raw_flights (
    id SERIAL PRIMARY KEY,
    airline_name VARCHAR(255),
    flight_number VARCHAR(50),
    origin_city VARCHAR(255),
    destination_city VARCHAR(255),
    origin_airport_code VARCHAR(10),
    destination_airport_code VARCHAR(10),
    departure_time VARCHAR(50),
    arrival_time VARCHAR(50),
    duration_hours FLOAT,
    price FLOAT,
    currency VARCHAR(10),
    num_stops VARCHAR(50),
    travel_class VARCHAR(50),
    days_until_departure INTEGER,
    departure_delay_mins FLOAT,
    arrival_delay_mins FLOAT,
    distance_miles FLOAT,
    is_cancelled INTEGER,
    is_diverted INTEGER,
    data_source VARCHAR(50),
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create lineage log table
-- Every single row that enters our pipeline gets recorded here
CREATE TABLE IF NOT EXISTS lineage_log (
    id SERIAL PRIMARY KEY,
    source_name VARCHAR(50),
    record_id INTEGER,
    raw_table VARCHAR(100),
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    row_hash VARCHAR(255),
    status VARCHAR(50)
);

-- Create conflict log table
-- When two sources disagree on the same data, we record it here
CREATE TABLE IF NOT EXISTS conflict_log (
    id SERIAL PRIMARY KEY,
    field_name VARCHAR(100),
    source_1 VARCHAR(50),
    value_1 TEXT,
    source_2 VARCHAR(50),
    value_2 TEXT,
    resolution VARCHAR(255),
    resolved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create quarantine table
-- Rows that fail quality checks land here instead of the main table
CREATE TABLE IF NOT EXISTS quarantine (
    id SERIAL PRIMARY KEY,
    original_table VARCHAR(100),
    data_source VARCHAR(50),
    raw_data TEXT,
    failure_reason TEXT,
    quarantined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create unified flights table
-- This is the clean final table after conflict resolution
CREATE TABLE IF NOT EXISTS unified_flights (
    id SERIAL PRIMARY KEY,
    airline_name VARCHAR(255),
    flight_number VARCHAR(50),
    origin_city VARCHAR(255),
    destination_city VARCHAR(255),
    origin_airport_code VARCHAR(10),
    destination_airport_code VARCHAR(10),
    duration_hours FLOAT,
    price FLOAT,
    currency VARCHAR(10),
    num_stops VARCHAR(50),
    travel_class VARCHAR(50),
    days_until_departure INTEGER,
    departure_delay_mins FLOAT,
    arrival_delay_mins FLOAT,
    distance_miles FLOAT,
    is_cancelled INTEGER,
    data_source VARCHAR(50),
    conflict_flag BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);