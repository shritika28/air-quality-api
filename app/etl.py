"""Extract -> Transform -> Load. Idempotent: re-running never duplicates rows."""
import logging

import requests

from . import db
from .client import OpenMeteoClient
from .config import CITIES

log = logging.getLogger(__name__)


def transform(city: str, weather: dict, air: dict) -> list[dict]:
    """Join the two hourly series on timestamp and normalise into rows."""
    w, a = weather["hourly"], air["hourly"]
    air_by_ts = {t: (p25, p10) for t, p25, p10 in zip(a["time"], a["pm2_5"], a["pm10"])}
    rows = []
    for ts, temp, hum, rain in zip(
        w["time"], w["temperature_2m"], w["relative_humidity_2m"], w["precipitation"]
    ):
        pm25, pm10 = air_by_ts.get(ts, (None, None))
        if all(v is None for v in (temp, hum, rain, pm25, pm10)):
            continue  # skip empty hours
        rows.append({"city": city, "ts": ts, "temperature_c": temp,
                     "humidity_pct": hum, "precip_mm": rain,
                     "pm2_5": pm25, "pm10": pm10})
    return rows


def run(client: OpenMeteoClient, path: str, cities: dict | None = None,
        past_days: int = 1) -> dict:
    """Ingest every city. One city failing must not stop the others."""
    db.init_db(path)
    report = {"loaded": {}, "failed": {}}
    for name, (lat, lon) in (cities or CITIES).items():
        try:
            weather = client.weather(lat, lon, past_days)
            air = client.air_quality(lat, lon, past_days)
            report["loaded"][name] = db.upsert_many(path, transform(name, weather, air))
        except (requests.RequestException, KeyError, ValueError) as exc:
            log.warning("ingest failed for %s: %s", name, exc)
            report["failed"][name] = str(exc)
    return report
