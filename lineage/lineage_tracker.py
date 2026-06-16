import hashlib
import json
import pandas as pd
from loguru import logger
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Database connection string
DB_URL = f"postgresql+psycopg2://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"

def get_engine():
    """
    Creates and returns a SQLAlchemy database engine.
    Think of the engine as a connection pool to PostgreSQL.
    """
    return create_engine(DB_URL)

def generate_row_hash(row):
    """
    Generates a unique hash for each row.
    A hash is a fixed-length fingerprint of the data.
    If two rows have the same hash — they are identical.
    This helps us detect duplicates across sources.
    """
    # Convert row to a sorted string so order doesn't matter
    row_str = json.dumps(dict(row), sort_keys=True, default=str)
    # Generate MD5 hash — produces a 32 character string
    return hashlib.md5(row_str.encode()).hexdigest()

def load_to_raw(df, source_name):
    """
    Loads a DataFrame into the raw_flights table.
    Records every row in the lineage_log.
    This is the entry point for all data into our pipeline.
    """
    logger.info(f"Loading {len(df)} rows from {source_name} into raw_flights...")

    engine = get_engine()

    # Load data into raw_flights table
    with engine.begin() as conn:
        df.to_sql(
            'raw_flights',
            conn,
            if_exists='append',
            index=False,
            method='multi'
        )
    logger.info(f"Loaded {len(df)} rows into raw_flights")

    # Now record every row in lineage_log
    # This is how we track where every row came from
    logger.info(f"Recording lineage for {len(df)} rows...")

    with engine.connect() as conn:
        # Get the IDs of the rows we just inserted
        result = conn.execute(
            text(f"SELECT id FROM raw_flights WHERE data_source = '{source_name}' ORDER BY id DESC LIMIT {len(df)}")
        )
        row_ids = [row[0] for row in result]

        # Insert lineage record for each row
        for i, row in df.iterrows():
            row_hash = generate_row_hash(row)
            conn.execute(
                text("""
                    INSERT INTO lineage_log (source_name, record_id, raw_table, row_hash, status)
                    VALUES (:source, :record_id, :table, :hash, :status)
                """),
                {
                    'source': source_name,
                    'record_id': row_ids[i % len(row_ids)] if row_ids else None,
                    'table': 'raw_flights',
                    'hash': row_hash,
                    'status': 'ingested'
                }
            )
        conn.commit()

    logger.success(f"Lineage recorded for {len(df)} rows from {source_name}")

def log_conflict(field_name, source_1, value_1, source_2, value_2, resolution):
    """
    Records a conflict between two sources in the conflict_log table.
    A conflict is when two sources disagree on the same data point.
    """
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(
            text("""
                INSERT INTO conflict_log (field_name, source_1, value_1, source_2, value_2, resolution)
                VALUES (:field, :s1, :v1, :s2, :v2, :resolution)
            """),
            {
                'field': field_name,
                's1': source_1,
                'v1': str(value_1),
                's2': source_2,
                'v2': str(value_2),
                'resolution': resolution
            }
        )
        conn.commit()
    logger.info(f"Conflict logged — field: {field_name}, {source_1}: {value_1} vs {source_2}: {value_2}")

def get_lineage_summary():
    """
    Returns a summary of all lineage records.
    Shows how many rows came from each source.
    """
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(
            text("""
                SELECT source_name, status, COUNT(*) as row_count
                FROM lineage_log
                GROUP BY source_name, status
                ORDER BY source_name
            """)
        )
        rows = result.fetchall()

    logger.info("Lineage summary:")
    for row in rows:
        logger.info(f"  {row[0]} — {row[1]}: {row[2]} rows")

    return rows

if __name__ == "__main__":
    # Test lineage tracker with a small sample
    logger.info("Testing lineage tracker...")

    # Create a small test DataFrame
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