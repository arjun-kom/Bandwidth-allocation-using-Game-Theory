"""Social optimum: the allocation that maximises total (budget-weighted) utility.

Used only as the yardstick for the price of anarchy. Sigmoid utilities make the problem
non-convex, so it is solved with SLSQP from several starting points and the best result is kept.
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import minimize

from .models import User


def social_welfare(users: list[User], x, values=None) -> float:
    values = np.ones(len(users)) if values is None else np.asarray(values)
    return float(sum(v * u.utility(xi) for u, xi, v in zip(users, x, values)))


def social_optimum(users: list[User], capacity: float, values=None, starts=None) -> np.ndarray:
    from .mechanisms import max_min_fair, nash_bargaining, equal_share

    n = len(users)
    if n == 0:
        return np.zeros(0)
    values = np.ones(n) if values is None else np.asarray(values, dtype=float)
    caps = np.array([u.demand for u in users])
    if caps.sum() <= capacity:
        return caps

    def neg(x):
        return -social_welfare(users, x, values)

    candidates = [nash_bargaining(users, capacity), max_min_fair(users, capacity), equal_share(users, capacity)]
    # also try "serve users in order of value per Mbps": greedy fill of minimum rates
    order = np.argsort(-values / np.maximum(caps, 1e-9))
    greedy = np.zeros(n)
    left = capacity
    for i in order:
        greedy[i] = min(caps[i], left)
        left -= greedy[i]
    candidates.append(greedy)
    if starts:
        candidates.extend(np.asarray(s, dtype=float) for s in starts)

    best_x, best_v = None, -np.inf
    cons = [{"type": "ineq", "fun": lambda x: capacity - x.sum()}]
    bounds = [(0.0, c) for c in caps]
    for x0 in candidates:
        x0 = np.clip(np.minimum(x0, caps), 0, None)
        res = minimize(neg, x0, method="SLSQP", bounds=bounds, constraints=cons, options={"maxiter": 300, "ftol": 1e-10})
        for x in (res.x, x0):
            x = np.clip(x, 0, caps)
            if x.sum() > capacity + 1e-6:
                x = x * capacity / x.sum()
            v = -neg(x)
            if v > best_v:
                best_x, best_v = x, v
    return best_x
