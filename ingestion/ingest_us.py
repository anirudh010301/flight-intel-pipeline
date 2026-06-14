import pandas as pd
import os
from loguru import logger
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Define paths to our CSV files
US_FLIGHTS_PATH = "data/raw/kaggle_us/flights.csv"
US_AIRLINES_PATH = "data/raw/kaggle_us/airlines.csv"
US_AIRPORTS_PATH = "data/raw/kaggle_us/airports.csv"

def load_us_flights():
    """
    Loads the US flights dataset.
    Joins with airlines and airports lookup tables.
    Returns a cleaned pandas DataFrame.
    """
    logger.info("Starting US flights ingestion...")

    # Check all files exist before reading
    for path in [US_FLIGHTS_PATH, US_AIRLINES_PATH, US_AIRPORTS_PATH]:
        if not os.path.exists(path):
            logger.error(f"File not found: {path}")
            return None

    # Load lookup tables first — these are small so fast to load
    logger.info("Loading airlines lookup table...")
    airlines_df = pd.read_csv(US_AIRLINES_PATH)

    logger.info("Loading airports lookup table...")
    airports_df = pd.read_csv(US_AIRPORTS_PATH)

    # Load only first 100,000 rows of flights
    # Full dataset is 5 million rows — too large for development
    # In production we would process in batches
    logger.info("Loading US flights (first 100,000 rows)...")
    df = pd.read_csv(US_FLIGHTS_PATH, nrows=100000)
    logger.info(f"Loaded {len(df)} rows from US flights dataset")

    # Join with airlines lookup to get full airline names
    # This converts codes like 'UA' to 'United Air Lines Inc.'
    df = df.merge(
        airlines_df,
        left_on='AIRLINE',
        right_on='IATA_CODE',
        how='left'
    )
    # Rename the full airline name column
    df = df.rename(columns={'AIRLINE_y': 'airline_full_name'})
    logger.info("Joined with airlines lookup table")

    # Join with airports lookup to get origin city names
    # This converts codes like 'ANC' to 'Anchorage'
    df = df.merge(
        airports_df[['IATA_CODE', 'CITY', 'STATE']],
        left_on='ORIGIN_AIRPORT',
        right_on='IATA_CODE',
        how='left'
    )
    df = df.rename(columns={
        'CITY': 'origin_city',
        'STATE': 'origin_state'
    })
    logger.info("Joined with origin airports lookup table")

    # Join with airports lookup again for destination city names
    df = df.merge(
        airports_df[['IATA_CODE', 'CITY', 'STATE']],
        left_on='DESTINATION_AIRPORT',
        right_on='IATA_CODE',
        how='left',
        suffixes=('', '_dest')
    )
    df = df.rename(columns={
        'CITY': 'destination_city',
        'STATE': 'destination_state'
    })
    logger.info("Joined with destination airports lookup table")

    # Select only the columns we need
    df = df[[
        'airline_full_name',
        'FLIGHT_NUMBER',
        'origin_city',
        'origin_state',
        'destination_city',
        'destination_state',
        'ORIGIN_AIRPORT',
        'DESTINATION_AIRPORT',
        'MONTH',
        'DAY',
        'YEAR',
        'DEPARTURE_DELAY',
        'ARRIVAL_DELAY',
        'AIR_TIME',
        'DISTANCE',
        'CANCELLED',
        'DIVERTED'
    ]]

    # Rename columns to standard format — same pattern as Indian dataset
    df = df.rename(columns={
        'airline_full_name': 'airline_name',
        'FLIGHT_NUMBER': 'flight_number',
        'ORIGIN_AIRPORT': 'origin_airport_code',
        'DESTINATION_AIRPORT': 'destination_airport_code',
        'MONTH': 'month',
        'DAY': 'day',
        'YEAR': 'year',
        'DEPARTURE_DELAY': 'departure_delay_mins',
        'ARRIVAL_DELAY': 'arrival_delay_mins',
        'AIR_TIME': 'duration_mins',
        'DISTANCE': 'distance_miles',
        'CANCELLED': 'is_cancelled',
        'DIVERTED': 'is_diverted'
    })

    # Convert duration from minutes to hours to match Indian dataset
    # Indian dataset has duration in hours, US has it in minutes
    df['duration_hours'] = df['duration_mins'] / 60
    logger.info("Converted duration from minutes to hours")

    # Add source column for lineage tracking
    df['data_source'] = 'kaggle_us'

    # US dataset has no price column — we add it as null
    # We'll handle this in conflict resolution phase
    df['price'] = None
    df['currency'] = 'USD'

    # Log what we have
    logger.info(f"Columns after processing: {list(df.columns)}")
    logger.info(f"Shape: {df.shape}")
    logger.info(f"Sample data:\n{df.head(2)}")

    return df

if __name__ == "__main__":
    df = load_us_flights()
    if df is not None:
        logger.success(f"US flights loaded successfully — {len(df)} rows")
        print(df.head())
        print(f"\nColumn names: {list(df.columns)}")
        print(f"\nData types:\n{df.dtypes}")