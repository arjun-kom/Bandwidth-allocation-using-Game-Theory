"""Weighted priority game: weighted Nash bargaining (weighted proportional fairness).

Higher-weight users are admitted first when minimum rates do not fit, and they get a share of the
spare capacity proportional to their weight. Nobody with a positive weight is starved of the
spare capacity entirely.
"""
from __future__ import annotations

import numpy as np

from ..models import User
from .nash_bargaining import nash_bargaining


def weighted_priority(users: list[User], capacity: float, **_) -> np.ndarray:
    return nash_bargaining(users, capacity, use_weights=True)
