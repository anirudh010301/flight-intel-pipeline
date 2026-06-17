import psycopg2
from loguru import logger
from dotenv import load_dotenv
import os

load_dotenv()

def get_quarantine_summary():
    """
    Prints a summary of all quarantined rows.
    Called by Airflow dag_quality DAG.
    """
    conn = psycopg2.connect(
        host=os.getenv('POSTGRES_HOST'),
        port=os.getenv('POSTGRES_PORT'),
        user=os.getenv('POSTGRES_USER'),
        password=os.getenv('POSTGRES_PASSWORD'),
        dbname=os.getenv('POSTGRES_DB')
    )
    cursor = conn.cursor()

    # Total quarantined rows
    cursor.execute("SELECT COUNT(*) FROM quarantine")
    total = cursor.fetchone()[0]
    logger.info(f"Total quarantined rows: {total}")

    # Breakdown by source
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

    # Top failure reasons
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