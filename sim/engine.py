"""Time-stepped network simulation.

Each tick: apply scheduled events (users join, leave, change demand, start lying), let elastic
demands drift a little, call core.allocate(), and record the result.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np

from core import USER_TYPES, allocate, make_user
from core.models import User

SCENARIO_DIR = Path(__file__).parent / "scenarios"


def list_scenarios() -> list[dict]:
    out = []
    for p in sorted(SCENARIO_DIR.glob("*.json")):
        cfg = json.loads(p.read_text())
        out.append({"id": p.stem, "name": cfg.get("name", p.stem), "description": cfg.get("description", ""),
                    "capacity": cfg["capacity"], "ticks": cfg["ticks"]})
    return out


def load_scenario(scenario_id: str) -> dict:
    path = SCENARIO_DIR / f"{scenario_id}.json"
    if not path.is_file() or path.parent != SCENARIO_DIR:
        raise ValueError(f"unknown scenario '{scenario_id}'")
    return json.loads(path.read_text())


class Simulation:
    def __init__(self, scenario: dict | str, mechanism: str = "nash_bargaining", seed: int | None = None):
        self.config = load_scenario(scenario) if isinstance(scenario, str) else copy.deepcopy(scenario)
        self.scenario_id = scenario if isinstance(scenario, str) else self.config.get("id", "custom")
        self.mechanism = mechanism
        self.capacity = float(self.config["capacity"])
        self.total_ticks = int(self.config.get("ticks", 60))
        self.noise = float(self.config.get("demand_noise", 0.0))
        self.rng = np.random.default_rng(self.config.get("seed", 42) if seed is None else seed)
        self.tick = 0
        self.users: dict[str, User] = {}
        self.base_demand: dict[str, float] = {}
        self.state: dict = {}
        self.history: list[dict] = []
        self._counters: dict[str, int] = {}
        for group in self.config.get("users", []):
            for _ in range(int(group.get("count", 1))):
                self.add_user(group["type"], **{k: v for k, v in group.items() if k not in ("type", "count")})

    # --- user management -------------------------------------------------
    def _new_id(self, user_type: str) -> str:
        self._counters[user_type] = self._counters.get(user_type, 0) + 1
        return f"{user_type}-{self._counters[user_type]}"

    def add_user(self, user_type: str, user_id: str | None = None, **params) -> User:
        uid = user_id or self._new_id(user_type)
        if uid in self.users:
            raise ValueError(f"user '{uid}' already exists")
        allowed = {"demand", "min_rate", "weight", "budget", "reported_demand", "steepness"}
        user = make_user(uid, user_type, **{k: v for k, v in params.items() if k in allowed})
        self.users[uid] = user
        self.base_demand[uid] = user.demand
        return user

    def remove_user(self, user_id: str) -> None:
        self.users.pop(user_id, None)
        self.base_demand.pop(user_id, None)

    def update_user(self, user_id: str, **params) -> None:
        user = self.users[user_id]
        for key in ("weight", "budget", "reported_demand", "min_rate"):
            if key in params:
                setattr(user, key, params[key])
        if "demand" in params:
            user.demand = float(params["demand"])
            self.base_demand[user_id] = user.demand
        if "honest" in params and params["honest"]:
            user.reported_demand = None

    def _matching(self, selector: dict) -> list[str]:
        if "id" in selector:
            return [selector["id"]] if selector["id"] in self.users else []
        ids = [uid for uid, u in self.users.items() if u.type == selector.get("type", u.type)]
        return ids[: int(selector["count"])] if "count" in selector else ids

    # --- events ----------------------------------------------------------
    def _apply_event(self, ev: dict) -> str:
        action = ev["action"]
        if action == "join":
            made = [self.add_user(ev["type"], **{k: v for k, v in ev.items() if k not in ("tick", "action", "type", "count")})
                    for _ in range(int(ev.get("count", 1)))]
            return f"{len(made)} {USER_TYPES[ev['type']]['label'].lower()} user(s) joined"
        if action == "leave":
            ids = self._matching(ev)
            for uid in ids:
                self.remove_user(uid)
            return f"{len(ids)} user(s) left"
        if action == "set":
            ids = self._matching(ev)
            for uid in ids:
                self.update_user(uid, **ev.get("params", {}))
            return ev.get("label", f"{len(ids)} user(s) changed")
        if action == "capacity":
            self.capacity = float(ev["value"])
            return f"link capacity set to {self.capacity:g} Mbps"
        raise ValueError(f"unknown event action '{action}'")

    def _drift_demands(self) -> None:
        if self.noise <= 0:
            return
        for uid, u in self.users.items():
            if u.elastic:
                base = self.base_demand[uid]
                u.demand = float(max(0.2 * base, base * (1 + self.noise * self.rng.standard_normal())))

    # --- main loop -------------------------------------------------------
    @property
    def done(self) -> bool:
        return self.tick >= self.total_ticks

    def step(self) -> dict:
        events = [self._apply_event(ev) for ev in self.config.get("events", []) if int(ev["tick"]) == self.tick]
        self._drift_demands()
        users = list(self.users.values())
        if users:
            result = allocate(users, self.capacity, self.mechanism, state=self.state)
            rates, metrics, extra = result.rates, result.metrics, result.extra
        else:
            rates, metrics, extra = {}, {}, {}
        record = {
            "tick": self.tick,
            "mechanism": self.mechanism,
            "capacity": self.capacity,
            "events": events,
            "users": [
                {**u.to_dict(), "rate": rates.get(u.id, 0.0), "utility": round(float(u.utility(rates.get(u.id, 0.0))), 4),
                 "starved": bool(u.min_rate > 0 and rates.get(u.id, 0.0) < u.min_rate - 1e-6)}
                for u in users
            ],
            "metrics": metrics,
            "extra": {k: v for k, v in extra.items() if k != "bids_by_user"} | (
                {"bids": extra["bids_by_user"]} if "bids_by_user" in extra else {}),
        }
        self.history.append(record)
        self.tick += 1
        return record

    def run(self) -> list[dict]:
        while not self.done:
            self.step()
        return self.history
