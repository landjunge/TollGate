"""agent_gate: read-only, fake data only."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta, timezone

from tollgate.agent_gate import agent_gate

NOW = datetime(2026, 11, 19, 12, 0, 0).astimezone()
TODAY = NOW.date().isoformat()


def _w(path, obj):
    path.write_text(json.dumps(obj), encoding="utf-8")


def _cfg(d, envs):
    _w(d / "keys_app.json", {"consumer_envelopes": envs})


def _usage(d, consumers, day=TODAY):
    _w(d / "keys_usage.json", {"day": day, "consumers": consumers, "providers": {}, "totals": {}})


def _plan(d, provider="claude", status="exhausted", evidence=NOW - timedelta(minutes=30),
          resets=NOW + timedelta(hours=2), minutes=300):
    iso = lambda t: t.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")  # noqa: E731
    row = {"schema": "tollgate-plan-snapshot-v1", "provider": provider, "limit_status": status,
           "evidence_at": iso(evidence), "observed_at": iso(evidence),
           "windows": [{"window": "5h", "minutes": minutes, "used_percent": 100.0, "resets_at": iso(resets)}]}
    with (d / "plan_status.jsonl").open("a") as h:
        h.write(json.dumps(row) + "\n")


def g(d, consumer="claude"):
    return agent_gate(consumer, user_dir=d, now=NOW)


def test_no_envelope_allows(tmp_path):
    _cfg(tmp_path, {})
    r = g(tmp_path)
    assert (r["decision"], r["limit_source"], r["plan"]) == ("allow", "none", None)
    assert r["day"]["limit_usd"] is None


def test_default_only_never_denies(tmp_path):
    _cfg(tmp_path, {"_default": {"max_usd_day": 0.01}})
    _usage(tmp_path, {"claude": {"calls": 5, "usd": 99.0}})
    r = g(tmp_path)
    assert r["decision"] == "allow" and r["limit_source"] == "none"
    assert agent_gate("_default", user_dir=tmp_path, now=NOW)["decision"] == "allow"


def test_envelope_zero_is_unlimited(tmp_path):
    _cfg(tmp_path, {"claude": {"max_usd_day": 0}})
    _usage(tmp_path, {"claude": {"calls": 5, "usd": 99.0}})
    assert g(tmp_path)["limit_source"] == "none"


def test_spend_below_at_above(tmp_path):
    _cfg(tmp_path, {"claude": {"max_usd_day": 10}})
    out = []
    for usd in (9.99, 10.0, 12.5):
        _usage(tmp_path, {"claude": {"calls": 3, "usd": usd}})
        out.append(g(tmp_path))
    assert [r["decision"] for r in out] == ["allow", "deny", "deny"]
    assert out[0]["reason"] == "within_budget" and out[1]["reason"] == "day_budget_reached"
    assert out[1]["day"] == {"spent_usd": 10.0, "limit_usd": 10.0, "usd_kind": "estimated"}
    assert out[1]["limit_source"] == "user_envelope" and out[1]["valid_until"] > NOW.timestamp()


def test_spend_unknown_allows(tmp_path):
    _cfg(tmp_path, {"claude": {"max_usd_day": 10}})
    _usage(tmp_path, {"claude": {"calls": 7, "usd": 0.0}})  # calls but no usd
    r = g(tmp_path)
    assert (r["decision"], r["reason"], r["day"]["usd_kind"], r["day"]["spent_usd"]) == (
        "allow", "spend_unknown", "unknown", None)
    # no entry, missing ledger, stale day bucket: all unknown, never exceeded
    _usage(tmp_path, {})
    assert g(tmp_path)["reason"] == "spend_unknown"
    _usage(tmp_path, {"claude": {"usd": 50.0}}, day="2026-11-18")
    assert g(tmp_path)["decision"] == "allow"
    (tmp_path / "keys_usage.json").unlink()
    assert g(tmp_path)["reason"] == "spend_unknown"


def test_corrupt_envelope_file_unknown(tmp_path):
    (tmp_path / "keys_app.json").write_text("{not json", encoding="utf-8")
    r = g(tmp_path)
    assert (r["decision"], r["reason"], r["limit_source"]) == ("unknown", "tollgate_unavailable", "unavailable")


def test_corrupt_ledger_unknown(tmp_path):
    _cfg(tmp_path, {"claude": {"max_usd_day": 10}})
    (tmp_path / "keys_usage.json").write_text("garbage", encoding="utf-8")
    assert g(tmp_path)["decision"] == "unknown"
    _w(tmp_path / "keys_usage.json", {"_corrupt": True})
    assert g(tmp_path)["reason"] == "tollgate_unavailable"


def test_plan_exhausted_fresh_never_denies(tmp_path):
    _cfg(tmp_path, {})
    _plan(tmp_path)
    r = g(tmp_path)
    assert r["decision"] == "allow" and r["reason"] == "plan_exhausted_observed"
    assert r["plan"]["limit_status"] == "exhausted" and r["plan"]["fresh"] is True
    assert r["valid_until"] is not None


def test_plan_exhausted_stale(tmp_path):
    _cfg(tmp_path, {})
    _plan(tmp_path, evidence=NOW - timedelta(hours=9), resets=NOW - timedelta(hours=1))
    r = g(tmp_path)
    assert r["plan"]["fresh"] is False and r["reason"] != "plan_exhausted_observed"
    assert r["decision"] == "allow"


def test_plan_older_than_its_window_is_stale(tmp_path):
    _cfg(tmp_path, {})
    _plan(tmp_path, evidence=NOW - timedelta(minutes=90), resets=NOW + timedelta(hours=1), minutes=60)
    assert g(tmp_path)["plan"]["fresh"] is False


def test_plan_other_provider_is_none(tmp_path):
    _cfg(tmp_path, {})
    _plan(tmp_path, provider="grok")
    assert g(tmp_path)["plan"] is None


def test_plan_does_not_override_budget_deny(tmp_path):
    _cfg(tmp_path, {"claude": {"max_usd_day": 1}})
    _usage(tmp_path, {"claude": {"calls": 1, "usd": 2.0}})
    _plan(tmp_path)
    r = g(tmp_path)
    assert r["decision"] == "deny" and r["plan"]["limit_status"] == "exhausted"


def test_missing_files_allow(tmp_path):
    r = g(tmp_path)
    assert r["decision"] == "allow" and r["limit_source"] == "none" and r["plan"] is None


def test_never_raises_and_never_writes(tmp_path):
    _cfg(tmp_path, {"claude": {"max_usd_day": 10}})
    _usage(tmp_path, {"claude": {"calls": 1, "usd": 1.0}})
    _plan(tmp_path)
    before = {p.name: (p.stat().st_mtime_ns, p.read_bytes()) for p in tmp_path.iterdir()}
    time.sleep(0.01)
    for consumer in ("claude", "", "x" * 500, None):
        assert g(tmp_path, consumer)["decision"] in ("allow", "deny", "unknown")
    assert agent_gate("claude", user_dir=tmp_path / "nope", now=NOW)["decision"] == "allow"
    assert agent_gate("claude", user_dir=object(), now="bad")["decision"] == "unknown"
    after = {p.name: (p.stat().st_mtime_ns, p.read_bytes()) for p in tmp_path.iterdir()}
    assert before == after
    assert not (tmp_path / "nope").exists()


def test_default_now_and_epoch_now(tmp_path):
    _cfg(tmp_path, {"claude": {"max_usd_day": 10}})
    assert agent_gate("claude", user_dir=tmp_path)["decision"] == "allow"
    assert agent_gate("claude", user_dir=tmp_path, now=NOW.timestamp())["decision"] == "allow"


def test_two_exhausted_windows_stay_exhausted_until_the_last_resets(tmp_path):
    iso = lambda t: t.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")  # noqa: E731
    evidence = NOW - timedelta(hours=8)  # older than the 6h evidence age
    row = {
        "schema": "tollgate-plan-snapshot-v1", "provider": "claude", "limit_status": "exhausted",
        "evidence_at": iso(evidence), "observed_at": iso(evidence),
        "windows": [
            {"window": "5h", "minutes": 300, "used_percent": 100.0,
             "resets_at": iso(NOW - timedelta(hours=1))},  # the short window already reset
            {"window": "7d", "minutes": 10080, "used_percent": 100.0,
             "resets_at": iso(NOW + timedelta(days=3))},
        ],
    }
    (tmp_path / "plan_status.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
    result = g(tmp_path)
    assert result["plan"]["fresh"] is True
    assert result["reason"] == "plan_exhausted_observed"
    assert result["decision"] == "allow"
    assert result["valid_until"] == (NOW + timedelta(days=3)).timestamp()


def test_default_dir_is_resolved_without_creating_a_portable_directory(tmp_path, monkeypatch):
    from tollgate import paths

    hub = tmp_path / "stick" / "tollgate"
    hub.mkdir(parents=True)
    monkeypatch.delenv("TOLLGATE_HOME", raising=False)
    monkeypatch.delenv("GNOM_WS", raising=False)
    monkeypatch.delenv("TOLLGATE_CONFIG", raising=False)
    monkeypatch.delenv("GNOM_KEYS_CONFIG", raising=False)
    monkeypatch.setattr(paths, "is_portable_mode", lambda root=None: True)
    monkeypatch.setattr(paths, "project_root", lambda: hub)
    before = sorted(p.name for p in hub.parent.iterdir())
    result = agent_gate("claude")
    assert result["decision"] == "unknown" and result["reason"] == "tollgate_unavailable"
    assert sorted(p.name for p in hub.parent.iterdir()) == before


def test_consumer_ids_are_normalized_like_the_ledger(tmp_path):
    _cfg(tmp_path, {"anonymous": {"max_usd_day": 1.0}})
    _usage(tmp_path, {"anonymous": {"requests": 3, "usd": 2.0, "tokens": 0}})
    for label in ("", "   ", "not a valid id!!", "anonymous"):
        assert g(tmp_path, label)["decision"] == "deny", label
