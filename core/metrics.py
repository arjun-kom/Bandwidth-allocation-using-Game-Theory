"""Evaluation metrics for an allocation. All use the users' TRUE demand."""
from __future__ import annotations

import numpy as np

from .models import User


def jain_index(values) -> float:
    """Jain's fairness index: 1 = perfectly even, 1/n = one user gets everything."""
    v = np.asarray(values, dtype=float)
    if len(v) == 0 or np.all(v == 0):
        return 1.0 if len(v) == 0 else 0.0
    return float(v.sum() ** 2 / (len(v) * (v ** 2).sum()))


def compute_metrics(users: list[User], x, capacity: float) -> dict:
    x = np.asarray(x, dtype=float)
    n = len(users)
    if n == 0:
        return {"jain_fairness": 1.0, "total_utility": 0.0, "mean_utility": 0.0, "mean_satisfaction": 1.0,
                "min_satisfaction": 1.0, "starved_users": 0, "utilization": 0.0, "users": 0}
    demand = np.array([u.demand for u in users])
    useful = np.minimum(x, demand)  # bandwidth above true demand is wasted
    satisfaction = useful / demand
    utilities = np.array([float(u.utility(xi)) for u, xi in zip(users, x)])
    starved = sum(1 for u, xi in zip(users, x) if u.min_rate > 0 and xi < u.min_rate - 1e-6)
    return {
        "jain_fairness": round(jain_index(satisfaction), 4),
        "total_utility": round(float(utilities.sum()), 4),
        "mean_utility": round(float(utilities.mean()), 4),
        "mean_satisfaction": round(float(satisfaction.mean()), 4),
        "min_satisfaction": round(float(satisfaction.min()), 4),
        "starved_users": int(starved),
        "utilization": round(float(x.sum() / capacity) if capacity > 0 else 0.0, 4),
        "useful_utilization": round(float(useful.sum() / capacity) if capacity > 0 else 0.0, 4),
        "users": n,
    }


def price_of_anarchy(users: list[User], x_equilibrium, x_optimum, values=None) -> float:
    """Optimal welfare / equilibrium welfare (1.0 = selfish play costs nothing)."""
    from .optimum import social_welfare

    eq = social_welfare(users, x_equilibrium, values)
    opt = social_welfare(users, x_optimum, values)
    if eq <= 1e-12:
        return float("inf") if opt > 1e-12 else 1.0
    return float(max(opt / eq, 1.0))
