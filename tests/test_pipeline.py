import pytest
import requests
from fastapi.testclient import TestClient

from app import config, db, etl
from app.main import aqi_category, app, get_client

TIMES = ["2026-10-04T00:00", "2026-10-04T01:00", "2026-10-04T02:00"]
WEATHER = {"hourly": {"time": TIMES, "temperature_2m": [14.0, 13.5, None],
                      "relative_humidity_2m": [80, 82, None], "precipitation": [0, 0.2, None]}}
AIR = {"hourly": {"time": TIMES, "pm2_5": [40.0, 50.0, None], "pm10": [60.0, 70.0, None]}}


class FakeClient:
    def weather(self, lat, lon, past_days=1): return WEATHER
    def air_quality(self, lat, lon, past_days=1): return AIR


class FlakyClient(FakeClient):
    def weather(self, lat, lon, past_days=1):
        if lat == 28.2096:  # pokhara
            raise requests.ConnectionError("boom")
        return WEATHER


@pytest.fixture
def path(tmp_path, monkeypatch):
    p = str(tmp_path / "t.db")
    monkeypatch.setenv("DB_PATH", p)
    return p


def test_transform_joins_and_drops_empty_hours():
    rows = etl.transform("kathmandu", WEATHER, AIR)
    assert len(rows) == 2 and rows[0]["pm2_5"] == 40.0


def test_etl_is_idempotent(path):
    etl.run(FakeClient(), path, {"kathmandu": (27.7, 85.3)})
    etl.run(FakeClient(), path, {"kathmandu": (27.7, 85.3)})
    assert len(db.query_observations(path)) == 2


def test_one_city_failing_does_not_stop_others(path):
    report = etl.run(FlakyClient(), path)
    assert "pokhara" in report["failed"] and "kathmandu" in report["loaded"]


def test_api_flow(path):
    app.dependency_overrides[get_client] = lambda: FakeClient()
    with TestClient(app) as c:
        assert c.post("/ingest").status_code == 401
        r = c.post("/ingest", headers={"X-API-Key": config.api_key()})
        assert r.status_code == 200 and r.json()["loaded"]["kathmandu"] == 2
        s = c.get("/cities/kathmandu/summary").json()
        assert s["avg_pm2_5"] == 45.0 and s["air_quality"] == "unhealthy for sensitive groups"
        assert len(c.get("/observations?city=kathmandu&limit=1").json()) == 1
        assert c.get("/observations?city=atlantis").status_code == 404
        assert c.get("/observations?limit=0").status_code == 422
    app.dependency_overrides.clear()


def test_aqi_bands():
    assert aqi_category(5) == "good" and aqi_category(200) == "very unhealthy"
    assert aqi_category(None) == "unknown"
