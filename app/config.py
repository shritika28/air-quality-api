import os

# city -> (latitude, longitude)
CITIES: dict[str, tuple[float, float]] = {
    "kathmandu": (27.7172, 85.3240),
    "pokhara": (28.2096, 83.9856),
    "delhi": (28.6139, 77.2090),
    "london": (51.5072, -0.1276),
}


def db_path() -> str:
    return os.getenv("DB_PATH", "data/observations.db")


def api_key() -> str:
    return os.getenv("INGEST_API_KEY", "dev-key")
