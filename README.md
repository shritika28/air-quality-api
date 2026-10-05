# Air Quality API

A small data-engineering project that shows both sides of API work:

- **Consumes** a third-party REST API (Open-Meteo weather + air quality, no key needed)
- **Serves** the cleaned data through its own documented REST API (FastAPI)

```
Open-Meteo APIs ──> client.py (retries, timeouts) ──> etl.py (transform) ──> SQLite
                                                                               │
                                          FastAPI (main.py) <──────────────────┘
```

## What it demonstrates

| Skill | Where |
|---|---|
| Consuming APIs with retry/backoff and timeouts | `app/client.py` |
| ETL: join two sources on timestamp, drop empty rows | `app/etl.py` |
| Idempotent loads (`INSERT ... ON CONFLICT DO UPDATE`) | `app/db.py` |
| Partial-failure handling (one city failing doesn't stop the rest) | `app/etl.py` |
| REST design: pagination, filtering, validation, status codes | `app/main.py` |
| API-key auth with constant-time comparison | `require_api_key` |
| Auto-generated OpenAPI docs | `/docs` |
| Tests with dependency injection (no network needed) | `tests/` |
| Containerisation | `Dockerfile` |

## Run it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/docs, then load data:

```bash
curl -X POST "http://127.0.0.1:8000/ingest?past_days=2" -H "X-API-Key: dev-key"
curl "http://127.0.0.1:8000/cities/kathmandu/summary"
curl "http://127.0.0.1:8000/observations?city=kathmandu&limit=5"
```

Set `INGEST_API_KEY` and `DB_PATH` environment variables for non-dev use.

## Endpoints

| Method | Path | Notes |
|---|---|---|
| GET | `/health` | liveness check |
| GET | `/cities` | supported cities |
| GET | `/observations` | filters: `city`, `start`, `end`; paging: `limit`, `offset` |
| GET | `/cities/{city}/summary` | averages, peak PM2.5, air-quality band |
| POST | `/ingest` | requires `X-API-Key`; pulls fresh data |

## Test / Docker

```bash
pytest
docker build -t air-quality-api . && docker run -p 8000:8000 -v aq-data:/data air-quality-api
```

## Ideas to extend

- Swap SQLite for PostgreSQL (or Azure SQL) and add Alembic migrations
- Schedule `/ingest` with cron, Airflow, or Azure Functions
- Add a GitHub Actions workflow running `pytest` on every push
- Add response caching and rate limiting
