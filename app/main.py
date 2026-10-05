import secrets
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel

from . import config, db, etl
from .client import OpenMeteoClient


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db(config.db_path())
    yield


app = FastAPI(title="Air Quality API", version="1.0.0", lifespan=lifespan,
              description="Ingests Open-Meteo data and serves it as a clean REST API.")


class Observation(BaseModel):
    city: str
    ts: str
    temperature_c: float | None
    humidity_pct: float | None
    precip_mm: float | None
    pm2_5: float | None
    pm10: float | None


class Summary(BaseModel):
    city: str
    observations: int
    avg_temp_c: float | None
    avg_pm2_5: float | None
    max_pm2_5: float | None
    air_quality: str
    first_ts: str
    last_ts: str


def aqi_category(pm25: float | None) -> str:
    """Simplified US EPA PM2.5 bands (ug/m3)."""
    if pm25 is None:
        return "unknown"
    for limit, label in ((12.0, "good"), (35.4, "moderate"),
                         (55.4, "unhealthy for sensitive groups"), (150.4, "unhealthy")):
        if pm25 <= limit:
            return label
    return "very unhealthy"


def get_client() -> OpenMeteoClient:  # overridable in tests
    return OpenMeteoClient()


def require_api_key(x_api_key: Annotated[str | None, Header()] = None) -> None:
    if not x_api_key or not secrets.compare_digest(x_api_key, config.api_key()):
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key")


def valid_city(city: str) -> str:
    city = city.lower()
    if city not in config.CITIES:
        raise HTTPException(status_code=404, detail=f"Unknown city '{city}'")
    return city


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/cities")
def cities() -> list[str]:
    return sorted(config.CITIES)


@app.get("/observations", response_model=list[Observation])
def observations(
    city: str | None = None,
    start: str | None = Query(None, description="ISO timestamp, inclusive"),
    end: str | None = Query(None, description="ISO timestamp, inclusive"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    if city:
        city = valid_city(city)
    return db.query_observations(config.db_path(), city, start, end, limit, offset)


@app.get("/cities/{city}/summary", response_model=Summary)
def summary(city: str):
    city = valid_city(city)
    s = db.city_summary(config.db_path(), city)
    if not s:
        raise HTTPException(status_code=404, detail="No data yet; POST /ingest first")
    return Summary(city=city, observations=s["n"],
                   avg_temp_c=round(s["avg_temp_c"], 1) if s["avg_temp_c"] is not None else None,
                   avg_pm2_5=round(s["avg_pm2_5"], 1) if s["avg_pm2_5"] is not None else None,
                   max_pm2_5=s["max_pm2_5"], air_quality=aqi_category(s["avg_pm2_5"]),
                   first_ts=s["first_ts"], last_ts=s["last_ts"])


@app.post("/ingest", dependencies=[Depends(require_api_key)])
def ingest(past_days: int = Query(1, ge=1, le=7),
           client: OpenMeteoClient = Depends(get_client)):
    return etl.run(client, config.db_path(), past_days=past_days)
