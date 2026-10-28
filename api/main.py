"""FastAPI server: REST for one-off allocations and experiments, WebSocket for live simulations."""
from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from core import MECHANISMS, USER_TYPES, allocate, make_user
from sim import Simulation, list_scenarios

from . import storage

ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = Path(os.environ.get("BWA_RESULTS", ROOT / "results"))
STATIC_DIR = Path(os.environ.get("BWA_STATIC", ROOT / "dashboard" / "dist"))

app = FastAPI(title="Game-Theoretic Bandwidth Allocation", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class UserIn(BaseModel):
    id: str = Field(min_length=1, max_length=40)
    type: str
    demand: Optional[float] = Field(default=None, gt=0, le=10000)
    min_rate: Optional[float] = Field(default=None, ge=0, le=10000)
    weight: Optional[float] = Field(default=None, gt=0, le=100)
    budget: Optional[float] = Field(default=None, gt=0, le=10000)
    reported_demand: Optional[float] = Field(default=None, gt=0, le=10000)


class AllocateIn(BaseModel):
    capacity: float = Field(gt=0, le=100000)
    mechanism: str = "nash_bargaining"
    users: list[UserIn] = Field(min_length=1, max_length=200)


class CompareIn(BaseModel):
    capacity: float = Field(gt=0, le=100000)
    users: list[UserIn] = Field(min_length=1, max_length=200)


def _users(items: list[UserIn]):
    ids = [u.id for u in items]
    if len(set(ids)) != len(ids):
        raise HTTPException(422, "user ids must be unique")
    try:
        return [make_user(u.id, u.type, **u.model_dump(exclude={"id", "type"})) for u in items]
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/meta")
def meta():
    return {
        "user_types": USER_TYPES,
        "mechanisms": {k: {kk: vv for kk, vv in v.items() if kk != "fn"} for k, v in MECHANISMS.items()},
        "scenarios": list_scenarios(),
    }


@app.post("/api/allocate")
def allocate_once(body: AllocateIn):
    if body.mechanism not in MECHANISMS:
        raise HTTPException(422, f"unknown mechanism '{body.mechanism}'")
    users = _users(body.users)
    return {"allocation": allocate(users, body.capacity, body.mechanism).to_dict(),
            "users": [u.to_dict() for u in users]}


@app.post("/api/compare")
def compare(body: CompareIn):
    users = _users(body.users)
    return {"users": [u.to_dict() for u in users],
            "results": {m: allocate(users, body.capacity, m).to_dict() for m in MECHANISMS}}


# --- experiments ---------------------------------------------------------
_exp_state = {"running": False, "error": None, "finished_at": None}


def _run_experiments():
    from experiments.run_all import run_all

    try:
        run_all(RESULTS_DIR, charts=True, verbose=False)
        _exp_state.update(error=None, finished_at=time.time())
    except Exception as e:  # pragma: no cover - surfaced to the dashboard
        _exp_state["error"] = str(e)
    finally:
        _exp_state["running"] = False


@app.get("/api/experiments")
def experiments():
    path = RESULTS_DIR / "results.json"
    data = json.loads(path.read_text()) if path.is_file() else None
    charts = sorted(p.name for p in RESULTS_DIR.glob("*.png")) if RESULTS_DIR.is_dir() else []
    return {"results": data, "charts": charts, **_exp_state}


@app.post("/api/experiments/run", status_code=202)
def run_experiments():
    if not _exp_state["running"]:
        _exp_state["running"] = True
        threading.Thread(target=_run_experiments, daemon=True).start()
    return _exp_state


@app.get("/api/experiments/charts/{name}")
def chart(name: str):
    path = (RESULTS_DIR / name).resolve()
    if path.parent != RESULTS_DIR.resolve() or path.suffix != ".png" or not path.is_file():
        raise HTTPException(404, "chart not found")
    return FileResponse(path)


# --- run history ---------------------------------------------------------
@app.get("/api/runs")
def runs():
    return storage.list_runs()


@app.get("/api/runs/{run_id}")
def run_detail(run_id: int):
    r = storage.get_run(run_id)
    if r is None:
        raise HTTPException(404, "run not found")
    return r


# --- live simulation -----------------------------------------------------
@app.websocket("/ws/simulate")
async def simulate(ws: WebSocket):
    """Protocol (JSON messages).

    client -> server: {"type": "start", "scenario": "peak_hour", "mechanism": "kelly", "speed": 2}
                      {"type": "pause"} {"type": "resume"} {"type": "step"}
                      {"type": "set_mechanism", "mechanism": "..."} {"type": "set_speed", "speed": 4}
                      {"type": "set_capacity", "capacity": 50}
                      {"type": "add_user", "user_type": "video", "weight": 2, "demand": 8, "budget": 10}
                      {"type": "remove_user", "id": "video-3"}
                      {"type": "update_user", "id": "download-1", "params": {"reported_demand": 40}}
                      {"type": "extend", "ticks": 60}
    server -> client: {"type": "started", ...} {"type": "tick", "record": {...}} {"type": "done", "run_id": 3}
                      {"type": "error", "message": "..."}
    """
    await ws.accept()
    ctl = {"sim": None, "paused": True, "speed": 2.0, "step_once": False, "started": 0.0, "saved": False}
    lock = asyncio.Lock()

    async def send(msg):
        await ws.send_text(json.dumps(msg))

    def save():
        sim = ctl["sim"]
        if sim is not None and sim.history and not ctl["saved"]:
            ctl["saved"] = True
            return storage.save_run(sim.scenario_id, sim.history, ctl["started"])
        return None

    async def handle(msg: dict):
        kind = msg.get("type")
        sim = ctl["sim"]
        if kind == "start":
            mech = msg.get("mechanism", "nash_bargaining")
            if mech not in MECHANISMS:
                raise ValueError(f"unknown mechanism '{mech}'")
            await asyncio.to_thread(save)
            ctl.update(sim=Simulation(msg.get("scenario", "peak_hour"), mech), paused=False, saved=False,
                       started=time.time(), speed=float(msg.get("speed", ctl["speed"])))
            s = ctl["sim"]
            await send({"type": "started", "scenario": s.scenario_id, "name": s.config.get("name"),
                        "description": s.config.get("description"), "ticks": s.total_ticks, "mechanism": mech})
            return
        if sim is None:
            raise ValueError("send a 'start' message first")
        if kind == "pause":
            ctl["paused"] = True
        elif kind == "resume":
            ctl["paused"] = False
        elif kind == "step":
            ctl["step_once"] = True
        elif kind == "set_speed":
            ctl["speed"] = min(max(float(msg["speed"]), 0.2), 20)
        elif kind == "set_mechanism":
            if msg["mechanism"] not in MECHANISMS:
                raise ValueError("unknown mechanism")
            sim.mechanism = msg["mechanism"]
            sim.state = {}
        elif kind == "set_capacity":
            cap = float(msg["capacity"])
            if not 0 < cap <= 100000:
                raise ValueError("capacity must be between 0 and 100000 Mbps")
            sim.capacity = cap
        elif kind == "add_user":
            params = {k: msg[k] for k in ("demand", "weight", "budget", "min_rate") if msg.get(k) is not None}
            if len(sim.users) >= 200:
                raise ValueError("at most 200 users")
            sim.add_user(msg["user_type"], **params)
        elif kind == "remove_user":
            sim.remove_user(msg["id"])
        elif kind == "update_user":
            if msg["id"] not in sim.users:
                raise ValueError("unknown user")
            sim.update_user(msg["id"], **msg.get("params", {}))
        elif kind == "extend":
            sim.total_ticks += int(msg.get("ticks", 60))
            ctl["paused"] = False
            ctl["saved"] = False
        else:
            raise ValueError(f"unknown message type '{kind}'")

    async def receiver():
        while True:
            raw = await ws.receive_text()
            try:
                async with lock:
                    await handle(json.loads(raw))
            except (ValueError, KeyError, TypeError) as e:
                await send({"type": "error", "message": str(e)})

    async def ticker():
        while True:
            sim = ctl["sim"]
            if sim is not None and (not ctl["paused"] or ctl["step_once"]) and not sim.done:
                ctl["step_once"] = False
                async with lock:
                    record = await asyncio.to_thread(sim.step)
                await send({"type": "tick", "record": record, "total_ticks": sim.total_ticks})
                if sim.done:
                    run_id = await asyncio.to_thread(save)
                    await send({"type": "done", "run_id": run_id})
                await asyncio.sleep(1.0 / ctl["speed"])
            else:
                await asyncio.sleep(0.05)

    tasks = [asyncio.create_task(receiver()), asyncio.create_task(ticker())]
    try:
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
        for t in done:
            exc = t.exception()
            if exc and not isinstance(exc, WebSocketDisconnect):
                raise exc
    except WebSocketDisconnect:
        pass
    finally:
        for t in tasks:
            t.cancel()
        await asyncio.to_thread(save)


# --- dashboard (built React app) -----------------------------------------
if STATIC_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        file = (STATIC_DIR / path).resolve()
        if path and file.is_file() and STATIC_DIR.resolve() in file.parents:
            return FileResponse(file)
        return FileResponse(STATIC_DIR / "index.html")
