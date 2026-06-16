import pandas as pd
import numpy as np
from loguru import logger
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

# Database connection
DB_URL = f"postgresql+psycopg2://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"

def get_engine():
    return create_engine(DB_URL)

# ── Quality Rules ──────────────────────────────────────────────
# Each rule is a function that takes a row and returns True (pass) or False (fail)
# This is our custom lightweight quality gate system

QUALITY_RULES = {

    'airline_name_not_null': {
        'description': 'Airline name must not be null or empty',
        'check': lambda row: (
            pd.notna(row.get('airline_name')) and
            str(row.get('airline_name')).strip() not in ['', 'None', 'empty', 'nan']
        )
    },

    'origin_city_not_null': {
        'description': 'Origin city must not be null or empty',
        'check': lambda row: (
            pd.notna(row.get('origin_city')) and
            str(row.get('origin_city')).strip() not in ['', 'None', 'nan']
        )
    },

    'destination_city_not_null': {
        'description': 'Destination city must not be null or empty',
        'check': lambda row: (
            pd.notna(row.get('destination_city')) and
            str(row.get('destination_city')).strip() not in ['', 'None', 'nan']
        )
    },

    'duration_positive': {
        'description': 'Flight duration must be positive and less than 50 hours',
        'check': lambda row: (
            pd.isna(row.get('duration_hours')) or
            (float(row.get('duration_hours', 0)) > 0 and
             float(row.get('duration_hours', 0)) < 50)
        )
    },

    'price_positive': {
        'description': 'Price must be positive if present',
        'check': lambda row: (
            pd.isna(row.get('price')) or
            row.get('price') is None or
            float(row.get('price', 0)) > 0
        )
    },

    'origin_destination_different': {
        'description': 'Origin and destination cities must be different',
        'check': lambda row: (
            pd.isna(row.get('origin_city')) or
            pd.isna(row.get('destination_city')) or
            str(row.get('origin_city')).strip().lower() !=
            str(row.get('destination_city')).strip().lower()
        )
    },

    'valid_data_source': {
        'description': 'Data source must be one of our known sources',
        'check': lambda row: row.get('data_source') in [
            'kaggle_indian', 'kaggle_us', 'aviationstack_api', 'test'
        ]
    },

}

def run_quality_checks(df, source_name):
    """
    Runs all quality rules against a DataFrame.
    Splits rows into passed and failed.
    Sends failed rows to quarantine table.
    Returns cleaned DataFrame with only passing rows.
    """
    logger.info(f"Running quality checks on {len(df)} rows from {source_name}...")

    passed_rows = []
    failed_rows = []
    failure_reasons = []

    # Check each row against all rules
    for idx, row in df.iterrows():
        row_failures = []

        # Run every quality rule
        for rule_name, rule in QUALITY_RULES.items():
            try:
                passed = rule['check'](row)
                if not passed:
                    row_failures.append(f"{rule_name}: {rule['description']}")
            except Exception as e:
                row_failures.append(f"{rule_name}: ERROR — {str(e)}")

        if len(row_failures) == 0:
            # Row passed all checks
            passed_rows.append(row)
        else:
            # Row failed one or more checks
            failed_rows.append(row)
            failure_reasons.append(' | '.join(row_failures))

    logger.info(f"Quality check results for {source_name}:")
    logger.info(f"  ✅ Passed: {len(passed_rows)} rows")
    logger.info(f"  ❌ Failed: {len(failed_rows)} rows")

    # Send failed rows to quarantine
    if len(failed_rows) > 0:
        quarantine_failed_rows(failed_rows, failure_reasons, source_name)

    # Return only passing rows
    if len(passed_rows) > 0:
        return pd.DataFrame(passed_rows).reset_index(drop=True)
    else:
        logger.warning(f"No rows passed quality checks for {source_name}")
        return pd.DataFrame()

def quarantine_failed_rows(failed_rows, failure_reasons, source_name):
    """
    Sends failed rows to the quarantine table.
    These rows will never reach the ML model.
    """
    logger.info(f"Sending {len(failed_rows)} rows to quarantine...")

    engine = get_engine()

    quarantine_records = []
    for row, reason in zip(failed_rows, failure_reasons):
        quarantine_records.append({
            'original_table': 'raw_flights',
            'data_source': source_name,
            'raw_data': str(dict(row)),
            'failure_reason': reason
        })

    quarantine_df = pd.DataFrame(quarantine_records)

    with engine.begin() as conn:
        quarantine_df.to_sql(
            'quarantine',
            conn,
            if_exists='append',
            index=False
        )

    logger.warning(f"Quarantined {len(failed_rows)} rows from {source_name}")

def get_quality_summary():
    """
    Returns a summary of quarantined rows by source and reason.
    """
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(
            text("""
                SELECT data_source, failure_reason, COUNT(*) as count
                FROM quarantine
                GROUP BY data_source, failure_reason
                ORDER BY count DESC
                LIMIT 20
            """)
        )
        rows = result.fetchall()

    logger.info("Quality summary — top failure reasons:")
    for row in rows:
        logger.info(f"  {row[0]} — {row[2]} rows — {row[1][:80]}")

    return rows

if __name__ == "__main__":
    from ingestion.ingest_indian import load_indian_flights
    from ingestion.ingest_us import load_us_flights
    from ingestion.ingest_api import fetch_live_flights

    logger.info("Running quality checks on all 3 sources...")

    # Load all 3 sources
    indian_df = load_indian_flights()
    us_df = load_us_flights()
    api_df = fetch_live_flights(limit=100)

    # Run quality checks on each source
    logger.info("Checking Indian flights...")
    indian_clean = run_quality_checks(indian_df, 'kaggle_indian')

    logger.info("Checking US flights...")
    us_clean = run_quality_checks(us_df, 'kaggle_us')

    logger.info("Checking API flights...")
    api_clean = run_quality_checks(api_df, 'aviationstack_api')

    # Show summary
    logger.success(f"Indian flights — {len(indian_clean)}/{len(indian_df)} rows passed")
    logger.success(f"US flights — {len(us_clean)}/{len(us_df)} rows passed")
    logger.success(f"API flights — {len(api_clean)}/{len(api_df)} rows passed")

    # Show quarantine summary
    get_quality_summary()