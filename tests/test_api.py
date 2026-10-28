import os
import tempfile

os.environ.setdefault("BWA_DB", os.path.join(tempfile.mkdtemp(), "runs.db"))

from fastapi.testclient import TestClient  # noqa: E402

from api.main import app  # noqa: E402

client = TestClient(app)
USERS = [{"id": "v", "type": "video"}, {"id": "w", "type": "web"}, {"id": "d", "type": "download"}]


def test_health_and_meta():
    assert client.get("/api/health").json() == {"status": "ok"}
    meta = client.get("/api/meta").json()
    assert "nash_bargaining" in meta["mechanisms"] and "video" in meta["user_types"]
    assert len(meta["scenarios"]) == 5


def test_allocate():
    r = client.post("/api/allocate", json={"capacity": 10, "mechanism": "nash_bargaining", "users": USERS})
    assert r.status_code == 200
    rates = r.json()["allocation"]["rates"]
    assert abs(sum(rates.values()) - 10) < 1e-3


def test_compare_has_every_mechanism():
    r = client.post("/api/compare", json={"capacity": 10, "users": USERS}).json()
    assert set(r["results"]) == {"nash_bargaining", "kelly", "weighted_priority", "max_min", "equal_share"}


def test_bad_requests():
    assert client.post("/api/allocate", json={"capacity": 10, "mechanism": "x", "users": USERS}).status_code == 422
    assert client.post("/api/allocate", json={"capacity": -1, "users": USERS}).status_code == 422
    dup = [{"id": "a", "type": "web"}, {"id": "a", "type": "web"}]
    assert client.post("/api/compare", json={"capacity": 10, "users": dup}).status_code == 422
    assert client.post("/api/compare", json={"capacity": 10, "users": [{"id": "a", "type": "fax"}]}).status_code == 422


def test_websocket_simulation_and_run_log():
    with client.websocket_connect("/ws/simulate") as ws:
        ws.send_json({"type": "start", "scenario": "light_load", "mechanism": "max_min", "speed": 20})
        assert ws.receive_json()["type"] == "started"
        first = ws.receive_json()
        assert first["type"] == "tick" and first["record"]["tick"] == 0
        ws.send_json({"type": "add_user", "user_type": "download", "weight": 2})
        ws.send_json({"type": "set_capacity", "capacity": 20})
        ws.send_json({"type": "bogus"})
        seen_error, seen_new = False, False
        for _ in range(40):
            m = ws.receive_json()
            if m["type"] == "error":
                seen_error = True
            if m["type"] == "tick" and any(u["id"] == "download-1" for u in m["record"]["users"]):
                seen_new = True
                assert m["record"]["capacity"] == 20
            if m["type"] == "done":
                break
        assert seen_error and seen_new
        assert m["type"] == "done" and m["run_id"]
    runs = client.get("/api/runs").json()
    assert runs and runs[0]["scenario"] == "light_load"
    assert client.get(f"/api/runs/{runs[0]['id']}").json()["ticks"] == 30


def test_experiments_endpoint_reports_state():
    r = client.get("/api/experiments").json()
    assert "running" in r and "charts" in r
