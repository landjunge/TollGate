"""HTTP surface smoke (open mode)."""

from __future__ import annotations


def test_root_and_health(monkeypatch, tmp_path):
    monkeypatch.setenv("TOLLGATE_HOME", str(tmp_path))
    monkeypatch.delenv("TOLLGATE_REQUIRE_AUTH", raising=False)
    (tmp_path / "User").mkdir(parents=True)
    from tollgate import consumers as c

    c.clear_cache()
    # empty consumers → open
    from fastapi.testclient import TestClient
    from tollgate.server_v1 import app

    client = TestClient(app)
    root = client.get("/").json()
    assert root["service"] == "tollgate"
    assert root["repo"] == "https://github.com/landjunge/TollGate"
    assert "https://github.com/landjunge/TollGate" in app.description
    assert "docs/VISION.md" == root["vision"]
    assert "/v1/auth" in root["v1"]

    h = client.get("/v1/health").json()
    assert h["ok"] is True
    assert "portable" in h
    assert h["portable"]["data_home"]
    assert h["auth"]["required"] is False

    r = client.post("/v1/route", json={"intent": "search"})
    assert r.status_code == 200
    assert r.json().get("consumer") in ("anonymous", "anonymous") or "consumer" in r.json()


def test_config_patch_open(monkeypatch, tmp_path):
    monkeypatch.setenv("TOLLGATE_HOME", str(tmp_path))
    monkeypatch.delenv("TOLLGATE_REQUIRE_AUTH", raising=False)
    (tmp_path / "User").mkdir(parents=True)
    from tollgate import consumers as c

    c.clear_cache()
    from fastapi.testclient import TestClient
    from tollgate.server_v1 import app

    client = TestClient(app)
    r = client.post("/v1/config", json={"cost_guard": {"max_usd_day_global": 2.5}})
    assert r.status_code == 200
    assert r.json()["ok"] is True
    g = client.get("/v1/config").json()
    assert g["config"]["cost_guard"]["max_usd_day_global"] == 2.5
