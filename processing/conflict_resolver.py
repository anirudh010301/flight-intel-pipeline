import pandas as pd
from loguru import logger
from dotenv import load_dotenv
import sys
import os

# Add project root to path so we can import our own modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lineage.lineage_tracker import load_to_raw, log_conflict, get_lineage_summary
from ingestion.ingest_indian import load_indian_flights
from ingestion.ingest_us import load_us_flights
from ingestion.ingest_api import fetch_live_flights

load_dotenv()

def standardize_airline_name(name):
    """
    Standardizes airline names across sources.
    Different sources use different formats for the same airline.
    Example: 'IndiGo' vs 'Indigo Airlines' vs 'INDIGO'
    """
    if pd.isna(name) or name is None:
        return None

    # Convert to string and strip whitespace
    name = str(name).strip()

    # Remove common suffixes that differ across sources
    suffixes = [' Inc.', ' Inc', ' LLC', ' Ltd', ' Limited', ' Airlines', ' Air Lines']
    for suffix in suffixes:
        if name.endswith(suffix):
            name = name[:-len(suffix)].strip()

    # Title case for consistency
    name = name.title()

    return name

def standardize_city_name(city):
    """
    Standardizes city names across sources.
    Example: 'New Delhi' vs 'Delhi' vs 'DELHI'
    """
    if pd.isna(city) or city is None:
        return None

    city = str(city).strip().title()

    # Common city name mappings
    # These are cases where sources use different names for the same city
    city_mappings = {
        'New Delhi': 'Delhi',
        'Bengaluru': 'Bangalore',
        'Bombay': 'Mumbai',
        'Calcutta': 'Kolkata',
        'Madras': 'Chennai',
        'Los Angeles': 'Los Angeles',
        'Nyc': 'New York',
        'Jfk': 'New York',
        'Lax': 'Los Angeles',
    }

    return city_mappings.get(city, city)

def resolve_duration_conflict(duration_indian, duration_us):
    """
    Resolves conflicts between duration values from different sources.
    Trust hierarchy: Indian dataset > US dataset
    Because Indian dataset has cleaner duration data.
    """
    if duration_indian is not None and not pd.isna(duration_indian):
        return duration_indian, 'kaggle_indian'
    elif duration_us is not None and not pd.isna(duration_us):
        return duration_us, 'kaggle_us'
    else:
        return None, None

def merge_and_resolve(indian_df, us_df, api_df):
    """
    Main conflict resolution function.
    Merges all 3 sources into one unified DataFrame.
    Detects and resolves conflicts.
    Records all conflicts in conflict_log.
    """
    logger.info("Starting conflict resolution...")

    # Step 1 — Standardize airline names across all sources
    logger.info("Standardizing airline names...")
    indian_df['airline_name'] = indian_df['airline_name'].apply(standardize_airline_name)
    us_df['airline_name'] = us_df['airline_name'].apply(standardize_airline_name)
    api_df['airline_name'] = api_df['airline_name'].apply(standardize_airline_name)

    # Step 2 — Standardize city names across all sources
    logger.info("Standardizing city names...")
    indian_df['origin_city'] = indian_df['origin_city'].apply(standardize_city_name)
    indian_df['destination_city'] = indian_df['destination_city'].apply(standardize_city_name)
    us_df['origin_city'] = us_df['origin_city'].apply(standardize_city_name)
    us_df['destination_city'] = us_df['destination_city'].apply(standardize_city_name)
    api_df['origin_city'] = api_df['origin_city'].apply(standardize_city_name)
    api_df['destination_city'] = api_df['destination_city'].apply(standardize_city_name)

    # Step 3 — Select common columns from each source
    # We pick the columns that exist in all sources or are important
    logger.info("Selecting common columns...")

    indian_common = indian_df[[
        'airline_name', 'flight_number', 'origin_city',
        'destination_city', 'duration_hours', 'price',
        'currency', 'num_stops', 'travel_class',
        'days_until_departure', 'data_source'
    ]].copy()

    us_common = us_df[[
        'airline_name', 'flight_number', 'origin_city',
        'destination_city', 'duration_hours', 'price',
        'currency', 'departure_delay_mins', 'arrival_delay_mins',
        'distance_miles', 'is_cancelled', 'data_source'
    ]].copy()

    api_common = api_df[[
        'airline_name', 'flight_number', 'origin_city',
        'destination_city', 'price', 'currency',
        'departure_delay_mins', 'arrival_delay_mins',
        'flight_status', 'data_source'
    ]].copy()

    # Step 4 — Detect duration conflict between Indian and US datasets
    # Both have duration but in different quality
    logger.info("Detecting conflicts...")

    # Sample conflict check — compare duration for similar routes
    # In a real pipeline we would match on flight_number
    indian_avg_duration = indian_df['duration_hours'].mean()
    us_avg_duration = us_df['duration_hours'].mean()

    if abs(indian_avg_duration - us_avg_duration) > 1:
        log_conflict(
            field_name='duration_hours',
            source_1='kaggle_indian',
            value_1=round(indian_avg_duration, 2),
            source_2='kaggle_us',
            value_2=round(us_avg_duration, 2),
            resolution='Trust hierarchy applied — kaggle_indian preferred for duration'
        )
        logger.warning(f"Duration conflict detected — Indian avg: {indian_avg_duration:.2f}h, US avg: {us_avg_duration:.2f}h")

    # Step 5 — Currency conflict
    # Indian dataset uses INR, US uses USD — both are correct but different
    log_conflict(
        field_name='currency',
        source_1='kaggle_indian',
        value_1='INR',
        source_2='kaggle_us',
        value_2='USD',
        resolution='Both kept — currency column preserved per source'
    )
    logger.info("Currency conflict logged — INR vs USD — both preserved")

    # Step 6 — Combine all sources into unified DataFrame
    logger.info("Combining all sources...")
    unified_df = pd.concat([indian_common, us_common, api_common], ignore_index=True)

    # Step 7 — Add conflict flag
    # Rows from sources with known conflicts get flagged
    unified_df['conflict_flag'] = False
    unified_df.loc[unified_df['data_source'] == 'kaggle_us', 'conflict_flag'] = True

    logger.info(f"Unified DataFrame shape: {unified_df.shape}")
    logger.info(f"Sources in unified data: {unified_df['data_source'].value_counts().to_dict()}")

    return unified_df

if __name__ == "__main__":
    logger.info("Starting full ingestion and conflict resolution pipeline...")

    # Step 1 — Load all 3 sources
    logger.info("Loading Indian flights...")
    indian_df = load_indian_flights()

    logger.info("Loading US flights...")
    us_df = load_us_flights()

    logger.info("Loading API flights...")
    api_df = fetch_live_flights(limit=100)

    if indian_df is None or us_df is None or api_df is None:
        logger.error("One or more sources failed to load")
        exit(1)

    # Step 2 — Load raw data into PostgreSQL with lineage tracking
    logger.info("Loading raw data into PostgreSQL...")
    load_to_raw(indian_df, 'kaggle_indian')
    load_to_raw(us_df, 'kaggle_us')
    load_to_raw(api_df, 'aviationstack_api')

    # Step 3 — Run conflict resolution
    unified_df = merge_and_resolve(indian_df, us_df, api_df)

    # Step 4 — Show lineage summary
    logger.info("Final lineage summary:")
    get_lineage_summary()

    logger.success(f"Conflict resolution complete — {len(unified_df)} unified rows")
    print(unified_df.head())
    print(f"\nSources: {unified_df['data_source'].value_counts().to_dict()}")
    print(f"\nConflict flagged rows: {unified_df['conflict_flag'].sum()}")