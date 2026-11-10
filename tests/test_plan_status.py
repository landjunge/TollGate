"""Read-only pilot snapshots for Codex, Claude and Grok — fixtures only, no network."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from tollgate.provider_ops import plan_status as ps

NOW = datetime(2026, 11, 10, 8, 35, tzinfo=timezone.utc)


def _jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return path


def test_codex_rpc_exhausted_weekly_window_without_raw_account_id():
    answer = {"id": 2, "result": {
        "ordinaryUsageAllowed": False, "accountId": "raw-account-id",
        "rateLimits": {"limitId": "codex", "planType": "prolite",
                       "primary": {"usedPercent": 100, "windowDurationMins": 10080,
                                   "resetsAt": 1794430015},
                       "secondary": None, "credits": {"hasCredits": False},
                       "rateLimitReachedType": "rate_limit_reached"}}}
    sent = []

    def runner(payload):
        sent.append(payload)
        return ["{}", json.dumps(answer)]

    snap = ps.codex_rpc(runner=runner, now=NOW)
    methods = [json.loads(line).get("method") for line in sent[0].splitlines()]
    assert methods == ["initialize", "initialized", "account/rateLimits/read"]
    assert snap["plan"] == {"name": "prolite", "confidence": "confirmed"}
    assert snap["windows"][0]["window"] == "7d"
    assert snap["windows"][0]["resets_at"] == "2026-11-11T20:46:55Z"
    assert snap["limit_status"] == "exhausted"
    assert snap["absolute_quota"] == "unknown"
    assert "raw-account-id" not in json.dumps(snap)
    assert snap["account_ref"].startswith("codex:acct-")
    assert ps.forecast(snap, NOW)["forecast"] == "no"
    # after the reset an old reading says nothing about the new window
    assert ps.forecast(snap, datetime(2026, 11, 11, 21, tzinfo=timezone.utc))["forecast"] == "unknown"


def test_codex_rpc_without_answer_is_unknown():
    snap = ps.codex_rpc(runner=lambda _p: [], now=NOW)
    assert snap["limit_status"] == "unknown"
    assert ps.forecast(snap, NOW) == {"forecast": "unknown", "basis": "unknown"}


def test_codex_session_log_snapshot(tmp_path):
    rate = {"limit_id": "codex", "plan_type": "prolite", "rate_limit_reached_type": None,
            "primary": {"used_percent": 99.0, "window_minutes": 10080, "resets_at": 1794430015}}
    _jsonl(tmp_path / "2026/11/08/rollout.jsonl", [
        {"timestamp": "2026-11-08T00:19:24Z", "type": "event_msg",
         "payload": {"type": "token_count", "rate_limits": rate}},
        {"timestamp": "2026-11-08T00:20:00Z", "type": "response_item", "payload": {}},
    ])
    snap = ps.codex_log_latest(tmp_path, now=NOW)
    assert snap["limit_status"] == "tight"
    assert snap["windows"][0]["used_percent"] == 99.0
    assert ps.forecast(snap, datetime(2026, 11, 8, 1, tzinfo=timezone.utc))["forecast"] == "tight"
    # two days later the reading is stale, not "still fits"
    assert ps.forecast(snap, NOW)["forecast"] == "unknown"


def test_claude_statusline_input():
    snap = ps.claude_statusline({
        "model": {"id": "claude-opus-5-5"},
        "rate_limits": {"five_hour": {"used_percentage": 42.5, "resets_at": 1794298200},
                        "seven_day": {"used_percentage": 12, "resets_at": 1794700000}}}, now=NOW)
    assert [w["window"] for w in snap["windows"]] == ["5h", "7d"]
    assert snap["model"] == "claude-opus-5-5"
    assert snap["limit_status"] == "available"
    empty = ps.claude_statusline({"model": {"id": "x"}}, now=NOW)
    assert empty["limit_status"] == "unknown" and empty["notes"]


def test_claude_cache_reads_plan_without_identity(tmp_path):
    path = tmp_path / "claude.json"
    path.write_text(json.dumps({
        "oauthAccount": {"accountUuid": "uuid-1", "emailAddress": "someone@example.org",
                         "organizationType": "claude_pro", "billingType": "stripe_subscription"},
        "cachedUsageUtilization": {"fetchedAtMs": 1794097665590, "utilization": {
            "five_hour": {"utilization": 23, "resets_at": "2026-11-08T04:40:00+00:00"},
            "seven_day": {"utilization": 14, "resets_at": "2026-11-08T18:00:00+00:00"}}},
        "unusedLimitResetStatusCache": {"holdsUnusedReset": True}}))
    snap = ps.claude_cache(path, now=NOW)
    text = json.dumps(snap)
    assert "someone@example.org" not in text and "uuid-1" not in text
    assert snap["plan"] == {"name": "claude_pro", "confidence": "confirmed"}
    assert snap["evidence_at"].startswith("2026-11-08T00:27")
    assert ps.forecast(snap, NOW)["forecast"] == "unknown"  # both windows reset long ago


def test_parse_claude_limit_message():
    at = datetime(2026, 11, 10, 4, 32, 17, tzinfo=timezone.utc)
    parsed = ps.parse_claude_limit("You've hit your 5-hour limit · resets 8:10am (Europe/Berlin)", at)
    assert parsed["window"] == "5h"
    assert parsed["resets_at"] == datetime(2026, 11, 10, 7, 10, tzinfo=timezone.utc)
    late = ps.parse_claude_limit("You've hit your 5-hour limit · resets 10:10pm (Europe/Berlin)",
                                 datetime(2026, 11, 8, 17, 13, tzinfo=timezone.utc))
    assert late["resets_at"] == datetime(2026, 11, 8, 21, 10, tzinfo=timezone.utc)
    assert ps.parse_claude_limit("all good", at) is None


def test_claude_log_evaluation_against_real_shaped_outcomes(tmp_path):
    def answer(ts, model="claude-opus-5-5"):
        return {"type": "assistant", "timestamp": ts, "message": {"model": model, "content": []}}

    limit = {"type": "assistant", "timestamp": "2026-11-10T04:32:17Z", "isApiErrorMessage": True,
             "error": "rate_limit", "message": {"model": "<synthetic>", "content": [
                 {"type": "text", "text": "You've hit your 5-hour limit · resets 8:10am (Europe/Berlin)"}]}}
    again = dict(limit, timestamp="2026-11-10T04:32:19Z")
    _jsonl(tmp_path / "p/s.jsonl", [answer("2026-11-10T04:32:16Z"), limit, again,
                                    answer("2026-11-10T07:52:56Z")])
    since = datetime(2026, 11, 10, tzinfo=timezone.utc)
    result = ps.evaluate(ps.claude_log_events(tmp_path, since=since, now=NOW))
    # first answer and first limit had no earlier reading; after that the block is
    # confirmed, and after the reset a new job is expected to fit (estimated)
    assert result["counts"] == {"no_data": 2, "correct_block": 1, "correct_fit": 1}


def test_grok_log_forecast_misses_the_last_two_percent(tmp_path):
    def billing(ts, pct):
        return {"ts": ts, "msg": "billing: fetched credits config", "ctx": {
            "subscriptionTier": "SuperGrok", "config": {
                "creditUsagePercent": pct, "prepaidBalance": {"val": 0},
                "currentPeriod": {"type": "USAGE_PERIOD_TYPE_WEEKLY",
                                  "start": "2026-11-03T20:47:10Z", "end": "2026-11-10T20:47:10Z"}}}}

    path = _jsonl(tmp_path / "unified.jsonl", [
        {"ts": "2026-11-07T10:00:00Z", "msg": "auth init user_info check", "ctx": {"user_id": "u-1"}},
        billing("2026-11-07T16:25:05Z", 90.0),
        {"ts": "2026-11-07T16:30:00Z", "msg": "shell.turn.inference_done", "ctx": {}},
        billing("2026-11-07T17:24:57Z", 98.0),
        {"ts": "2026-11-07T17:26:35Z", "msg": "shell.turn.inference_failed",
         "ctx": {"status_code": 402, "message": "Grok Build usage balance exhausted"}},
        billing("2026-11-07T17:27:04Z", 100.0),
        {"ts": "2026-11-07T17:30:00Z", "msg": "shell.turn.inference_failed", "ctx": {"status_code": 402}},
    ])
    events = list(ps.grok_log_events(path, now=NOW))
    snap = [s for s, _ in events if s][-1]
    assert snap["plan"]["name"] == "SuperGrok"
    assert snap["windows"][0]["window"] == "7d"
    assert "u-1" not in json.dumps(snap)
    result = ps.evaluate(events)
    assert result["counts"] == {"correct_fit": 1, "warned_limit": 1, "correct_block": 1}


def test_append_log_writes_jsonl(tmp_path):
    rows = [ps.codex_rpc(runner=lambda _p: [], now=NOW)]
    path = ps.append_log(rows, tmp_path / "log" / "plan_status.jsonl")
    ps.append_log(rows, path)
    lines = path.read_text().splitlines()
    assert len(lines) == 2 and json.loads(lines[0])["schema"] == ps.SCHEMA


def test_stale_age_parameter():
    snap = ps.snapshot("grok", source="s", source_kind="cli_log", evidence_at=NOW,
                       windows=[ps._window("7d", 10080, 50, NOW + timedelta(days=1))], now=NOW)
    assert ps.forecast(snap, NOW + timedelta(hours=1))["forecast"] == "fits"
    assert ps.forecast(snap, NOW + timedelta(hours=7))["forecast"] == "unknown"
