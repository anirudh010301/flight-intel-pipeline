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
DBT_PATH = f"{PROJECT_PATH}/venv/bin/dbt"
DBT_PROJECT_PATH = f"{PROJECT_PATH}/dbt_project"

with DAG(
    dag_id='dag_transform',
    default_args=default_args,
    description='Runs dbt transformations daily',
    schedule_interval='0 1 * * *',  # Every day at 1am — after ingestion
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['flight_intel', 'transformation']
) as dag:

    # Task 1 — Run staging model
    dbt_staging = BashOperator(
        task_id='dbt_staging',
        bash_command=f'cd {DBT_PROJECT_PATH} && {DBT_PATH} run --select stg_flights',
    )

    # Task 2 — Run ODS model
    dbt_ods = BashOperator(
        task_id='dbt_ods',
        bash_command=f'cd {DBT_PROJECT_PATH} && {DBT_PATH} run --select ods_flights',
    )

    # Task 3 — Run marts model
    dbt_marts = BashOperator(
        task_id='dbt_marts',
        bash_command=f'cd {DBT_PROJECT_PATH} && {DBT_PATH} run --select mart_flights',
    )

    # Task 4 — Run all dbt tests
    dbt_tests = BashOperator(
        task_id='dbt_tests',
        bash_command=f'cd {DBT_PROJECT_PATH} && {DBT_PATH} test',
    )

    # Define task order — run layer by layer
    dbt_staging >> dbt_ods >> dbt_marts >> dbt_tests