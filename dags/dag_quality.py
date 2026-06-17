from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta

default_args = {
    'owner': 'flight_intel',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5)
}

PROJECT_PATH = "/Users/addaanirudh/Documents/flight-intel-pipeline"
PYTHON_PATH = f"{PROJECT_PATH}/venv/bin/python"
DBT_PATH = f"{PROJECT_PATH}/venv/bin/dbt"
DBT_PROJECT_PATH = f"{PROJECT_PATH}/dbt_project"

with DAG(
    dag_id='dag_quality',
    default_args=default_args,
    description='Runs quality checks and generates quarantine report daily',
    schedule_interval='0 3 * * *',  # Every day at 3am — after ML
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['flight_intel', 'quality']
) as dag:

    # Task 1 — Run quality checks on fresh data
    quality_checks = BashOperator(
        task_id='quality_checks',
        bash_command=f'cd {PROJECT_PATH} && {PYTHON_PATH} quality/quality_checks.py',
    )

    # Task 2 — Run all dbt tests
    dbt_tests = BashOperator(
        task_id='dbt_tests',
        bash_command=f'cd {DBT_PROJECT_PATH} && {DBT_PATH} test',
    )

    # Task 3 — Check quarantine table
    check_quarantine = BashOperator(
        task_id='check_quarantine',
        bash_command=f'cd {PROJECT_PATH} && {PYTHON_PATH} quality/quarantine_report.py',
    )

    # Define task order
    quality_checks >> dbt_tests >> check_quarantine