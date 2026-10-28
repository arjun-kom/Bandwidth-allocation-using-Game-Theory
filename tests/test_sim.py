import pytest

from sim import Simulation, list_scenarios


def test_all_scenarios_load():
    ids = {s["id"] for s in list_scenarios()}
    assert {"light_load", "peak_hour", "heavy_user_joins", "selfish_user", "priority_traffic"} <= ids


@pytest.mark.parametrize("scenario", ["light_load", "heavy_user_joins", "selfish_user"])
def test_scenarios_run_and_respect_capacity(scenario):
    hist = Simulation(scenario, "nash_bargaining").run()
    assert len(hist) > 0
    for h in hist:
        assert sum(u["rate"] for u in h["users"]) <= h["capacity"] + 1e-3


def test_events_fire():
    sim = Simulation("heavy_user_joins", "max_min")
    hist = sim.run()
    assert any("joined" in e for e in hist[15]["events"])
    assert len(hist[16]["users"]) == len(hist[14]["users"]) + 1


def test_runs_are_reproducible():
    a = Simulation("peak_hour", "max_min").run()
    b = Simulation("peak_hour", "max_min").run()
    assert [h["metrics"] for h in a] == [h["metrics"] for h in b]


def test_live_controls():
    sim = Simulation("light_load", "nash_bargaining")
    sim.step()
    u = sim.add_user("download", weight=2)
    sim.capacity = 10
    rec = sim.step()
    assert any(x["id"] == u.id for x in rec["users"])
    sim.remove_user(u.id)
    assert all(x["id"] != u.id for x in sim.step()["users"])
