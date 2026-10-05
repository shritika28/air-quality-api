import os
import sqlite3
from contextlib import contextmanager

SCHEMA = """
CREATE TABLE IF NOT EXISTS observations (
    city           TEXT NOT NULL,
    ts             TEXT NOT NULL,          -- ISO 8601, UTC
    temperature_c  REAL,
    humidity_pct   REAL,
    precip_mm      REAL,
    pm2_5          REAL,
    pm10           REAL,
    PRIMARY KEY (city, ts)
);
CREATE INDEX IF NOT EXISTS idx_obs_ts ON observations (ts);
"""

UPSERT = """
INSERT INTO observations (city, ts, temperature_c, humidity_pct, precip_mm, pm2_5, pm10)
VALUES (:city, :ts, :temperature_c, :humidity_pct, :precip_mm, :pm2_5, :pm10)
ON CONFLICT (city, ts) DO UPDATE SET
    temperature_c = excluded.temperature_c,
    humidity_pct  = excluded.humidity_pct,
    precip_mm     = excluded.precip_mm,
    pm2_5         = excluded.pm2_5,
    pm10          = excluded.pm10;
"""


@contextmanager
def connect(path: str):
    if path != ":memory:":
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(path: str) -> None:
    with connect(path) as conn:
        conn.executescript(SCHEMA)


def upsert_many(path: str, rows: list[dict]) -> int:
    with connect(path) as conn:
        conn.executemany(UPSERT, rows)
    return len(rows)


def query_observations(path, city=None, start=None, end=None, limit=100, offset=0):
    sql, params = "SELECT * FROM observations WHERE 1=1", {}
    if city:
        sql += " AND city = :city"; params["city"] = city
    if start:
        sql += " AND ts >= :start"; params["start"] = start
    if end:
        sql += " AND ts <= :end"; params["end"] = end
    sql += " ORDER BY ts DESC LIMIT :limit OFFSET :offset"
    params.update(limit=limit, offset=offset)
    with connect(path) as conn:
        return [dict(r) for r in conn.execute(sql, params)]


def city_summary(path: str, city: str) -> dict | None:
    with connect(path) as conn:
        row = conn.execute(
            """SELECT COUNT(*) AS n, AVG(temperature_c) AS avg_temp_c,
                      AVG(pm2_5) AS avg_pm2_5, MAX(pm2_5) AS max_pm2_5,
                      MIN(ts) AS first_ts, MAX(ts) AS last_ts
               FROM observations WHERE city = ?""", (city,)).fetchone()
    return dict(row) if row and row["n"] else None
