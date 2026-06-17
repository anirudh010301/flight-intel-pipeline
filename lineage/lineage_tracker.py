import hashlib
import json
import psycopg2
import pandas as pd
from loguru import logger
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

def get_connection():
    """
    Creates and returns a psycopg2 database connection.
    We use psycopg2 directly instead of SQLAlchemy
    to avoid version conflicts with Airflow.
    """
    return psycopg2.connect(
        host=os.getenv('POSTGRES_HOST'),
        port=os.getenv('POSTGRES_PORT'),
        user=os.getenv('POSTGRES_USER'),
        password=os.getenv('POSTGRES_PASSWORD'),
        dbname=os.getenv('POSTGRES_DB')
    )

def generate_row_hash(row):
    """
    Generates a unique hash for each row.
    A hash is a fixed-length fingerprint of the data.
    If two rows have the same hash — they are identical.
    This helps us detect duplicates across sources.
    """
    row_str = json.dumps(dict(row), sort_keys=True, default=str)
    return hashlib.md5(row_str.encode()).hexdigest()

def load_to_raw(df, source_name):
    """
    Loads a DataFrame into the raw_flights table.
    Records every row in the lineage_log.
    This is the entry point for all data into our pipeline.
    """
    logger.info(f"Loading {len(df)} rows from {source_name} into raw_flights...")

    conn = get_connection()
    cursor = conn.cursor()

    # Define allowed columns — must match raw_flights table
    allowed_cols = [
        'airline_name', 'airline_iata', 'flight_number', 'origin_city',
        'origin_state', 'destination_city', 'destination_state',
        'origin_airport_code', 'destination_airport_code',
        'departure_time', 'arrival_time', 'duration_hours', 'duration_mins',
        'price', 'currency', 'num_stops', 'travel_class',
        'days_until_departure', 'departure_delay_mins', 'arrival_delay_mins',
        'distance_miles', 'is_cancelled', 'is_diverted', 'flight_status',
        'month', 'day', 'year', 'data_source'
    ]

    # Only use columns that exist in both DataFrame and allowed list
    cols = [c for c in df.columns if c in allowed_cols]

    # Build insert query dynamically
    placeholders = ','.join(['%s'] * len(cols))
    col_names = ','.join(cols)
    insert_query = f"INSERT INTO raw_flights ({col_names}) VALUES ({placeholders})"

    # Insert rows in batches of 1000 for performance
    batch_size = 1000
    rows = [tuple(
        None if pd.isna(row[col]) else row[col]
        for col in cols
    ) for _, row in df.iterrows()]

    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        cursor.executemany(insert_query, batch)

    conn.commit()
    logger.info(f"Loaded {len(df)} rows into raw_flights")

    # Record lineage for every row
    logger.info(f"Recording lineage for {len(df)} rows...")

    lineage_rows = []
    for _, row in df.iterrows():
        row_hash = generate_row_hash(row)
        lineage_rows.append((source_name, 'raw_flights', row_hash, 'ingested'))

    # Insert lineage in batches
    for i in range(0, len(lineage_rows), batch_size):
        batch = lineage_rows[i:i + batch_size]
        cursor.executemany(
            "INSERT INTO lineage_log (source_name, raw_table, row_hash, status) VALUES (%s, %s, %s, %s)",
            batch
        )

    conn.commit()
    cursor.close()
    conn.close()

    logger.success(f"Lineage recorded for {len(df)} rows from {source_name}")

def log_conflict(field_name, source_1, value_1, source_2, value_2, resolution):
    """
    Records a conflict between two sources in the conflict_log table.
    A conflict is when two sources disagree on the same data point.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO conflict_log 
        (field_name, source_1, value_1, source_2, value_2, resolution) 
        VALUES (%s, %s, %s, %s, %s, %s)""",
        (field_name, source_1, str(value_1), source_2, str(value_2), resolution)
    )
    conn.commit()
    cursor.close()
    conn.close()
    logger.info(f"Conflict logged — field: {field_name}, {source_1}: {value_1} vs {source_2}: {value_2}")

def get_lineage_summary():
    """
    Returns a summary of all lineage records.
    Shows how many rows came from each source.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT source_name, status, COUNT(*) as row_count
        FROM lineage_log
        GROUP BY source_name, status
        ORDER BY source_name
    """)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    logger.info("Lineage summary:")
    for row in rows:
        logger.info(f"  {row[0]} — {row[1]}: {row[2]} rows")

    return rows

if __name__ == "__main__":
    logger.info("Testing lineage tracker...")

    test_df = pd.DataFrame([
        {
            'airline_name': 'Test Airline',
            'flight_number': 'TA001',
            'origin_city': 'Mumbai',
            'destination_city': 'Delhi',
            'duration_hours': 2.5,
            'price': 5000.0,
            'currency': 'INR',
            'data_source': 'test'
        }
    ])

    load_to_raw(test_df, 'test')
    get_lineage_summary()