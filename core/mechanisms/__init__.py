"""Allocation mechanisms. Each one takes (users, capacity) and returns a numpy array of Mbps."""
from .baselines import equal_share, max_min_fair
from .kelly import kelly_auction
from .nash_bargaining import nash_bargaining
from .priority import weighted_priority

MECHANISMS = {
    "nash_bargaining": {
        "label": "Nash bargaining",
        "kind": "cooperative",
        "fn": nash_bargaining,
        "description": "Maximises the product of every user's gain over their minimum rate. Pareto-optimal and proportionally fair.",
    },
    "kelly": {
        "label": "Kelly auction",
        "kind": "non-cooperative",
        "fn": kelly_auction,
        "description": "Users bid money; each gets capacity in proportion to their bid. Bids are updated by best response until a Nash equilibrium.",
    },
    "weighted_priority": {
        "label": "Weighted priority",
        "kind": "cooperative",
        "fn": weighted_priority,
        "description": "Nash bargaining with priority weights: higher-weight users get a bigger share of the spare capacity.",
    },
    "max_min": {
        "label": "Max-min fair",
        "kind": "baseline",
        "fn": max_min_fair,
        "description": "Water-filling: raise everyone equally until their demand is met or capacity runs out.",
    },
    "equal_share": {
        "label": "Equal share",
        "kind": "baseline",
        "fn": equal_share,
        "description": "Everyone gets C / n, capped at their demand. Unused share is wasted.",
    },
}

__all__ = ["MECHANISMS", "equal_share", "max_min_fair", "nash_bargaining", "weighted_priority", "kelly_auction"]
