import pandas as pd
import numpy as np
from loguru import logger
from dotenv import load_dotenv
from sqlalchemy import create_engine
import os
import sys
import joblib
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

# Database connection
DB_URL = f"postgresql+psycopg2://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"

# Model save path
MODEL_DIR = "ml/models"
MODEL_PATH = f"{MODEL_DIR}/flight_price_model.joblib"
ENCODER_PATH = f"{MODEL_DIR}/label_encoders.joblib"
METRICS_PATH = f"{MODEL_DIR}/model_metrics.joblib"

def get_engine():
    return create_engine(DB_URL)

def load_training_data():
    """
    Loads training data from mart_flights table.
    Only uses rows that have price data — Indian dataset.
    """
    logger.info("Loading training data from mart_flights...")

    import psycopg2
    conn = psycopg2.connect(
        host=os.getenv('POSTGRES_HOST'),
        port=os.getenv('POSTGRES_PORT'),
        user=os.getenv('POSTGRES_USER'),
        password=os.getenv('POSTGRES_PASSWORD'),
        dbname=os.getenv('POSTGRES_DB')
    )

    query = """
        SELECT
            airline_name,
            origin_city,
            destination_city,
            duration_hours,
            num_stops,
            travel_class,
            days_until_departure,
            price,
            price_category,
            duration_category,
            route_avg_price,
            route_min_price,
            route_max_price,
            route_avg_duration,
            airline_avg_price,
            airline_avg_delay
        FROM public.mart_flights
        WHERE price IS NOT NULL
        AND price > 0
        AND duration_hours IS NOT NULL
        AND airline_name IS NOT NULL
        AND origin_city IS NOT NULL
        AND destination_city IS NOT NULL
    """

    df = pd.read_sql(query, conn)
    conn.close()
    logger.info(f"Loaded {len(df)} rows for training")
    return df

def engineer_features(df):
    """
    converts raw columns into ML-friendly features.
    ML models need numbers — not text.
    This function converts text columns to numbers.
    """
    logger.info("Engineering features...")

    # Make a copy so we don't modify original
    df = df.copy()

    # Label encode categorical columns
    # Label encoding converts text to numbers
    # Example: 'SpiceJet' → 0, 'IndiGo' → 1, 'Vistara' → 2
    encoders = {}
    categorical_cols = [
        'airline_name',
        'origin_city',
        'destination_city',
        'num_stops',
        'travel_class',
        'price_category',
        'duration_category'
    ]

    for col in categorical_cols:
        if col in df.columns:
            le = LabelEncoder()
            # Fill nulls with 'unknown' before encoding
            df[col] = df[col].fillna('unknown')
            df[col] = le.fit_transform(df[col].astype(str))
            encoders[col] = le
            logger.info(f"Encoded {col} — {len(le.classes_)} unique values")

    # Fill numeric nulls with median
    numeric_cols = [
        'duration_hours', 'days_until_departure',
        'route_avg_price', 'route_min_price', 'route_max_price',
        'route_avg_duration', 'airline_avg_price', 'airline_avg_delay'
    ]

    for col in numeric_cols:
        if col in df.columns:
            df[col] = df[col].fillna(df[col].median())

    logger.info(f"Feature engineering complete — {len(df.columns)} features")
    return df, encoders

def train_model(df):
    """
    Trains a Random Forest Regressor to predict flight prices.

    What is Random Forest?
    - An ensemble of many decision trees
    - Each tree makes a prediction
    - Final prediction = average of all trees
    - More trees = more accurate but slower
    - Very robust — handles missing data and outliers well
    """
    logger.info("Training Random Forest model...")

    # Define features (X) and target (y)
    # Features = what we know about a flight
    # Target = what we want to predict (price)
    feature_cols = [
        'airline_name',
        'origin_city',
        'destination_city',
        'duration_hours',
        'num_stops',
        'travel_class',
        'days_until_departure',
        'price_category',
        'duration_category',
        'route_avg_price',
        'route_min_price',
        'route_max_price',
        'route_avg_duration',
        'airline_avg_price',
        'airline_avg_delay'
    ]

    # Only use columns that exist in our data
    available_features = [col for col in feature_cols if col in df.columns]
    logger.info(f"Using {len(available_features)} features: {available_features}")

    X = df[available_features]
    y = df['price']

    # Split into training and testing sets
    # 80% for training, 20% for testing
    # random_state=42 means results are reproducible
    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=0.2,
        random_state=42
    )

    logger.info(f"Training set: {len(X_train)} rows")
    logger.info(f"Testing set: {len(X_test)} rows")

    # Initialize Random Forest model
    # n_estimators=100 means 100 decision trees
    # max_depth=10 limits tree depth to prevent overfitting
    # n_jobs=-1 uses all CPU cores for faster training
    model = RandomForestRegressor(
        n_estimators=100,
        max_depth=10,
        min_samples_split=5,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=-1
    )

    # Train the model
    logger.info("Fitting model — this may take a minute...")
    model.fit(X_train, y_train)
    logger.info("Model training complete!")

    # Evaluate model on test set
    y_pred = model.predict(X_test)

    # Calculate metrics
    mae = mean_absolute_error(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    r2 = r2_score(y_test, y_pred)

    metrics = {
        'mae': round(mae, 2),
        'rmse': round(rmse, 2),
        'r2': round(r2, 4),
        'training_rows': len(X_train),
        'testing_rows': len(X_test),
        'features': available_features
    }

    logger.info("Model performance:")
    logger.info(f"  MAE  (Mean Absolute Error): {mae:.2f} INR")
    logger.info(f"  RMSE (Root Mean Sq Error):  {rmse:.2f} INR")
    logger.info(f"  R2   (Accuracy score):      {r2:.4f}")

    return model, metrics, available_features

def save_model(model, encoders, metrics):
    """
    Saves the trained model, encoders and metrics to disk.
    joblib is used because it handles large numpy arrays efficiently.
    """
    # Create models directory if it doesn't exist
    os.makedirs(MODEL_DIR, exist_ok=True)

    # Save model
    joblib.dump(model, MODEL_PATH)
    logger.info(f"Model saved to {MODEL_PATH}")

    # Save encoders — needed for making predictions later
    joblib.dump(encoders, ENCODER_PATH)
    logger.info(f"Encoders saved to {ENCODER_PATH}")

    # Save metrics — needed for model monitoring
    joblib.dump(metrics, METRICS_PATH)
    logger.info(f"Metrics saved to {METRICS_PATH}")

def load_model():
    """
    Loads a previously trained model from disk.
    Used by FastAPI and Streamlit for making predictions.
    """
    if not os.path.exists(MODEL_PATH):
        logger.error(f"No model found at {MODEL_PATH}")
        return None, None, None

    model = joblib.load(MODEL_PATH)
    encoders = joblib.load(ENCODER_PATH)
    metrics = joblib.load(METRICS_PATH)
    logger.info("Model loaded successfully")
    return model, encoders, metrics

if __name__ == "__main__":
    logger.info("Starting ML training pipeline...")

    # Step 1 — Load data
    df = load_training_data()

    if len(df) == 0:
        logger.error("No training data found!")
        exit(1)

    # Step 2 — Engineer features
    df_engineered, encoders = engineer_features(df)

    # Step 3 — Train model
    model, metrics, features = train_model(df_engineered)

    # Step 4 — Save model
    save_model(model, encoders, metrics)

    logger.success("ML training pipeline complete!")
    logger.success(f"Model accuracy (R2): {metrics['r2']}")
    logger.success(f"Average prediction error (MAE): {metrics['mae']} INR")