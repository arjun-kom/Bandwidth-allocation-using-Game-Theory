"""Kelly proportional-share auction (non-cooperative game).

Each user i bids w_i (money, at most its budget) and receives

    x_i = C * w_i / sum_j w_j

User i's payoff is  budget_i * U_i(x_i) - w_i : the value of the bandwidth minus what it paid.
Every user plays best response to the others' bids, with damping, until no one wants to change
their bid. That fixed point is a Nash equilibrium. Johari and Tsitsiklis (2004) showed that with
concave utilities the equilibrium loses at most 25% of the optimal total utility (price of
anarchy 4/3).

Because bids are paid, a user who lies about its demand gains nothing here: the bid depends only
on how much the user really values bandwidth.
"""
from __future__ import annotations

import numpy as np

from ..models import User

MIN_BID = 1e-6


def _share(bids: np.ndarray, capacity: float, caps: np.ndarray) -> np.ndarray:
    """Proportional share, with anything above a user's demand handed back to the others."""
    x = np.zeros_like(bids)
    active = np.ones(len(bids), dtype=bool)
    remaining = capacity
    for _ in range(len(bids) + 1):
        total = bids[active].sum()
        if total <= 0 or remaining <= 1e-12:
            break
        trial = np.where(active, remaining * bids / total, 0.0)
        over = active & (trial >= caps - x)
        if not over.any():
            x = x + trial
            break
        x[over] = caps[over]
        remaining = capacity - x.sum()
        active &= ~over
    return x


def _utility_matrix(x: np.ndarray, demand, min_rate, elastic, k) -> np.ndarray:
    """Vectorised utility: row i uses user i's parameters (same formula as core.models.utility)."""
    d, m, e, k = (a[:, None] for a in (demand, min_rate, elastic, k))
    x = np.clip(x, 0.0, d)
    log_u = np.log1p(x) / np.log1p(d)
    sig = lambda z: 1.0 / (1.0 + np.exp(-z))
    s0, sd = sig(-k * m), sig(k * (d - m))
    sig_u = (sig(k * (x - m)) - s0) / np.maximum(sd - s0, 1e-12)
    return np.where(e | (m <= 0), log_u, sig_u)


def best_responses(users: list[User], bids: np.ndarray, capacity: float, others: np.ndarray | None = None) -> np.ndarray:
    """Every user's best bid against the others' current bids, all at once.

    Maximises budget * U(C*w/(w+others)) - w over w in [0, budget] with a grid search
    followed by two rounds of local refinement.
    """
    budgets = np.array([max(u.budget, MIN_BID * 10) for u in users])
    demand = np.array([u.demand for u in users])
    min_rate = np.array([u.min_rate for u in users])
    elastic = np.array([u.elastic for u in users])
    k = np.array([u.steepness if u.steepness > 0 else 2.0 for u in users])
    others = np.maximum(bids.sum() - bids if others is None else others, MIN_BID)[:, None]
    frac = np.unique(np.concatenate([np.geomspace(1e-6, 1, 60), np.linspace(0, 1, 61)[1:]]))
    grid = np.maximum(budgets[:, None] * frac[None, :], MIN_BID)

    def payoff(w):
        x = capacity * w / (w + others)
        return budgets[:, None] * _utility_matrix(x, demand, min_rate, elastic, k) - w

    for _ in range(3):
        values = payoff(grid)
        idx = np.argmax(values, axis=1)
        rows = np.arange(len(users))
        lo = grid[rows, np.maximum(idx - 1, 0)]
        hi = grid[rows, np.minimum(idx + 1, grid.shape[1] - 1)]
        best = grid[rows, idx]
        grid = np.linspace(lo, hi, 21).T
    return np.maximum(best, MIN_BID)


def best_response(user: User, others: float, capacity: float) -> float:
    """One user's best bid when everyone else together bids `others`."""
    return float(best_responses([user], np.array([MIN_BID]), capacity, others=np.array([others]))[0])


def kelly_auction(users: list[User], capacity: float, info: dict | None = None,
                  max_iter: int = 120, damping: float = 0.5, tol: float = 1e-3, **_) -> np.ndarray:
    n = len(users)
    if n == 0:
        return np.zeros(0)
    budgets = np.array([max(u.budget, MIN_BID * 10) for u in users])
    init = (info or {}).get("init_bids")
    bids = np.array(init, dtype=float) if init is not None and len(init) == n else budgets / 2
    bids = np.clip(bids, MIN_BID, budgets)

    converged = False
    it = 0
    recent: list[np.ndarray] = []
    for it in range(1, max_iter + 1):
        # step size shrinks over time so users with all-or-nothing (sigmoid) needs
        # stop jumping between "give up" and "bid for the minimum"
        step = max(0.05, damping / (1 + it / 15))
        # Gauss-Seidel: each user reacts to the latest bids of everyone before it
        new = bids.copy()
        for i in range(n):
            others = new.sum() - new[i]
            br = best_responses([users[i]], new[i:i + 1], capacity, others=np.array([others]))[0]
            new[i] = (1 - step) * new[i] + step * br
        change = np.max(np.abs(new - bids) / budgets)
        bids = new
        recent = (recent + [bids.copy()])[-20:]
        if change < tol:
            converged = True
            break
    if not converged and recent:
        # Users with all-or-nothing needs can cycle forever (a pure equilibrium may not exist
        # when utilities are not concave). Use the time-average of the last bids instead.
        bids = np.mean(recent, axis=0)

    caps = np.array([u.claimed_demand for u in users])
    x = _share(bids, capacity, caps)
    if info is not None:
        info.update(
            bids=bids.tolist(),
            price=float(bids.sum() / capacity),
            iterations=it,
            converged=converged,
        )
    return x
