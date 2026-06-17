from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta

# Default arguments applied to all tasks in this DAG
default_args = {
    'owner': 'flight_intel',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5)
}

# Project path — all scripts run from here
PROJECT_PATH = "/Users/addaanirudh/Documents/flight-intel-pipeline"
PYTHON_PATH = f"{PROJECT_PATH}/venv/bin/python"

with DAG(
    dag_id='dag_ingest',
    default_args=default_args,
    description='Ingests flight data from all 3 sources daily',
    schedule_interval='0 0 * * *',  # Every day at midnight
    start_date=datetime(2024, 1, 1),
    catchup=False,  # Don't run missed runs — very important!
    tags=['flight_intel', 'ingestion']
) as dag:

    # Task 1 — Ingest Indian flights
    ingest_indian = BashOperator(
        task_id='ingest_indian_flights',
        bash_command=f'cd {PROJECT_PATH} && {PYTHON_PATH} ingestion/ingest_indian.py',
    )

    # Task 2 — Ingest US flights
    ingest_us = BashOperator(
        task_id='ingest_us_flights',
        bash_command=f'cd {PROJECT_PATH} && {PYTHON_PATH} ingestion/ingest_us.py',
    )

    # Task 3 — Ingest API flights
    ingest_api = BashOperator(
        task_id='ingest_api_flights',
        bash_command=f'cd {PROJECT_PATH} && {PYTHON_PATH} ingestion/ingest_api.py',
    )

    # Task 4 — Run conflict resolution
    conflict_resolution = BashOperator(
        task_id='conflict_resolution',
        bash_command=f'cd {PROJECT_PATH} && {PYTHON_PATH} processing/conflict_resolver.py',
    )

    # Task 5 — Run quality checks
    quality_checks = BashOperator(
        task_id='quality_checks',
        bash_command=f'cd {PROJECT_PATH} && {PYTHON_PATH} quality/quality_checks.py',
    )

    # Define task order
    # Ingest all 3 sources in parallel first
    # Then run conflict resolution
    # Then run quality checks
    [ingest_indian, ingest_us, ingest_api] >> conflict_resolution >> quality_checks