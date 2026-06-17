import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from loguru import logger
from dotenv import load_dotenv
from sqlalchemy import create_engine
import os
import sys
import joblib

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

# Database connection
DB_URL = f"postgresql+psycopg2://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"

# Paths
MODEL_PATH = "ml/models/flight_price_model.joblib"
ENCODER_PATH = "ml/models/label_encoders.joblib"
CHARTS_DIR = "ml/charts"

def get_engine():
    return create_engine(DB_URL)

def load_data():
    """Loads data from mart_flights for visualization."""
    engine = get_engine()
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
            delay_category,
            route_avg_price,
            route_min_price,
            route_max_price,
            route_avg_duration,
            airline_avg_price,
            airline_avg_delay,
            data_source
        FROM public.mart_flights
        WHERE price IS NOT NULL
        AND price > 0
        AND data_source = 'kaggle_indian'
    """
    df = pd.read_sql(query, engine)
    logger.info(f"Loaded {len(df)} rows for visualization")
    return df

def plot_price_distribution(df):
    """
    Chart 1 — Price Distribution
    Shows how flight prices are distributed
    Helps understand if prices are skewed or normal
    """
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle('Flight Price Distribution', fontsize=16, fontweight='bold')

    # Histogram
    axes[0].hist(df['price'], bins=50, color='steelblue', edgecolor='white', alpha=0.8)
    axes[0].set_title('Price Distribution')
    axes[0].set_xlabel('Price (INR)')
    axes[0].set_ylabel('Number of Flights')
    axes[0].axvline(df['price'].mean(), color='red', linestyle='--', label=f"Mean: ₹{df['price'].mean():,.0f}")
    axes[0].axvline(df['price'].median(), color='green', linestyle='--', label=f"Median: ₹{df['price'].median():,.0f}")
    axes[0].legend()

    # Box plot by travel class
    economy = df[df['travel_class'] == 'Economy']['price']
    business = df[df['travel_class'] == 'Business']['price']
    axes[1].boxplot([economy, business], labels=['Economy', 'Business'])
    axes[1].set_title('Price by Travel Class')
    axes[1].set_xlabel('Travel Class')
    axes[1].set_ylabel('Price (INR)')

    plt.tight_layout()
    path = f"{CHARTS_DIR}/price_distribution.png"
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    logger.info(f"Saved: {path}")

def plot_price_by_airline(df):
    """
    Chart 2 — Average Price by Airline
    Shows which airlines are cheapest and most expensive
    """
    airline_avg = df.groupby('airline_name')['price'].mean().sort_values(ascending=False)

    fig, ax = plt.subplots(figsize=(12, 6))
    bars = ax.bar(airline_avg.index, airline_avg.values, color='steelblue', edgecolor='white')

    # Add value labels on bars
    for bar, val in zip(bars, airline_avg.values):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 200,
                f'₹{val:,.0f}', ha='center', va='bottom', fontsize=9)

    ax.set_title('Average Flight Price by Airline', fontsize=14, fontweight='bold')
    ax.set_xlabel('Airline')
    ax.set_ylabel('Average Price (INR)')
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()

    path = f"{CHARTS_DIR}/price_by_airline.png"
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    logger.info(f"Saved: {path}")

def plot_price_vs_days(df):
    """
    Chart 3 — Price vs Days Until Departure
    Shows how price changes as departure date approaches
    This is the most important insight for the AI assistant
    """
    # Sample 5000 rows for cleaner visualization
    sample = df.sample(min(5000, len(df)), random_state=42)

    fig, ax = plt.subplots(figsize=(12, 6))
    scatter = ax.scatter(
        sample['days_until_departure'],
        sample['price'],
        alpha=0.3,
        c=sample['price'],
        cmap='RdYlGn_r',
        s=10
    )

    # Add trend line
    z = np.polyfit(sample['days_until_departure'], sample['price'], 2)
    p = np.poly1d(z)
    x_line = np.linspace(sample['days_until_departure'].min(),
                          sample['days_until_departure'].max(), 100)
    ax.plot(x_line, p(x_line), "r--", linewidth=2, label='Trend')

    plt.colorbar(scatter, label='Price (INR)')
    ax.set_title('Flight Price vs Days Until Departure', fontsize=14, fontweight='bold')
    ax.set_xlabel('Days Until Departure')
    ax.set_ylabel('Price (INR)')
    ax.legend()
    plt.tight_layout()

    path = f"{CHARTS_DIR}/price_vs_days.png"
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    logger.info(f"Saved: {path}")

def plot_feature_importance(df):
    """
    Chart 4 — Feature Importance
    Shows which features the ML model relies on most
    Very impressive chart for interviews and dashboard
    """
    # Load trained model
    model = joblib.load(MODEL_PATH)
    encoders = joblib.load(ENCODER_PATH)

    # Load saved metrics to get exact feature list model was trained on
    metrics = joblib.load('ml/models/model_metrics.joblib')
    trained_features = metrics['features']

    importances = model.feature_importances_
    feature_importance_df = pd.DataFrame({
        'feature': trained_features,
        'importance': importances
    }).sort_values('importance', ascending=True)

    fig, ax = plt.subplots(figsize=(10, 8))
    bars = ax.barh(
        feature_importance_df['feature'],
        feature_importance_df['importance'],
        color='steelblue',
        edgecolor='white'
    )

    # Add value labels
    for bar, val in zip(bars, feature_importance_df['importance']):
        ax.text(bar.get_width() + 0.001, bar.get_y() + bar.get_height()/2,
                f'{val:.3f}', va='center', fontsize=9)

    ax.set_title('Feature Importance — What Drives Flight Prices?',
                 fontsize=14, fontweight='bold')
    ax.set_xlabel('Importance Score')
    ax.set_ylabel('Feature')
    plt.tight_layout()

    path = f"{CHARTS_DIR}/feature_importance.png"
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    logger.info(f"Saved: {path}")

def plot_actual_vs_predicted(df):
    """
    Chart 5 — Actual vs Predicted Prices
    Shows how well our model predicts prices
    Perfect model = all points on diagonal line
    """
    # Load model and encoders
    model = joblib.load(MODEL_PATH)
    encoders = joblib.load(ENCODER_PATH)

    # Prepare sample for prediction
    sample = df.sample(min(2000, len(df)), random_state=42).copy()

    # Load exact feature list from saved metrics
    metrics = joblib.load('ml/models/model_metrics.joblib')
    available_features = metrics['features']

    feature_cols = [
        'airline_name', 'origin_city', 'destination_city',
        'duration_hours', 'num_stops', 'travel_class',
        'days_until_departure', 'price_category', 'duration_category',
        'route_avg_price', 'route_min_price', 'route_max_price',
        'route_avg_duration', 'airline_avg_price', 'airline_avg_delay'
    ]

    # Encode categorical columns
    for col, encoder in encoders.items():
        if col in sample.columns:
            sample[col] = sample[col].fillna('unknown')
            # Handle unseen labels
            sample[col] = sample[col].apply(
                lambda x: x if x in encoder.classes_ else 'unknown'
            )
            sample[col] = encoder.transform(sample[col].astype(str))

    # Fill numeric nulls
    for col in available_features:
        if sample[col].dtype in ['float64', 'int64']:
            sample[col] = sample[col].fillna(sample[col].median())

    # Make predictions
    X_sample = sample[available_features]
    y_actual = sample['price']
    y_pred = model.predict(X_sample)

    # Plot
    fig, ax = plt.subplots(figsize=(10, 8))
    ax.scatter(y_actual, y_pred, alpha=0.3, color='steelblue', s=10)

    # Perfect prediction line
    min_val = min(y_actual.min(), y_pred.min())
    max_val = max(y_actual.max(), y_pred.max())
    ax.plot([min_val, max_val], [min_val, max_val], 'r--',
            linewidth=2, label='Perfect Prediction')

    ax.set_title('Actual vs Predicted Flight Prices', fontsize=14, fontweight='bold')
    ax.set_xlabel('Actual Price (INR)')
    ax.set_ylabel('Predicted Price (INR)')
    ax.legend()
    plt.tight_layout()

    path = f"{CHARTS_DIR}/actual_vs_predicted.png"
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    logger.info(f"Saved: {path}")

def plot_price_by_stops(df):
    """
    Chart 6 — Price by Number of Stops
    Shows how stops affect price
    """
    fig, ax = plt.subplots(figsize=(10, 6))

    stop_avg = df.groupby('num_stops')['price'].mean().sort_values(ascending=False)
    bars = ax.bar(stop_avg.index, stop_avg.values, color=['steelblue', 'orange', 'green'])

    for bar, val in zip(bars, stop_avg.values):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 200,
                f'₹{val:,.0f}', ha='center', va='bottom', fontsize=11)

    ax.set_title('Average Price by Number of Stops', fontsize=14, fontweight='bold')
    ax.set_xlabel('Number of Stops')
    ax.set_ylabel('Average Price (INR)')
    plt.tight_layout()

    path = f"{CHARTS_DIR}/price_by_stops.png"
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    logger.info(f"Saved: {path}")

if __name__ == "__main__":
    logger.info("Generating ML visualization charts...")

    # Create charts directory
    os.makedirs(CHARTS_DIR, exist_ok=True)

    # Load data
    df = load_data()

    # Generate all charts
    logger.info("Chart 1 — Price Distribution...")
    plot_price_distribution(df)

    logger.info("Chart 2 — Price by Airline...")
    plot_price_by_airline(df)

    logger.info("Chart 3 — Price vs Days Until Departure...")
    plot_price_vs_days(df)

    logger.info("Chart 4 — Feature Importance...")
    plot_feature_importance(df)

    logger.info("Chart 5 — Actual vs Predicted...")
    plot_actual_vs_predicted(df)

    logger.info("Chart 6 — Price by Stops...")
    plot_price_by_stops(df)

    logger.success(f"All charts saved to {CHARTS_DIR}/")