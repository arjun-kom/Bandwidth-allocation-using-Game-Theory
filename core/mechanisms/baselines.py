"""Simple baselines to compare the game-theoretic mechanisms against."""
from __future__ import annotations

import numpy as np

from ..models import User
from .waterfill import waterfill


def equal_share(users: list[User], capacity: float, **_) -> np.ndarray:
    """Everyone gets capacity / n, capped at what they asked for. Leftover is wasted."""
    if not users:
        return np.zeros(0)
    share = capacity / len(users)
    return np.array([min(share, u.claimed_demand) for u in users])


def max_min_fair(users: list[User], capacity: float, **_) -> np.ndarray:
    """Max-min fairness by water-filling: no user can get more without a poorer user getting less."""
    return waterfill(capacity, [u.claimed_demand for u in users])
