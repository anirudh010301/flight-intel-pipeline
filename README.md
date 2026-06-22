# ✈️ Flight Intel Pipeline

An end-to-end ML pipeline that ingests real flight data from 3 sources, resolves conflicts, tracks full data lineage, gates quality with custom checks, predicts prices with a self-retraining Random Forest model, and serves everything through FastAPI, Streamlit, and an AI flight assistant powered by local Llama 3 — fully orchestrated by Airflow and containerized with Docker.

---

## 🎯 Project Goal

Build a production-grade flight intelligence pipeline that demonstrates:

- **Multi-source ingestion** with conflict resolution
- **Automated ML retraining** pipeline
- **Data quality gates** that block bad data before it reaches the model
- **Full lineage tracking** — every row knows where it came from
- **RAG + ML AI assistant** that answers questions using real data + predictions

---

## 🏗️ Architecture

Kaggle Indian CSV ─┐

Kaggle US CSV ─┼─→ Lineage Tracking → Quality Gates → Conflict Resolution

AviationStack API ─┘ ↓ ↓

Lineage Log Quarantine Table

↓

PostgreSQL (raw_flights)

↓

dbt (staging → ODS → marts)

↓

Random Forest Price Prediction Model

↓

┌──────────────────────────────┤

↓ ↓

FastAPI REST Streamlit Dashboard

↓ ↓

AI Assistant (RAG) 7 Interactive Pages

Llama 3 + PostgreSQL

↓

Airflow (4 DAGs daily)

↓

Docker Compose

---

## 🛠️ Tech Stack

| Layer            | Tool                                    |
| ---------------- | --------------------------------------- |
| Data Sources     | Kaggle CSV x2 + AviationStack API       |
| Database         | PostgreSQL 15                           |
| Transformation   | dbt (staging → ODS → marts)             |
| Data Quality     | Custom quality gates + quarantine table |
| Lineage          | Custom PostgreSQL lineage_log table     |
| ML               | Scikit-learn Random Forest + joblib     |
| AI Assistant     | Ollama + Llama 3 + custom RAG pipeline  |
| API              | FastAPI                                 |
| Dashboard        | Streamlit                               |
| Orchestration    | Airflow (4 DAGs)                        |
| Containerization | Docker + Docker Compose                 |
| Version Control  | Git + GitHub                            |

---

## 📊 ML Model Performance

| Metric        | Value                    |
| ------------- | ------------------------ |
| R2 Score      | 0.9676 (96.76% accuracy) |
| MAE           | ₹2,045 average error     |
| RMSE          | ₹4,079                   |
| Training rows | 720,367                  |
| Features      | 15                       |

---

## 🚀 Quick Start

### Prerequisites

- Docker + Docker Compose
- Python 3.12
- Ollama with Llama 3 (`ollama pull llama3`)

### 1. Clone the repository

```bash
git clone https://github.com/anirudh010301/flight-intel-pipeline.git
cd flight-intel-pipeline
```

### 2. Set up environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
cp .env.example .env
# Edit .env with your credentials
```

### 4. Start core services

```bash
docker-compose -f docker/docker-compose.yml up -d
```

### 5. Download data and run ingestion

```bash
# Download Kaggle datasets and place in data/raw/
python processing/conflict_resolver.py
```

### 6. Run dbt transformations

```bash
cd dbt_project
dbt run
dbt test
```

### 7. Train ML model

```bash
python ml/train_model.py
```

### 8. Start API and Dashboard

```bash
# Terminal 1
uvicorn api.main:app --port 8000

# Terminal 2
streamlit run dashboard/app.py
```

---

## 📁 Project Structure

flight-intel-pipeline/

├── ingestion/ # Data fetching scripts (3 sources)

├── processing/ # Conflict resolution

├── quality/ # Quality gates + quarantine

├── lineage/ # Lineage tracking

├── dbt_project/ # dbt transformations

│ └── models/

│ ├── staging/ # stg_flights

│ ├── ods/ # ods_flights

│ └── marts/ # mart_flights

├── ml/ # ML model training + visualization

│ ├── models/ # Saved model files

│ └── charts/ # Pre-generated charts

├── ai_assistant/ # RAG + Llama 3 assistant

├── api/ # FastAPI REST layer

├── dashboard/ # Streamlit 7-page dashboard

├── dags/ # Airflow DAGs (4 DAGs)

├── docker/ # Dockerfiles + docker-compose

└── airflow/ # Airflow configuration

---

## 🌐 API Endpoints

| Method | Endpoint            | Purpose                |
| ------ | ------------------- | ---------------------- |
| GET    | `/`                 | Health check           |
| GET    | `/airlines`         | List all airlines      |
| GET    | `/routes`           | Routes with avg prices |
| POST   | `/predict`          | ML price prediction    |
| GET    | `/lineage/{source}` | Lineage for a source   |
| GET    | `/quarantine`       | Quality gate failures  |
| GET    | `/model/metrics`    | Model performance      |
| GET    | `/conflicts`        | Resolved conflicts     |

---

## 📋 Airflow DAGs

| DAG             | Schedule | Purpose                 |
| --------------- | -------- | ----------------------- |
| `dag_ingest`    | Midnight | Ingest all 3 sources    |
| `dag_transform` | 1am      | Run dbt transformations |
| `dag_ml`        | 2am      | Retrain ML model        |
| `dag_quality`   | 3am      | Quality audit           |

---

## 🤖 AI Assistant

The AI assistant uses a custom RAG pipeline:

1. **Retrieves** historical prices from PostgreSQL
2. **Retrieves** airline comparison data
3. **Calls** the ML model for price prediction
4. **Asks** Llama 3 to explain everything in plain English

Example:

> **Q:** Should I book Delhi to Mumbai now or wait?
> **A:** Based on 45,867 historical flights, the average price is ₹19,355. Our ML model predicts ₹6,313 for booking today with high confidence (96.76% R2). Booking now could save you around ₹13,000 compared to the average.

---

## 🔑 Key Engineering Concepts

| Concept                | Implementation                                 |
| ---------------------- | ---------------------------------------------- |
| Multi-source ingestion | 3 different formats reconciled into one schema |
| Conflict resolution    | Trust hierarchy + conflict_log table           |
| Data lineage           | Every row tagged with source + hash            |
| Quality gates          | 7 rules, failures go to quarantine table       |
| ML retraining          | Airflow retrains daily on fresh data           |
| RAG + ML               | LLM grounded in real DB data + ML predictions  |

---

## 📝 License

MIT License

## 📝 Author

👨‍💻 Anirudh Adda
