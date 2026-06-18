from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import psycopg2
import joblib
import pandas as pd
import numpy as np
from loguru import logger
from dotenv import load_dotenv
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="Flight Intel API",
    description="REST API for flight price prediction and intelligence",
    version="1.0.0"
)

# Model paths
MODEL_PATH = "ml/models/flight_price_model.joblib"
ENCODER_PATH = "ml/models/label_encoders.joblib"
METRICS_PATH = "ml/models/model_metrics.joblib"

# Load ML model on startup
# This means model is loaded once — not every request
model = None
encoders = None
metrics = None

def get_connection():
    """Creates psycopg2 database connection."""
    return psycopg2.connect(
        host=os.getenv('POSTGRES_HOST'),
        port=os.getenv('POSTGRES_PORT'),
        user=os.getenv('POSTGRES_USER'),
        password=os.getenv('POSTGRES_PASSWORD'),
        dbname=os.getenv('POSTGRES_DB')
    )

def load_ml_model():
    """Loads ML model from disk."""
    global model, encoders, metrics
    if os.path.exists(MODEL_PATH):
        model = joblib.load(MODEL_PATH)
        encoders = joblib.load(ENCODER_PATH)
        metrics = joblib.load(METRICS_PATH)
        logger.info("ML model loaded successfully")
    else:
        logger.warning("No ML model found — train model first")

# Load model when API starts
load_ml_model()

# ── Request/Response Models ────────────────────────────────────
# Pydantic models define what data each endpoint accepts and returns
# FastAPI uses these for automatic validation and documentation

class PredictionRequest(BaseModel):
    """What the user sends to get a price prediction."""
    airline_name: str
    origin_city: str
    destination_city: str
    duration_hours: float
    num_stops: str
    travel_class: str
    days_until_departure: int

class PredictionResponse(BaseModel):
    """What we send back after prediction."""
    predicted_price: float
    currency: str
    confidence: str
    model_r2: float

class FlightFilter(BaseModel):
    """Filters for querying flights."""
    origin_city: Optional[str] = None
    destination_city: Optional[str] = None
    airline_name: Optional[str] = None
    limit: Optional[int] = 100

# ── Endpoints ─────────────────────────────────────────────────

@app.get("/")
def health_check():
    """Health check endpoint — confirms API is running."""
    return {
        "status": "healthy",
        "api": "Flight Intel Pipeline",
        "version": "1.0.0",
        "model_loaded": model is not None
    }

@app.get("/airlines")
def get_airlines():
    """Returns list of all unique airlines in our database."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT airline_name, data_source
        FROM mart_flights
        WHERE airline_name IS NOT NULL
        ORDER BY airline_name
    """)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return {"airlines": [{"name": r[0], "source": r[1]} for r in rows]}

@app.get("/routes")
def get_routes():
    """Returns list of all unique routes with average prices."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            origin_city,
            destination_city,
            COUNT(*) as total_flights,
            ROUND(AVG(price)::numeric, 2) as avg_price,
            ROUND(MIN(price)::numeric, 2) as min_price,
            ROUND(MAX(price)::numeric, 2) as max_price
        FROM mart_flights
        WHERE price IS NOT NULL
        GROUP BY origin_city, destination_city
        ORDER BY total_flights DESC
        LIMIT 50
    """)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return {
        "routes": [
            {
                "origin": r[0],
                "destination": r[1],
                "total_flights": r[2],
                "avg_price": float(r[3]) if r[3] else None,
                "min_price": float(r[4]) if r[4] else None,
                "max_price": float(r[5]) if r[5] else None
            }
            for r in rows
        ]
    }

@app.post("/predict", response_model=PredictionResponse)
def predict_price(request: PredictionRequest):
    """
    Predicts flight price using our trained ML model.
    This is the core endpoint — takes flight details and returns predicted price.
    """
    if model is None:
        raise HTTPException(status_code=503, detail="ML model not loaded")

    try:
        # Build input DataFrame
        # Calculate duration category from duration_hours
        if request.duration_hours < 2:
            duration_cat = 'short'
        elif request.duration_hours <= 5:
            duration_cat = 'medium'
        else:
            duration_cat = 'long'

        input_data = {
            'airline_name': [request.airline_name],
            'origin_city': [request.origin_city],
            'destination_city': [request.destination_city],
            'duration_hours': [request.duration_hours],
            'num_stops': [request.num_stops],
            'travel_class': [request.travel_class],
            'days_until_departure': [request.days_until_departure],
            'price_category': ['mid'],
            'duration_category': [duration_cat],
            'route_avg_price': [None],
            'route_min_price': [None],
            'route_max_price': [None],
            'route_avg_duration': [None],
            'airline_avg_price': [None],
            'airline_avg_delay': [None]
        }

        # Enrich with route stats from database
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                ROUND(AVG(price)::numeric, 2),
                ROUND(MIN(price)::numeric, 2),
                ROUND(MAX(price)::numeric, 2),
                ROUND(AVG(duration_hours)::numeric, 2)
            FROM mart_flights
            WHERE origin_city = %s
            AND destination_city = %s
            AND price IS NOT NULL
        """, (request.origin_city, request.destination_city))
        route_stats = cursor.fetchone()

        if route_stats and route_stats[0]:
            input_data['route_avg_price'] = [float(route_stats[0])]
            input_data['route_min_price'] = [float(route_stats[1])]
            input_data['route_max_price'] = [float(route_stats[2])]
            input_data['route_avg_duration'] = [float(route_stats[3])]

        # Get airline stats
        cursor.execute("""
            SELECT ROUND(AVG(price)::numeric, 2)
            FROM mart_flights
            WHERE airline_name = %s
            AND price IS NOT NULL
        """, (request.airline_name,))
        airline_stats = cursor.fetchone()

        if airline_stats and airline_stats[0]:
            input_data['airline_avg_price'] = [float(airline_stats[0])]

        cursor.close()
        conn.close()

        df = pd.DataFrame(input_data)

        # Encode categorical columns
        feature_cols = metrics['features']
        for col, encoder in encoders.items():
            if col in df.columns:
                df[col] = df[col].fillna('unknown')
                df[col] = df[col].apply(
                    lambda x: x if x in encoder.classes_ else 'unknown'
                )
                df[col] = encoder.transform(df[col].astype(str))

        # Fill numeric nulls with 0
        for col in feature_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        # Make prediction
        X = df[feature_cols]
        predicted_price = model.predict(X)[0]

        # Determine confidence based on R2
        r2 = metrics['r2']
        confidence = "high" if r2 > 0.9 else "medium" if r2 > 0.7 else "low"

        return PredictionResponse(
            predicted_price=round(float(predicted_price), 2),
            currency="INR",
            confidence=confidence,
            model_r2=r2
        )

    except Exception as e:
        logger.error(f"Prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/lineage/{source_name}")
def get_lineage(source_name: str):
    """Returns lineage summary for a specific source."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT source_name, status, COUNT(*) as count, 
               MIN(ingested_at) as first_ingested,
               MAX(ingested_at) as last_ingested
        FROM lineage_log
        WHERE source_name = %s
        GROUP BY source_name, status
    """, (source_name,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    if not rows:
        raise HTTPException(status_code=404, detail=f"No lineage found for {source_name}")

    return {
        "source": source_name,
        "lineage": [
            {
                "status": r[1],
                "row_count": r[2],
                "first_ingested": str(r[3]),
                "last_ingested": str(r[4])
            }
            for r in rows
        ]
    }

@app.get("/quarantine")
def get_quarantine():
    """Returns quarantine summary — rows that failed quality checks."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT data_source, failure_reason, COUNT(*) as count
        FROM quarantine
        GROUP BY data_source, failure_reason
        ORDER BY count DESC
        LIMIT 20
    """)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    return {
        "quarantine_summary": [
            {
                "source": r[0],
                "failure_reason": r[1],
                "count": r[2]
            }
            for r in rows
        ]
    }

@app.get("/model/metrics")
def get_model_metrics():
    """Returns current ML model performance metrics."""
    if metrics is None:
        raise HTTPException(status_code=503, detail="No model metrics found")

    return {
        "r2": metrics['r2'],
        "mae": metrics['mae'],
        "rmse": metrics['rmse'],
        "training_rows": metrics['training_rows'],
        "testing_rows": metrics['testing_rows'],
        "features": metrics['features']
    }

@app.get("/conflicts")
def get_conflicts():
    """Returns all logged conflicts between data sources."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT field_name, source_1, value_1, source_2, value_2, resolution, resolved_at
        FROM conflict_log
        ORDER BY resolved_at DESC
        LIMIT 50
    """)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    return {
        "conflicts": [
            {
                "field": r[0],
                "source_1": r[1],
                "value_1": r[2],
                "source_2": r[3],
                "value_2": r[4],
                "resolution": r[5],
                "resolved_at": str(r[6])
            }
            for r in rows
        ]
    }