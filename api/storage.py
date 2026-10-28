"""SQLite log of simulation runs (one row per run, per-tick metrics as JSON)."""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from pathlib import Path

DB_PATH = Path(os.environ.get("BWA_DB", Path(__file__).resolve().parent.parent / "data" / "runs.db"))
_lock = threading.Lock()


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("""CREATE TABLE IF NOT EXISTS runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        started_at REAL, scenario TEXT, mechanisms TEXT, ticks INTEGER,
        mean_fairness REAL, mean_utility REAL, mean_starved REAL, metrics TEXT)""")
    return c


def save_run(scenario: str, history: list[dict], started_at: float | None = None) -> int | None:
    rows = [h for h in history if h.get("metrics")]
    if not rows:
        return None
    mean = lambda k: sum(h["metrics"][k] for h in rows) / len(rows)
    per_tick = [{"tick": h["tick"], "mechanism": h["mechanism"], "capacity": h["capacity"], **h["metrics"]} for h in rows]
    mechs = sorted({h["mechanism"] for h in rows})
    with _lock, _conn() as c:
        cur = c.execute(
            "INSERT INTO runs (started_at, scenario, mechanisms, ticks, mean_fairness, mean_utility, mean_starved, metrics) VALUES (?,?,?,?,?,?,?,?)",
            (started_at or time.time(), scenario, ",".join(mechs), len(rows), mean("jain_fairness"),
             mean("total_utility"), mean("starved_users"), json.dumps(per_tick)))
        return cur.lastrowid


def list_runs(limit: int = 50) -> list[dict]:
    with _lock, _conn() as c:
        rows = c.execute("SELECT id, started_at, scenario, mechanisms, ticks, mean_fairness, mean_utility, mean_starved "
                         "FROM runs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def get_run(run_id: int) -> dict | None:
    with _lock, _conn() as c:
        r = c.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
    if r is None:
        return None
    d = dict(r)
    d["metrics"] = json.loads(d["metrics"])
    return d
