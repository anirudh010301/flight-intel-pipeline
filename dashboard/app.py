import streamlit as st
import requests
import pandas as pd
import psycopg2
import plotly.express as px
import plotly.graph_objects as go
from dotenv import load_dotenv
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

# ── Page Configuration ─────────────────────────────────────────
# Sets the browser tab title, icon and overall layout width
st.set_page_config(
    page_title="Flight Intel Dashboard",
    page_icon="✈️",
    layout="wide"
)

# FastAPI URL
API_URL = "http://localhost:8000"

# ── Database Connection ────────────────────────────────────────
def get_connection():
    """Direct psycopg2 connection — same pattern as our other scripts."""
    return psycopg2.connect(
        host=os.getenv('POSTGRES_HOST'),
        port=os.getenv('POSTGRES_PORT'),
        user=os.getenv('POSTGRES_USER'),
        password=os.getenv('POSTGRES_PASSWORD'),
        dbname=os.getenv('POSTGRES_DB')
    )

@st.cache_data(ttl=300)  # Cache results for 5 minutes — avoids hammering DB
def run_query(query, params=None):
    """Runs a query and returns results as a pandas DataFrame."""
    conn = get_connection()
    df = pd.read_sql(query, conn, params=params)
    conn.close()
    return df

# ── Dark Bloomberg-style theme ─────────────────────────────────
st.markdown("""
    <style>
    .stApp {
        background-color: #0e1117;
    }
    </style>
""", unsafe_allow_html=True)

# ── Sidebar Navigation ──────────────────────────────────────────
st.sidebar.title("✈️ Flight Intel")
page = st.sidebar.radio(
    "Navigate",
    [
        "🏠 Home",
        "🔍 Flight Explorer",
        "🔮 Price Predictor",
        "🤖 AI Assistant",
        "📊 Model Performance",
        "🔗 Data Lineage",
        "⚠️ Quarantine Monitor"
    ]
)

# ── PAGE 1 — Home ───────────────────────────────────────────────
if page == "🏠 Home":
    st.title("✈️ Flight Intelligence Pipeline")
    st.markdown("End-to-end ML pipeline with multi-source ingestion, quality gates and AI assistant")

    # Pull quick stats
    col1, col2, col3, col4 = st.columns(4)

    total_flights = run_query("SELECT COUNT(*) as count FROM mart_flights")
    total_sources = run_query("SELECT COUNT(DISTINCT data_source) as count FROM mart_flights")
    total_quarantine = run_query("SELECT COUNT(*) as count FROM quarantine")
    total_conflicts = run_query("SELECT COUNT(*) as count FROM conflict_log")

    col1.metric("Total Flights", f"{total_flights['count'][0]:,}")
    col2.metric("Data Sources", total_sources['count'][0])
    col3.metric("Quarantined Rows", f"{total_quarantine['count'][0]:,}")
    col4.metric("Conflicts Resolved", total_conflicts['count'][0])

    st.markdown("---")

    # Source breakdown chart
    st.subheader("Data by Source")
    source_df = run_query("""
        SELECT data_source, COUNT(*) as count 
        FROM mart_flights 
        GROUP BY data_source
    """)
    fig = px.pie(source_df, values='count', names='data_source', 
                 title='Flight Records by Source')
    st.plotly_chart(fig, use_container_width=True)

# ── PAGE 2 — Flight Explorer ────────────────────────────────────
elif page == "🔍 Flight Explorer":
    st.title("🔍 Flight Explorer")

    # Filters
    col1, col2 = st.columns(2)
    origin = col1.text_input("Origin City", "Delhi")
    destination = col2.text_input("Destination City", "Mumbai")

    if st.button("Search Flights"):
        df = run_query("""
            SELECT airline_name, origin_city, destination_city, 
                   duration_hours, price, num_stops, travel_class, data_source
            FROM mart_flights
            WHERE origin_city ILIKE %(origin)s 
            AND destination_city ILIKE %(dest)s
            AND price IS NOT NULL
            ORDER BY price ASC
            LIMIT 100
        """, params={'origin': f'%{origin}%', 'dest': f'%{destination}%'})

        if len(df) > 0:
            st.success(f"Found {len(df)} flights")

            col1, col2, col3 = st.columns(3)
            col1.metric("Average Price", f"₹{df['price'].mean():,.0f}")
            col2.metric("Cheapest", f"₹{df['price'].min():,.0f}")
            col3.metric("Most Expensive", f"₹{df['price'].max():,.0f}")

            st.dataframe(df, use_container_width=True)

            fig = px.box(df, x='airline_name', y='price', title='Price by Airline')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("No flights found for this route")

# ── PAGE 3 — Price Predictor ────────────────────────────────────
elif page == "🔮 Price Predictor":
    st.title("🔮 Price Predictor")
    st.markdown("Get an ML-powered price prediction for any route")

    col1, col2 = st.columns(2)
    with col1:
        airline = st.selectbox("Airline", ["Indigo", "Air_India", "SpiceJet", "Vistara", "GO_FIRST", "AirAsia"])
        origin = st.text_input("Origin City", "Delhi", key="pred_origin")
        destination = st.text_input("Destination City", "Mumbai", key="pred_dest")
        travel_class = st.selectbox("Travel Class", ["Economy", "Business"])

    with col2:
        duration = st.slider("Duration (hours)", 1.0, 20.0, 2.5)
        stops = st.selectbox("Number of Stops", ["zero", "one", "two_or_more"])
        days_until = st.slider("Days Until Departure", 1, 60, 10)

    if st.button("Predict Price", type="primary"):
        with st.spinner("Calling ML model..."):
            try:
                response = requests.post(
                    f"{API_URL}/predict",
                    json={
                        "airline_name": airline,
                        "origin_city": origin,
                        "destination_city": destination,
                        "duration_hours": duration,
                        "num_stops": stops,
                        "travel_class": travel_class,
                        "days_until_departure": days_until
                    },
                    timeout=10
                )
                if response.status_code == 200:
                    result = response.json()
                    st.success("Prediction complete!")

                    col1, col2, col3 = st.columns(3)
                    col1.metric("Predicted Price", f"₹{result['predicted_price']:,.2f}")
                    col2.metric("Confidence", result['confidence'].upper())
                    col3.metric("Model Accuracy (R2)", f"{result['model_r2']*100:.2f}%")
                else:
                    st.error(f"Prediction failed: {response.json().get('detail')}")
            except Exception as e:
                st.error(f"Could not reach API: {e}")

# ── PAGE 4 — AI Assistant ────────────────────────────────────────
elif page == "🤖 AI Assistant":
    st.title("🤖 AI Flight Assistant")
    st.markdown("Ask me anything about flight prices — I use real data + ML to answer")

    col1, col2 = st.columns(2)
    origin = col1.text_input("Origin City", "Delhi", key="ai_origin")
    destination = col2.text_input("Destination City", "Mumbai", key="ai_dest")

    question = st.text_area("Your Question", "Should I book this flight now or wait?")

    if st.button("Ask Assistant", type="primary"):
        with st.spinner("Thinking... (Llama 3 is analyzing real data)"):
            sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from ai_assistant.flight_assistant import ask_flight_assistant

            result = ask_flight_assistant(question, origin, destination)

            st.markdown("### 💬 Answer")
            st.info(result['answer'])

            with st.expander("📊 See data used for this answer"):
                st.text(result['context_used'])

# ── PAGE 5 — Model Performance ──────────────────────────────────
elif page == "📊 Model Performance":
    st.title("📊 ML Model Performance")

    try:
        response = requests.get(f"{API_URL}/model/metrics")
        if response.status_code == 200:
            metrics = response.json()

            col1, col2, col3 = st.columns(3)
            col1.metric("R2 Score", f"{metrics['r2']*100:.2f}%")
            col2.metric("MAE", f"₹{metrics['mae']:,.2f}")
            col3.metric("RMSE", f"₹{metrics['rmse']:,.2f}")

            st.markdown("---")
            st.subheader("Training Details")
            col1, col2 = st.columns(2)
            col1.metric("Training Rows", f"{metrics['training_rows']:,}")
            col2.metric("Testing Rows", f"{metrics['testing_rows']:,}")

            st.subheader("Features Used")
            st.write(metrics['features'])

            # Show pre-generated charts if they exist
            st.markdown("---")
            st.subheader("Feature Importance")
            if os.path.exists("ml/charts/feature_importance.png"):
                st.image("ml/charts/feature_importance.png")

            st.subheader("Actual vs Predicted")
            if os.path.exists("ml/charts/actual_vs_predicted.png"):
                st.image("ml/charts/actual_vs_predicted.png")
        else:
            st.warning("Could not load model metrics")
    except Exception as e:
        st.error(f"Could not reach API: {e}")

# ── PAGE 6 — Data Lineage ────────────────────────────────────────
elif page == "🔗 Data Lineage":
    st.title("🔗 Data Lineage Tracker")
    st.markdown("See exactly where every row came from")

    source = st.selectbox("Select Source", ["kaggle_indian", "kaggle_us", "aviationstack_api"])

    try:
        response = requests.get(f"{API_URL}/lineage/{source}")
        if response.status_code == 200:
            data = response.json()
            for record in data['lineage']:
                st.json(record)
        else:
            st.warning("No lineage data found")
    except Exception as e:
        st.error(f"Could not reach API: {e}")

    st.markdown("---")
    st.subheader("Conflicts Resolved")
    try:
        response = requests.get(f"{API_URL}/conflicts")
        if response.status_code == 200:
            conflicts = response.json()['conflicts']
            if conflicts:
                df = pd.DataFrame(conflicts)
                st.dataframe(df, use_container_width=True)
            else:
                st.info("No conflicts logged yet")
    except Exception as e:
        st.error(f"Could not reach API: {e}")

# ── PAGE 7 — Quarantine Monitor ──────────────────────────────────
elif page == "⚠️ Quarantine Monitor":
    st.title("⚠️ Quarantine Monitor")
    st.markdown("Rows that failed quality checks — never reached the ML model")

    try:
        response = requests.get(f"{API_URL}/quarantine")
        if response.status_code == 200:
            data = response.json()['quarantine_summary']
            if data:
                df = pd.DataFrame(data)
                st.dataframe(df, use_container_width=True)

                fig = px.bar(df, x='source', y='count', color='failure_reason',
                             title='Quarantined Rows by Source and Reason')
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.success("No quarantined rows! Data quality is perfect.")
    except Exception as e:
        st.error(f"Could not reach API: {e}")