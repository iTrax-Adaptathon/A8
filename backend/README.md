# FlowCare_2 Backend — Hospital Capacity & Patient Flow Platform

FlowCare_2 is an independent, layered FastAPI backend providing hospital capacity intelligence, bed management, patient lifecycle tracking, and patient flow event orchestration.

## Features
- **Layered Architecture**: API schemas → Application services → Flow Orchestrator → Domain policies & entities → Repositories → SQLite ORM.
- **Capacity Intelligence Engine**: Configurable thresholds (`HIGH_UTILIZATION` >= 75%, `CRITICAL_CAPACITY` >= 90%).
- **Patient Flow Orchestration**: Admission, Transfer, and Discharge pipelines with automatic bed state releases.
- **SQLite Database**: Standalone `flowcare_2.db`.

## Running the Server
```bash
pip install -r requirements.txt
python -m scripts.seed_data
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

OpenAPI Swagger Docs: `http://127.0.0.1:8000/docs`

## Running Tests
```bash
pytest -v
```
