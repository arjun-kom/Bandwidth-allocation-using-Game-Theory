"""Users (players) and their utility functions.

Every utility is normalised to [0, 1]: 0 means the user gets nothing useful,
1 means their demand is fully met. Bandwidth above the demand adds nothing.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Optional

import numpy as np

# Default parameters per user type. Rates are in Mbps.
# elastic: happy with any bandwidth, diminishing returns (log utility)
# inelastic: nearly useless below min_rate (sigmoid utility)
USER_TYPES: dict[str, dict] = {
    "video": {"label": "Video streaming", "elastic": False, "min_rate": 5.0, "demand": 8.0, "steepness": 1.5, "color": "#e4572e"},
    "gaming": {"label": "Online gaming", "elastic": False, "min_rate": 2.0, "demand": 3.0, "steepness": 4.0, "color": "#7b2cbf"},
    "call": {"label": "Video call", "elastic": False, "min_rate": 3.0, "demand": 4.0, "steepness": 2.5, "color": "#2a9d8f"},
    "web": {"label": "Web browsing", "elastic": True, "min_rate": 0.0, "demand": 2.0, "steepness": 0.0, "color": "#3a86ff"},
    "download": {"label": "File download", "elastic": True, "min_rate": 0.0, "demand": 25.0, "steepness": 0.0, "color": "#f4a261"},
}


@dataclass
class User:
    """One player in the bandwidth game."""

    id: str
    type: str
    demand: float  # true demand in Mbps
    min_rate: float  # below this an inelastic app does not work
    weight: float = 1.0  # priority weight (paid tier, emergency traffic)
    budget: float = 10.0  # money available for bidding in the Kelly auction
    reported_demand: Optional[float] = None  # what the user tells the network; None = honest
    steepness: float = 0.0
    elastic: bool = True

    @property
    def claimed_demand(self) -> float:
        return self.reported_demand if self.reported_demand is not None else self.demand

    @property
    def honest(self) -> bool:
        return self.reported_demand is None or abs(self.reported_demand - self.demand) < 1e-9

    def utility(self, x):
        """Normalised utility of receiving x Mbps (works on floats and numpy arrays)."""
        return utility(x, self.demand, self.min_rate, self.elastic, self.steepness)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["claimed_demand"] = self.claimed_demand
        d["honest"] = self.honest
        return d


def make_user(user_id: str, user_type: str, **overrides) -> User:
    """Build a user from its type defaults, with optional overrides."""
    if user_type not in USER_TYPES:
        raise ValueError(f"unknown user type '{user_type}', expected one of {sorted(USER_TYPES)}")
    t = USER_TYPES[user_type]
    params = dict(
        id=user_id,
        type=user_type,
        demand=t["demand"],
        min_rate=t["min_rate"],
        steepness=t["steepness"],
        elastic=t["elastic"],
    )
    params.update({k: v for k, v in overrides.items() if v is not None})
    user = User(**params)
    if user.demand <= 0:
        raise ValueError("demand must be positive")
    user.min_rate = min(user.min_rate, user.demand)
    return user


def _sigmoid(z):
    return 1.0 / (1.0 + np.exp(-z))


def utility(x, demand: float, min_rate: float, elastic: bool, steepness: float):
    x = np.clip(np.asarray(x, dtype=float), 0.0, demand)
    if elastic or min_rate <= 0:
        return np.log1p(x) / math.log1p(demand)
    k = steepness if steepness > 0 else 2.0
    s0 = _sigmoid(-k * min_rate)
    sd = _sigmoid(k * (demand - min_rate))
    return (_sigmoid(k * (x - min_rate)) - s0) / (sd - s0)


@dataclass
class Allocation:
    """Result of one allocation round."""

    mechanism: str
    capacity: float
    rates: dict[str, float]
    metrics: dict[str, float] = field(default_factory=dict)
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)
