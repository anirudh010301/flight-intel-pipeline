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

with DAG(
    dag_id='dag_ml',
    default_args=default_args,
    description='Retrains ML model daily on fresh data',
    schedule_interval='0 2 * * *',  # Every day at 2am — after transformations
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['flight_intel', 'ml']
) as dag:

    # Task 1 — Retrain ML model
    train_model = BashOperator(
        task_id='train_model',
        bash_command=f'cd {PROJECT_PATH} && {PYTHON_PATH} ml/train_model.py',
    )

    # Task 2 — Generate visualizations
    visualize_model = BashOperator(
        task_id='visualize_model',
        bash_command=f'cd {PROJECT_PATH} && {PYTHON_PATH} ml/visualize_model.py',
    )

    # Define task order
    train_model >> visualize_model