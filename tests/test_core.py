import numpy as np
import pytest
from scipy.optimize import minimize

from core import MECHANISMS, allocate, make_user
from core.mechanisms import equal_share, kelly_auction, max_min_fair, nash_bargaining, weighted_priority
from core.mechanisms.kelly import best_response
from core.metrics import compute_metrics, jain_index, price_of_anarchy
from core.optimum import social_optimum


def crowd():
    return [make_user("v1", "video"), make_user("g1", "gaming"), make_user("c1", "call"),
            make_user("w1", "web"), make_user("d1", "download"), make_user("d2", "download")]


def test_utility_is_normalised_and_monotone():
    for t in ["video", "gaming", "call", "web", "download"]:
        u = make_user("x", t)
        xs = np.linspace(0, u.demand * 1.5, 50)
        ys = u.utility(xs)
        assert ys[0] == pytest.approx(0, abs=1e-9)
        assert ys[-1] == pytest.approx(1, abs=1e-9)
        assert np.all(np.diff(ys) >= -1e-12)


def test_inelastic_utility_is_low_below_min_rate():
    v = make_user("v", "video")
    assert v.utility(v.min_rate * 0.5) < 0.1
    assert v.utility(v.demand) == pytest.approx(1)


@pytest.mark.parametrize("name", list(MECHANISMS))
@pytest.mark.parametrize("capacity", [5, 20, 60])
def test_every_mechanism_respects_capacity_and_demand(name, capacity):
    users = crowd()
    x = MECHANISMS[name]["fn"](users, capacity)
    assert x.sum() <= capacity + 1e-6
    assert np.all(x >= -1e-9)
    assert np.all(x <= np.array([u.claimed_demand for u in users]) + 1e-6)


@pytest.mark.parametrize("name", ["nash_bargaining", "kelly", "weighted_priority", "max_min"])
def test_everyone_satisfied_when_link_is_big_enough(name):
    users = crowd()
    x = MECHANISMS[name]["fn"](users, 1000)
    assert np.allclose(x, [u.demand for u in users], atol=1e-3)


def test_max_min_is_water_filling():
    users = [make_user("a", "web", demand=1), make_user("b", "web", demand=10), make_user("c", "web", demand=10)]
    assert np.allclose(max_min_fair(users, 9), [1, 4, 4])


def test_equal_share_wastes_unused_share():
    users = [make_user("a", "web", demand=1), make_user("b", "web", demand=10)]
    assert np.allclose(equal_share(users, 10), [1, 5])


def test_nash_bargaining_matches_numerical_optimum():
    users = crowd()
    C = 25.0
    x = nash_bargaining(users, C)
    m = np.array([u.min_rate for u in users])
    d = np.array([u.demand for u in users])
    obj = lambda z: -np.sum(np.log(np.maximum(z - m, 1e-12)))
    res = minimize(obj, m + (C - m.sum()) / len(users) * 0.9, method="SLSQP",
                   bounds=[(mi + 1e-9, di) for mi, di in zip(m, d)],
                   constraints=[{"type": "ineq", "fun": lambda z: C - z.sum()}])
    assert obj(x) <= res.fun + 1e-4


def test_nash_bargaining_guarantees_minimum_rates_when_they_fit():
    users = crowd()
    x = nash_bargaining(users, 12)  # mins sum to 10
    for u, xi in zip(users, x):
        assert xi >= u.min_rate - 1e-6


def test_admission_control_when_minimums_do_not_fit():
    users = [make_user(f"v{i}", "video") for i in range(4)]  # mins 20 > 12
    a = allocate(users, 12, "nash_bargaining")
    assert len(a.extra["not_admitted"]) == 2
    assert a.metrics["starved_users"] == 2


def test_weighted_priority_favours_high_weight():
    users = [make_user("lo", "download", weight=1), make_user("hi", "download", weight=3)]
    x = weighted_priority(users, 20)
    assert x[1] == pytest.approx(3 * x[0], rel=1e-3)


def test_priority_admits_heavy_weight_first():
    users = [make_user("a", "video"), make_user("b", "video"), make_user("vip", "video", weight=5)]
    a = allocate(users, 11, "weighted_priority")
    assert "vip" not in a.extra["not_admitted"]


def test_kelly_converges_to_equilibrium():
    users = [make_user("w", "web", budget=5), make_user("d1", "download", budget=10), make_user("d2", "download", budget=20)]
    info = {}
    x = kelly_auction(users, 20, info=info)
    assert info["converged"]
    bids = np.array(info["bids"])
    for i, u in enumerate(users):  # nobody can do better by changing their bid
        br = best_response(u, bids.sum() - bids[i], 20)
        assert abs(br - bids[i]) / u.budget < 0.02
    assert x[2] > x[1]  # richer user gets more


def test_kelly_ignores_lies_about_demand():
    honest = [make_user("a", "download", demand=4), make_user("b", "download", demand=20)]
    liar = [make_user("a", "download", demand=4, reported_demand=40), make_user("b", "download", demand=20)]
    i1, i2 = {}, {}
    x1, x2 = kelly_auction(honest, 10, info=i1), kelly_auction(liar, 10, info=i2)
    assert np.allclose(i1["bids"], i2["bids"])  # the bid depends only on true value
    assert x2[0] - x1[0] < 0.2


def test_max_min_rewards_lies_about_demand():
    honest = [make_user("a", "download", demand=4), make_user("b", "download", demand=20)]
    liar = [make_user("a", "download", demand=4, reported_demand=40), make_user("b", "download", demand=20)]
    assert max_min_fair(liar, 10)[0] > max_min_fair(honest, 10)[0]


def test_jain_index():
    assert jain_index([1, 1, 1]) == pytest.approx(1)
    assert jain_index([1, 0, 0]) == pytest.approx(1 / 3)


def test_metrics_shape():
    users = crowd()
    m = compute_metrics(users, nash_bargaining(users, 20), 20)
    assert 0 <= m["jain_fairness"] <= 1
    assert m["utilization"] == pytest.approx(1)
    assert m["users"] == 6


def test_price_of_anarchy_is_at_least_one():
    users = crowd()
    values = np.array([u.budget for u in users])
    x_eq = kelly_auction(users, 20)
    x_opt = social_optimum(users, 20, values=values, starts=[x_eq])
    assert price_of_anarchy(users, x_eq, x_opt, values) >= 1.0


def test_allocate_rejects_bad_input():
    with pytest.raises(ValueError):
        allocate(crowd(), 10, "nope")
    with pytest.raises(ValueError):
        allocate(crowd(), 0)
    with pytest.raises(ValueError):
        make_user("x", "fax")
