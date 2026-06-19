import psycopg2
import requests
import json
from loguru import logger
from dotenv import load_dotenv
import os
import sys

# Add project root to path so this script can be run from anywhere
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env file — gives us access to POSTGRES_HOST, POSTGRES_USER etc
load_dotenv()

# ── Configuration ───────────────────────────────────────────────
# Ollama runs locally and exposes an API on this port by default
OLLAMA_URL = "http://localhost:11434/api/generate"

# Which model Ollama should use — must match what you see in `ollama list`
OLLAMA_MODEL = "llama3"

# Our own FastAPI server — the assistant calls itself essentially,
# reusing the /predict endpoint instead of duplicating ML logic
FASTAPI_URL = "http://localhost:8000"


def get_connection():
    """
    Opens a direct psycopg2 connection to PostgreSQL.
    We use psycopg2 directly (not SQLAlchemy) .
    """
    return psycopg2.connect(
        host=os.getenv('POSTGRES_HOST'),
        port=os.getenv('POSTGRES_PORT'),
        user=os.getenv('POSTGRES_USER'),
        password=os.getenv('POSTGRES_PASSWORD'),
        dbname=os.getenv('POSTGRES_DB')
    )


# ── TOOL 1 — Historical price lookup ───────────────────────────
def get_route_history(origin_city, destination_city):
    """
    Queries mart_flights for real historical stats on a specific route.

    Why this matters for RAG:
    Without this, Llama 3 would have to GUESS prices from its training
    data (which is outdated and not specific to our dataset).
    With this, we hand it real numbers from OUR database.

    ILIKE = case-insensitive partial match in PostgreSQL
    e.g. 'delhi' will match 'Delhi', 'New Delhi' etc
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            COUNT(*) as total_flights,
            ROUND(AVG(price)::numeric, 2) as avg_price,
            ROUND(MIN(price)::numeric, 2) as min_price,
            ROUND(MAX(price)::numeric, 2) as max_price,
            ROUND(AVG(duration_hours)::numeric, 2) as avg_duration
        FROM mart_flights
        WHERE origin_city ILIKE %s
        AND destination_city ILIKE %s
        AND price IS NOT NULL
    """, (f"%{origin_city}%", f"%{destination_city}%"))

    row = cursor.fetchone()
    cursor.close()
    conn.close()

    # row[0] is total_flights — if 0, we found no matching route
    if row and row[0] > 0:
        return {
            "total_flights": row[0],
            "avg_price": float(row[1]) if row[1] else None,
            "min_price": float(row[2]) if row[2] else None,
            "max_price": float(row[3]) if row[3] else None,
            "avg_duration": float(row[4]) if row[4] else None
        }
    return None  # No data found for this route — handled later


# ── TOOL 2 — Airline comparison ────────────────────────────────
def get_airline_info(origin_city, destination_city):
    """
    Returns the top 5 cheapest airlines flying a given route,
    sorted by average price ascending.

    This lets the assistant answer questions like
    "which airline is cheapest for Delhi to Mumbai?"
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            airline_name,
            COUNT(*) as flight_count,
            ROUND(AVG(price)::numeric, 2) as avg_price
        FROM mart_flights
        WHERE origin_city ILIKE %s
        AND destination_city ILIKE %s
        AND price IS NOT NULL
        GROUP BY airline_name
        ORDER BY avg_price ASC
        LIMIT 5
    """, (f"%{origin_city}%", f"%{destination_city}%"))

    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    return [
        {"airline": r[0], "flights": r[1], "avg_price": float(r[2])}
        for r in rows
    ]


# ── TOOL 3 — ML model prediction ───────────────────────────────
def get_ml_prediction(origin_city, destination_city, days_until_departure=7):
    """
    Calls our OWN FastAPI /predict endpoint — the same Random Forest
    model from Phase 6, accessed over HTTP instead of imported
    directly. This keeps the assistant decoupled from ML internals.

    NOTE: Some fields (airline_name, duration_hours, etc) are hardcoded
    defaults here because the user's question may not specify them.
    In a more advanced version, we could have the assistant ask follow-up
    """
    try:
        response = requests.post(
            f"{FASTAPI_URL}/predict",
            json={
                "airline_name": "Indigo",       # Default — most common airline
                "origin_city": origin_city,
                "destination_city": destination_city,
                "duration_hours": 2.5,           # Default — typical domestic flight
                "num_stops": "zero",
                "travel_class": "Economy",
                "days_until_departure": days_until_departure
            },
            timeout=10
        )
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        # If FastAPI isn't running, this fails gracefully instead of crashing
        logger.error(f"ML prediction failed: {e}")
        return None


# ── Generation step — talk to Llama 3 via Ollama ───────────────
def call_llama3(prompt):
    """
    Sends a prompt to the locally running Llama 3 model via Ollama's
    REST API and returns the generated text.

    stream=False means we wait for the FULL response at once,
    rather than getting it token by token.

    temperature=0.3 keeps answers factual and consistent —
    higher values (e.g. 0.8) would make answers more "creative"
    but also more likely to stray from our real data.
    """
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3
                }
            },
            timeout=60
        )
        if response.status_code == 200:
            return response.json().get('response', '')
        return "Sorry, I couldn't generate a response."
    except Exception as e:
        logger.error(f"Llama 3 call failed: {e}")
        return "Sorry, the AI assistant is currently unavailable."


# ── Main RAG orchestrator ──────────────────────────────────────
def ask_flight_assistant(question, origin_city=None, destination_city=None):
    """
    This is the heart of the AI assistant — the RAG pipeline.

    RAG = Retrieval Augmented Generation:
      1. RETRIEVE  — pull real facts from our 3 tools (DB history,
                      DB airlines, ML prediction)
      2. AUGMENT   — stuff those facts into a prompt as "context"
      3. GENERATE  — ask Llama 3 to answer using ONLY that context

    This is what stops the LLM from hallucinating — it's told
    explicitly: here are the facts, answer using only these.
    """
    logger.info(f"Processing question: {question}")

    # We'll collect each piece of retrieved context as a text block
    context_parts = []

    # Only retrieve route-specific data if the user gave us a route
    if origin_city and destination_city:
        logger.info(f"Retrieving data for {origin_city} -> {destination_city}")

        # --- Tool 1: historical prices ---
        history = get_route_history(origin_city, destination_city)
        if history:
            context_parts.append(f"""
Historical data for {origin_city} to {destination_city}:
- Total flights in database: {history['total_flights']}
- Average price: ₹{history['avg_price']}
- Minimum price seen: ₹{history['min_price']}
- Maximum price seen: ₹{history['max_price']}
- Average flight duration: {history['avg_duration']} hours
""")

        # --- Tool 2: airline comparison ---
        airlines = get_airline_info(origin_city, destination_city)
        if airlines:
            airline_text = "\n".join([
                f"  - {a['airline']}: ₹{a['avg_price']} average ({a['flights']} flights)"
                for a in airlines
            ])
            context_parts.append(f"Airlines flying this route (cheapest first):\n{airline_text}")

        # --- Tool 3: ML prediction ---
        prediction = get_ml_prediction(origin_city, destination_city)
        if prediction:
            context_parts.append(f"""
ML Model Prediction:
- Our trained model predicts a price of ₹{prediction['predicted_price']} for booking today
- Model confidence: {prediction['confidence']} (R2 accuracy score: {prediction['model_r2']})
""")

    # Combine all context blocks into one string.
    # If nothing was retrieved (e.g. no route given), say so explicitly —
    # this stops Llama 3 from making something up to fill the gap.
    full_context = "\n".join(context_parts) if context_parts else "No specific route data available."

    # This is the actual instruction sent to Llama 3.
    # The "ONLY" and "Do not make up" lines are deliberate guardrails
    # against hallucination — feel free to tighten/loosen this wording.
    prompt = f"""You are a helpful flight pricing assistant. Answer the user's question using ONLY the real data provided below. Be specific with numbers. Keep your answer concise — 3-4 sentences maximum. Do not make up any information not in the data below.

REAL DATA:
{full_context}

USER QUESTION: {question}

ANSWER:"""

    logger.info("Sending request to Llama 3...")
    answer = call_llama3(prompt)

    # We return context_used too — useful for debugging and for
    # showing "sources" in the dashboard later (transparency!)
    return {
        "question": question,
        "answer": answer,
        "context_used": full_context
    }


# ── Quick manual test when running this file directly ─────────
if __name__ == "__main__":
    logger.info("Testing Flight AI Assistant...")

    result = ask_flight_assistant(
        question="Should I book this flight now or wait? What's a good price?",
        origin_city="Delhi",
        destination_city="Mumbai"
    )

    print("\n" + "="*60)
    print("QUESTION:", result['question'])
    print("="*60)
    print("ANSWER:", result['answer'])
    print("="*60)
    print("\nCONTEXT USED:")
    print(result['context_used'])