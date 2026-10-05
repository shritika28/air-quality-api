"""Resilient client for the free Open-Meteo APIs (no API key required)."""
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"


class OpenMeteoClient:
    def __init__(self, session: requests.Session | None = None, timeout: float = 10):
        self.timeout = timeout
        self.session = session or self._build_session()

    @staticmethod
    def _build_session() -> requests.Session:
        session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=0.5,  # 0.5s, 1s, 2s between retries
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET",),
        )
        session.mount("https://", HTTPAdapter(max_retries=retry))
        session.headers["User-Agent"] = "air-quality-api/1.0"
        return session

    def _get(self, url: str, params: dict) -> dict:
        resp = self.session.get(url, params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def weather(self, lat: float, lon: float, past_days: int = 1) -> dict:
        return self._get(WEATHER_URL, {
            "latitude": lat, "longitude": lon, "past_days": past_days,
            "forecast_days": 1, "timezone": "UTC",
            "hourly": "temperature_2m,relative_humidity_2m,precipitation",
        })

    def air_quality(self, lat: float, lon: float, past_days: int = 1) -> dict:
        return self._get(AIR_URL, {
            "latitude": lat, "longitude": lon, "past_days": past_days,
            "forecast_days": 1, "timezone": "UTC",
            "hourly": "pm2_5,pm10",
        })
