"""Shared water-filling solver."""
from __future__ import annotations

import numpy as np


def waterfill(capacity: float, caps, base=None, weights=None, tol: float = 1e-10) -> np.ndarray:
    """Find x_i = min(cap_i, base_i + w_i * level) with sum(x) == capacity.

    If everything fits, every user simply gets their cap.
    """
    caps = np.asarray(caps, dtype=float)
    n = len(caps)
    if n == 0:
        return np.zeros(0)
    base = np.zeros(n) if base is None else np.minimum(np.asarray(base, dtype=float), caps)
    weights = np.ones(n) if weights is None else np.asarray(weights, dtype=float)
    weights = np.maximum(weights, 1e-12)
    if caps.sum() <= capacity + tol:
        return caps.copy()
    if base.sum() >= capacity:
        # even the base does not fit: scale the base down proportionally
        return base * (capacity / base.sum()) if base.sum() > 0 else np.zeros(n)

    def filled(level):
        return np.minimum(caps, base + weights * level)

    lo, hi = 0.0, float(np.max((caps - base) / weights)) + 1.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if filled(mid).sum() > capacity:
            hi = mid
        else:
            lo = mid
        if hi - lo < tol:
            break
    return filled(lo)
