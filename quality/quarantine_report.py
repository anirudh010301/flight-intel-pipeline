import psycopg2
from loguru import logger
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

def get_quarantine_summary():
    """
    Prints a summary of all quarantined rows.
    Called by Airflow dag_quality DAG as the final task.
    
    This report answers 3 questions:
    1. How many rows were quarantined in total?
    2. Which source has the most dirty data?
    3. What are the most common failure reasons?
    
    This is how data engineers monitor pipeline health in production.
    """

    # Connect directly using psycopg2
    # We avoid SQLAlchemy here to prevent version conflicts with Airflow
    conn = psycopg2.connect(
        host=os.getenv('POSTGRES_HOST'),
        port=os.getenv('POSTGRES_PORT'),
        user=os.getenv('POSTGRES_USER'),
        password=os.getenv('POSTGRES_PASSWORD'),
        dbname=os.getenv('POSTGRES_DB')
    )
    cursor = conn.cursor()

    # Query 1 — Total quarantined rows
    # If this number grows every day — our data sources are getting dirtier
    cursor.execute("SELECT COUNT(*) FROM quarantine")
    total = cursor.fetchone()[0]
    logger.info(f"Total quarantined rows: {total}")

    # Query 2 — Breakdown by source
    # Tells us which source has the most quality issues
    # Expected: aviationstack_api will have most issues — live APIs are messy
    cursor.execute("""
        SELECT data_source, COUNT(*) as count
        FROM quarantine
        GROUP BY data_source
        ORDER BY count DESC
    """)
    rows = cursor.fetchall()
    logger.info("Quarantine breakdown by source:")
    for row in rows:
        logger.info(f"  {row[0]}: {row[1]} rows")

    # Query 3 — Top failure reasons
    # Tells us which quality rules are catching the most issues
    # Useful for improving data quality at the source
    cursor.execute("""
        SELECT failure_reason, COUNT(*) as count
        FROM quarantine
        GROUP BY failure_reason
        ORDER BY count DESC
        LIMIT 10
    """)
    rows = cursor.fetchall()
    logger.info("Top failure reasons:")
    for row in rows:
        logger.info(f"  {row[1]} rows — {row[0][:100]}")

    cursor.close()
    conn.close()

if __name__ == "__main__":
    logger.info("Running quarantine report...")
    get_quarantine_summary()
    logger.success("Quarantine report complete!")