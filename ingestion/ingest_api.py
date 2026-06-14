import requests
import pandas as pd
import os
from loguru import logger
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get API key from .env file
API_KEY = os.getenv("AVIATIONSTACK_API_KEY")

# AviationStack base URL
BASE_URL = "http://api.aviationstack.com/v1"

def fetch_live_flights(limit=100):
    """
    Fetches live flight data from AviationStack API.
    Free tier allows 500 calls/month and 100 results per call.
    Returns a cleaned pandas DataFrame.
    """
    logger.info("Starting AviationStack API ingestion...")

    # Check API key exists
    if not API_KEY:
        logger.error("AVIATIONSTACK_API_KEY not found in .env file")
        return None

    # Build the API request parameters
    # These are the filters we send to the API
    params = {
        'access_key': API_KEY,
        'limit': limit,
        'flight_status': 'active'  # Only get currently active flights
    }

    logger.info(f"Calling AviationStack API — limit: {limit} flights")

    # Make the API call
    # This is an HTTP GET request — same as typing a URL in your browser
    try:
        response = requests.get(
            f"{BASE_URL}/flights",
            params=params,
            timeout=30  # Wait max 30 seconds for response
        )

        # Check if request was successful
        # Status code 200 means success
        if response.status_code != 200:
            logger.error(f"API call failed — status code: {response.status_code}")
            return None

        # Parse JSON response into Python dictionary
        data = response.json()

        # Check for API errors in response body
        if 'error' in data:
            logger.error(f"API error: {data['error']}")
            return None

        # Extract the list of flights from response
        flights = data.get('data', [])
        logger.info(f"Received {len(flights)} flights from API")

        if len(flights) == 0:
            logger.warning("No flights returned from API")
            return None

        # Parse each flight into a flat dictionary
        # API returns nested JSON — we flatten it into simple columns
        parsed_flights = []
        for flight in flights:
            parsed_flight = {
                # Airline information
                'airline_name': flight.get('airline', {}).get('name', None),
                'airline_iata': flight.get('airline', {}).get('iata', None),

                # Flight information
                'flight_number': flight.get('flight', {}).get('iata', None),

                # Origin airport information
                'origin_city': flight.get('departure', {}).get('airport', None),
                'origin_airport_code': flight.get('departure', {}).get('iata', None),

                # Destination airport information
                'destination_city': flight.get('arrival', {}).get('airport', None),
                'destination_airport_code': flight.get('arrival', {}).get('iata', None),

                # Timing information
                'departure_time': flight.get('departure', {}).get('scheduled', None),
                'arrival_time': flight.get('arrival', {}).get('scheduled', None),
                'departure_delay_mins': flight.get('departure', {}).get('delay', None),
                'arrival_delay_mins': flight.get('arrival', {}).get('delay', None),

                # Flight status
                'flight_status': flight.get('flight_status', None),
            }
            parsed_flights.append(parsed_flight)

        # Convert list of dictionaries to DataFrame
        df = pd.DataFrame(parsed_flights)
        logger.info(f"Parsed {len(df)} flights into DataFrame")

        # Add source column for lineage tracking
        df['data_source'] = 'aviationstack_api'

        # API doesn't provide price data
        df['price'] = None
        df['currency'] = None

        # Log what we have
        logger.info(f"Columns: {list(df.columns)}")
        logger.info(f"Shape: {df.shape}")
        logger.info(f"Sample data:\n{df.head(2)}")

        return df

    except requests.exceptions.Timeout:
        logger.error("API call timed out after 30 seconds")
        return None
    except requests.exceptions.ConnectionError:
        logger.error("Could not connect to AviationStack API")
        return None
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return None

if __name__ == "__main__":
    df = fetch_live_flights(limit=100)
    if df is not None:
        logger.success(f"API ingestion successful — {len(df)} flights")
        print(df.head())
        print(f"\nColumn names: {list(df.columns)}")
        print(f"\nFlight statuses: {df['flight_status'].value_counts()}")