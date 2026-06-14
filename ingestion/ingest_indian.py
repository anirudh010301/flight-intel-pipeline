import pandas as pd
import os
from loguru import logger
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Define the path to our CSV file
INDIAN_DATA_PATH = "data/raw/kaggle_indian/Clean_Dataset.csv"

def load_indian_flights():
    """
    Loads the Indian domestic flights dataset.
    Returns a cleaned pandas DataFrame.
    """
    logger.info("Starting Indian flights ingestion...")

    # Check if file exists before trying to read it
    if not os.path.exists(INDIAN_DATA_PATH):
        logger.error(f"File not found: {INDIAN_DATA_PATH}")
        return None

    # Read the CSV file into a pandas DataFrame
    # A DataFrame is like an Excel table in Python
    df = pd.read_csv(INDIAN_DATA_PATH)
    logger.info(f"Loaded {len(df)} rows from Indian dataset")

    # Drop the unnamed first column
    # This column is just row numbers from the original CSV — we don't need it
    if 'Unnamed: 0' in df.columns:
        df = df.drop(columns=['Unnamed: 0'])
        logger.info("Dropped unnamed index column")

    # Rename columns to a standard format
    # We use snake_case and clear names so all 3 sources speak the same language
    df = df.rename(columns={
        'airline': 'airline_name',
        'flight': 'flight_number',
        'source_city': 'origin_city',
        'departure_time': 'departure_time',
        'stops': 'num_stops',
        'arrival_time': 'arrival_time',
        'destination_city': 'destination_city',
        'class': 'travel_class',
        'duration': 'duration_hours',
        'days_left': 'days_until_departure',
        'price': 'price'
    })

    # Add a source column so we always know where this data came from
    # This is the foundation of our lineage tracking
    df['data_source'] = 'kaggle_indian'

    # Add a currency column since Indian prices are in INR
    df['currency'] = 'INR'

    # Log what we have
    logger.info(f"Columns after renaming: {list(df.columns)}")
    logger.info(f"Shape: {df.shape}")
    logger.info(f"Sample data:\n{df.head(2)}")

    return df

if __name__ == "__main__":
    df = load_indian_flights()
    if df is not None:
        logger.success(f"Indian flights loaded successfully — {len(df)} rows")
        print(df.head())
        print(f"\nColumn names: {list(df.columns)}")
        print(f"\nData types:\n{df.dtypes}")