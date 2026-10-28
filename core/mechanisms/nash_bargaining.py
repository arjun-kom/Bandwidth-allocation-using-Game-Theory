"""Nash Bargaining Solution for bandwidth sharing.

Each user i needs at least m_i (its minimum rate) and wants at most d_i (its demand).
The Nash bargaining problem with disagreement point m_i is

    maximise   sum_i  w_i * log(x_i - m_i)
    subject to sum_i x_i <= C,   m_i <= x_i <= d_i

The KKT conditions give a closed form: x_i = min(d_i, m_i + w_i * lambda), where lambda is
chosen so the link is exactly full. That is a water-filling over the excess above the minimum
(Yaiche, Mazumdar and Rosenberg, 2000).

When the minimum rates do not all fit (sum m_i > C) the bargaining set is empty, so we run
admission control: users are admitted by priority weight (then by smaller minimum) while their
minimums fit. Users who are not admitted have their minimum set to 0, so they still share any
spare capacity but are not guaranteed anything.
"""
from __future__ import annotations

import numpy as np

from ..models import User
from .waterfill import waterfill


def admit(users: list[User], capacity: float, use_weights: bool) -> np.ndarray:
    """Return a boolean mask of users whose minimum rate is guaranteed."""
    mins = np.array([u.min_rate for u in users])
    if mins.sum() <= capacity:
        return np.ones(len(users), dtype=bool)
    order = sorted(
        range(len(users)),
        key=lambda i: (-(users[i].weight if use_weights else 1.0), users[i].min_rate, i),
    )
    admitted = np.zeros(len(users), dtype=bool)
    used = 0.0
    for i in order:
        if used + mins[i] <= capacity + 1e-9:
            admitted[i] = True
            used += mins[i]
    return admitted


def nash_bargaining(users: list[User], capacity: float, use_weights: bool = False, **_) -> np.ndarray:
    if not users:
        return np.zeros(0)
    caps = np.array([u.claimed_demand for u in users])
    admitted = admit(users, capacity, use_weights)
    base = np.where(admitted, [u.min_rate for u in users], 0.0)
    weights = np.array([u.weight for u in users]) if use_weights else np.ones(len(users))
    return waterfill(capacity, caps, base=base, weights=weights)


def admitted_mask(users: list[User], capacity: float, use_weights: bool = False) -> list[bool]:
    return admit(users, capacity, use_weights).tolist() if users else []
