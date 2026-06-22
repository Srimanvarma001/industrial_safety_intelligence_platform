"""
SafetyIQ — SQLite persistence layer.
Replaces in-memory state with an async SQLite database.
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).parent / "data"
DB_PATH = DATA_DIR / "safetyiq.db"

_connection: sqlite3.Connection | None = None


def get_conn() -> sqlite3.Connection:
    global _connection
    if _connection is None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        _connection = sqlite3.connect(str(DB_PATH))
        _connection.row_factory = sqlite3.Row
        _connection.execute("PRAGMA journal_mode=WAL")
        _connection.execute("PRAGMA foreign_keys=ON")
    return _connection


def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS zones (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            workers INTEGER DEFAULT 2,
            base_gas REAL DEFAULT 20,
            gas_thresh REAL DEFAULT 50,
            current_gas REAL DEFAULT NULL,
            permit TEXT DEFAULT NULL,
            maintenance TEXT DEFAULT NULL,
            changeover INTEGER DEFAULT 0,
            updated_at TEXT DEFAULT NULL
        );

        CREATE TABLE IF NOT EXISTS gas_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            zone_id TEXT NOT NULL REFERENCES zones(id),
            reading REAL NOT NULL,
            recorded_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS alerts (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            zone_id TEXT NOT NULL,
            score INTEGER NOT NULL,
            timestamp TEXT NOT NULL,
            channels_dispatched TEXT DEFAULT '[]'
        );

        CREATE TABLE IF NOT EXISTS incidents (
            id TEXT PRIMARY KEY,
            zone_id TEXT NOT NULL,
            report TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_gas_history_zone ON gas_history(zone_id, recorded_at);
        CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON alerts(timestamp DESC);
        CREATE INDEX IF NOT EXISTS idx_incidents_created ON incidents(created_at DESC);
    """)
    conn.commit()

    _seed_zones()


def _seed_zones():
    conn = get_conn()
    existing = conn.execute("SELECT COUNT(*) FROM zones").fetchone()[0]
    if existing > 0:
        return

    default_zones = [
        ("Z1", "Blast Furnace A", 4, 28, 50, 28, None, None, False),
        ("Z2", "Coke Oven Bay", 2, 18, 45, 18, "welding", None, False),
        ("Z3", "Gas Processing", 5, 35, 50, 35, None, None, False),
        ("Z4", "Ore Handling", 3, 12, 60, 12, "hot_work", None, False),
        ("Z5", "Slag Yard", 2, 8, 60, 8, None, None, False),
        ("Z6", "Steam Plant", 4, 22, 50, 22, None, None, True),
        ("Z7", "Cooling Tower", 2, 5, 45, 5, None, None, False),
        ("Z8", "Control Room", 2, 2, 30, 2, None, None, False),
    ]
    now = datetime.now(timezone.utc).isoformat()
    conn.executemany(
        "INSERT INTO zones (id, name, workers, base_gas, gas_thresh, current_gas, permit, maintenance, changeover, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [(z[0], z[1], z[2], z[3], z[4], z[5], z[6], z[7], int(z[8]), now) for z in default_zones],
    )
    conn.commit()

    for z in default_zones:
        conn.execute(
            "INSERT INTO gas_history (zone_id, reading, recorded_at) VALUES (?, ?, ?)",
            (z[0], z[3], now),
        )
    conn.commit()


# ---------------------------------------------------------------------------
# Zone operations
# ---------------------------------------------------------------------------

def get_all_zones() -> list[dict]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM zones ORDER BY id").fetchall()
    return [dict(r) for r in rows]


def get_zone(zone_id: str) -> dict | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM zones WHERE id = ?", (zone_id,)).fetchone()
    return dict(row) if row else None


def update_zone(zone_id: str, **kwargs):
    conn = get_conn()
    fields = []
    values = []
    for key, val in kwargs.items():
        col = key.replace(" ", "_")
        fields.append(f"{col} = ?")
        values.append(val)
    values.append(zone_id)
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        f"UPDATE zones SET {', '.join(fields)}, updated_at = ? WHERE id = ?",
        (*values, now),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Gas history operations
# ---------------------------------------------------------------------------

def add_gas_reading(zone_id: str, reading: float):
    conn = get_conn()
    conn.execute(
        "INSERT INTO gas_history (zone_id, reading, recorded_at) VALUES (?, ?, ?)",
        (zone_id, reading, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    _trim_gas_history(zone_id)


def get_gas_history(zone_id: str, limit: int = 12) -> list[int]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT reading FROM gas_history WHERE zone_id = ? ORDER BY recorded_at DESC LIMIT ?",
        (zone_id, limit),
    ).fetchall()
    return [int(r["reading"]) for r in reversed(rows)]


def _trim_gas_history(zone_id: str, max_records: int = 12):
    conn = get_conn()
    conn.execute(
        """DELETE FROM gas_history WHERE zone_id = ? AND id NOT IN (
            SELECT id FROM gas_history WHERE zone_id = ? ORDER BY recorded_at DESC LIMIT ?
        )""",
        (zone_id, zone_id, max_records),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Alert operations
# ---------------------------------------------------------------------------

def insert_alert(entry: dict):
    conn = get_conn()
    channels_json = json.dumps(entry.get("channels_dispatched", []))
    conn.execute(
        "INSERT OR REPLACE INTO alerts (id, type, title, description, zone_id, score, timestamp, channels_dispatched) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (entry["id"], entry["type"], entry["title"], entry["description"],
         entry["zone_id"], entry["score"], entry["timestamp"], channels_json),
    )
    conn.commit()


def get_recent_alerts(limit: int = 20) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM alerts ORDER BY timestamp DESC LIMIT ?", (limit,)
    ).fetchall()
    results = []
    for r in rows:
        d = dict(r)
        d["channels_dispatched"] = json.loads(d.get("channels_dispatched", "[]"))
        results.append(d)
    return results


# ---------------------------------------------------------------------------
# Incident operations
# ---------------------------------------------------------------------------

def insert_incident(entry: dict):
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO incidents (id, zone_id, report, created_at) VALUES (?, ?, ?, ?)",
        (entry["incident_id"], entry["zone_id"], json.dumps(entry), entry["created_at"]),
    )
    conn.commit()


def get_all_incidents(limit: int = 50) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM incidents ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    return [json.loads(r["report"]) for r in rows]


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------

def reset_all():
    conn = get_conn()
    conn.executescript("""
        DELETE FROM gas_history;
        DELETE FROM alerts;
        DELETE FROM incidents;
        DELETE FROM zones;
    """)
    conn.commit()
    _seed_zones()


def close_db():
    global _connection
    if _connection:
        _connection.close()
        _connection = None
