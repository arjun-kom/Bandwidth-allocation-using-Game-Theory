"""The single entry point the simulator, API and experiments call."""
from __future__ import annotations

from .mechanisms import MECHANISMS
from .mechanisms.nash_bargaining import admitted_mask
from .metrics import compute_metrics
from .models import Allocation, User


def allocate(users: list[User], capacity: float, mechanism: str = "nash_bargaining", state: dict | None = None) -> Allocation:
    """Share `capacity` Mbps among `users` with the chosen mechanism.

    `state` is optional and lets the Kelly auction warm-start from last tick's bids.
    """
    if mechanism not in MECHANISMS:
        raise ValueError(f"unknown mechanism '{mechanism}', expected one of {sorted(MECHANISMS)}")
    if capacity <= 0:
        raise ValueError("capacity must be positive")
    info: dict = {}
    if state and mechanism == "kelly" and state.get("bids_by_user"):
        prev = state["bids_by_user"]
        info["init_bids"] = [prev.get(u.id, u.budget / 2) for u in users]
    x = MECHANISMS[mechanism]["fn"](users, capacity, info=info)
    rates = {u.id: round(float(xi), 4) for u, xi in zip(users, x)}
    extra = dict(info)
    extra.pop("init_bids", None)
    if mechanism == "kelly" and "bids" in extra:
        extra["bids_by_user"] = {u.id: round(b, 5) for u, b in zip(users, extra.pop("bids"))}
        if state is not None:
            state["bids_by_user"] = extra["bids_by_user"]
    if mechanism in ("nash_bargaining", "weighted_priority"):
        mask = admitted_mask(users, capacity, use_weights=mechanism == "weighted_priority")
        extra["not_admitted"] = [u.id for u, ok in zip(users, mask) if not ok]
    return Allocation(mechanism=mechanism, capacity=capacity, rates=rates,
                      metrics=compute_metrics(users, x, capacity), extra=extra)
