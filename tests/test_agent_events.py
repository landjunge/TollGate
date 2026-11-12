"""Synthetic adapter tests for structured agent events.

No provider calls, no real keys, no network. Only isolated temporary journals
under ``tmp_path`` are written. Covers the TollGate board ``dd26e513fd3f``
requirements: idempotent prompt/usage/stop mapping, the measured / observed /
estimated / unknown split, and fail-closed handling of unknown outcomes, DENY
decisions and committed stops so they never trigger a duplicate or a new paid
start. ``start_guard`` is a replay/attribution guard, never a budget grant.
"""

from __future__ import annotations

import json

import pytest

from tollgate.agent_events import (
    AgentEvent,
    AgentEventError,
    AgentEventJournal,
    AgentEventRef,
    EventType,
    UsageKind,
)


def _usage(
    job="job-1",
    session="session-1",
    event="usage-1",
    kind=UsageKind.MEASURED,
    **changes,
):
    kw = dict(
        job_id=job,
        session_id=session,
        event_id=event,
        event_type=EventType.USAGE,
        usage_kind=kind,
        tokens_in=10,
        tokens_out=20,
        cost_microusd=5,
        turns=1,
        runtime_s=1.5,
    )
    kw.update(changes)
    return AgentEvent(**kw)


def _stop(job="job-1", session="session-1", event="stop-1", **changes):
    kw = dict(
        job_id=job,
        session_id=session,
        event_id=event,
        event_type=EventType.STOP,
        usage_kind=UsageKind.UNKNOWN,
        decision="DENY",
        stop_reason="operator-stop",
    )
    kw.update(changes)
    return AgentEvent(**kw)


def test_record_is_idempotent_and_no_duplicate(tmp_path):
    journal = AgentEventJournal(root=tmp_path)
    event = _usage()
    first = journal.record(event)
    second = journal.record(event)
    assert first["tokens_in"] == second["tokens_in"] == 10
    assert first["cost_microusd"] == second["cost_microusd"] == 5
    assert first["deduplicated"] is False and second["deduplicated"] is True
    assert journal.summary("job-1")["events"] == 1
    # Repeating does not bump the durable sequence.
    path = journal._path("job-1")
    before = json.loads(path.read_text())
    journal.record(event)
    after = json.loads(path.read_text())
    assert after["seq"] == before["seq"]
    assert len(after["events"]["session-1"]) == 1


def test_changed_content_same_identity_is_conflict(tmp_path):
    journal = AgentEventJournal(root=tmp_path)
    journal.record(_usage())
    with pytest.raises(AgentEventError, match="IDEMPOTENCY_CONFLICT"):
        journal.record(_usage(tokens_in=99))


def test_same_event_id_in_different_session_or_job_is_distinct(tmp_path):
    journal = AgentEventJournal(root=tmp_path)
    journal.record(_usage())
    journal.record(_usage(session="session-2"))
    journal.record(_usage(job="job-2"))
    assert journal.summary("job-1")["events"] == 2
    assert journal.summary("job-2")["events"] == 1


def test_measured_observed_estimated_unknown_stay_separate(tmp_path):
    journal = AgentEventJournal(root=tmp_path)
    journal.record(_usage(event="m", kind=UsageKind.MEASURED, cost_microusd=10))
    journal.record(_usage(event="o", kind=UsageKind.OBSERVED, cost_microusd=12))
    journal.record(_usage(event="e", kind=UsageKind.ESTIMATED, cost_microusd=7))
    journal.record(_usage(event="u", kind=UsageKind.UNKNOWN, cost_microusd=0))
    usage = journal.summary("job-1")["usage"]
    assert usage["measured"]["cost_microusd"] == 10
    assert usage["observed"]["cost_microusd"] == 12
    assert usage["estimated"]["cost_microusd"] == 7
    assert usage["unknown"]["cost_microusd"] == 0
    # Unknown never leaks into measured/spent totals.
    assert usage["measured"]["tokens_in"] == 10
    assert usage["unknown"]["tokens_in"] == 10


def test_unknown_usage_blocks_new_start_and_does_not_count_as_measured(tmp_path):
    journal = AgentEventJournal(root=tmp_path)
    journal.record(_usage(event="m", kind=UsageKind.MEASURED))
    assert journal.start_guard("job-1")["blocked"] is False
    journal.record(_usage(event="u", kind=UsageKind.UNKNOWN))
    gate = journal.start_guard("job-1")
    assert gate["blocked"] is True and gate["reason"] == "UNKNOWN_OUTCOME"
    # The unknown event is recorded exactly once and is not a paid start.
    assert journal.summary("job-1")["events"] == 2
    assert journal.summary("job-1")["usage"]["measured"]["events"] == 1
    assert journal.summary("job-1")["usage"]["unknown"]["events"] == 1


def test_prompt_event_alone_does_not_block_start(tmp_path):
    journal = AgentEventJournal(root=tmp_path)
    journal.record(
        AgentEvent(
            job_id="job-1",
            session_id="session-1",
            event_id="prompt-1",
            event_type=EventType.PROMPT,
            usage_kind=UsageKind.UNKNOWN,
        )
    )
    assert journal.start_guard("job-1")["blocked"] is False
    assert journal.summary("job-1")["events"] == 1


def test_stop_blocks_start_durably_and_is_idempotent(tmp_path):
    journal = AgentEventJournal(root=tmp_path)
    stop = _stop()
    assert journal.record(stop)["deduplicated"] is False
    assert journal.record(stop)["deduplicated"] is True
    gate = journal.start_guard("job-1")
    assert gate["blocked"] is True and gate["reason"] == "WORKFLOW_STOPPED"
    summary = journal.summary("job-1")
    assert summary["stopped"] is True and summary["stop_reason"] == "operator-stop"
    assert summary["events"] == 1
    # A fresh instance still sees the durable barrier.
    assert AgentEventJournal(root=tmp_path).start_guard("job-1")["blocked"] is True


def test_stop_with_unknown_kind_is_still_a_committed_stop_not_an_unknown(tmp_path):
    journal = AgentEventJournal(root=tmp_path)
    journal.record(
        _stop(usage_kind=UsageKind.UNKNOWN, decision="DENY", stop_reason="budget")
    )
    gate = journal.start_guard("job-1")
    # Stop takes precedence: it is a committed barrier, not a lingering unknown.
    assert gate["reason"] == "WORKFLOW_STOPPED"


def test_deny_budget_decision_blocks_start(tmp_path):
    journal = AgentEventJournal(root=tmp_path)
    journal.record(_usage(event="d", decision="DENY"))
    gate = journal.start_guard("job-1")
    assert gate["blocked"] is True and gate["reason"] == "DECISION_DENIED"


def test_budget_decisions_are_recorded_and_kept_separate(tmp_path):
    journal = AgentEventJournal(root=tmp_path)
    journal.record(_usage(event="a", decision="ALLOW"))
    journal.record(_usage(event="b", decision="ALLOW"))
    journal.record(_usage(event="c", decision="DENY"))
    decisions = journal.summary("job-1")["decisions"]
    assert decisions == {"ALLOW": 2, "DENY": 1}


def test_turns_and_runtime_accumulate_from_usage_and_tool_events(tmp_path):
    journal = AgentEventJournal(root=tmp_path)
    journal.record(_usage(event="u1", turns=2, runtime_s=1.0))
    journal.record(
        AgentEvent(
            job_id="job-1",
            session_id="session-1",
            event_id="t1",
            event_type=EventType.TOOL,
            usage_kind=UsageKind.MEASURED,
            turns=3,
            runtime_s=0.5,
        )
    )
    summary = journal.summary("job-1")
    assert summary["turns"] == 5
    assert summary["runtime_s"] == 1.5


def test_cross_instance_consistency(tmp_path):
    a = AgentEventJournal(root=tmp_path)
    a.record(_usage(event="m"))
    b = AgentEventJournal(root=tmp_path)
    assert b.get(AgentEventRef("job-1", "session-1", "m"))["tokens_in"] == 10
    assert b.summary("job-1")["events"] == 1


def test_get_missing_event_fails_closed(tmp_path):
    journal = AgentEventJournal(root=tmp_path)
    with pytest.raises(AgentEventError, match="EVENT_NOT_FOUND"):
        journal.get(AgentEventRef("job-1", "session-1", "missing"))


@pytest.mark.parametrize("field", ["job_id", "session_id", "event_id"])
def test_invalid_identity_fails_closed(tmp_path, field):
    bad = {"job_id": "job-1", "session_id": "session-1", "event_id": "usage-1"}
    bad[field] = "sp ace"
    with pytest.raises(AgentEventError, match="INVALID_ID"):
        _usage(**bad)


@pytest.mark.parametrize("amount", [True, 1.5, -1, 10**16, "10"])
def test_money_strict_integer_and_bounded(tmp_path, amount):
    with pytest.raises(AgentEventError, match="INVALID_AMOUNT"):
        _usage(cost_microusd=amount)


def test_invalid_decision_and_unknown_enum_fail_closed(tmp_path):
    with pytest.raises(AgentEventError, match="INVALID_DECISION"):
        _usage(decision="MAYBE")
    with pytest.raises(AgentEventError, match="INVALID_KIND"):
        AgentEvent(
            job_id="j",
            session_id="s",
            event_id="e",
            event_type=EventType.USAGE,
            usage_kind="wat",
        )


def test_corrupt_and_duplicate_key_journals_fail_closed(tmp_path):
    journal = AgentEventJournal(root=tmp_path)
    journal.record(_usage())
    path = journal._path("job-1")
    original = path.read_bytes()
    path.write_text("{bad-json")
    with pytest.raises(AgentEventError, match="JOURNAL_UNAVAILABLE"):
        journal.summary("job-1")
    path.write_bytes(original)
    text = path.read_text().replace('"seq":1', '"seq":0,"seq":1')
    path.write_text(text)
    with pytest.raises(AgentEventError, match="JOURNAL_UNAVAILABLE"):
        journal.summary("job-1")


def test_tampered_identity_in_journal_fails_closed(tmp_path):
    journal = AgentEventJournal(root=tmp_path)
    journal.record(_usage())
    path = journal._path("job-1")
    data = json.loads(path.read_text())
    # Swap the persisted job_id under a still-valid session/event key path.
    data["events"]["session-1"]["usage-1"]["job_id"] = "other-job"
    path.write_text(json.dumps(data))
    with pytest.raises(AgentEventError, match="JOURNAL_UNAVAILABLE"):
        journal.summary("job-1")


@pytest.mark.parametrize(
    "field,value",
    [
        ("tokens_in", "10"),
        ("tokens_in", True),
        ("tokens_in", 1.5),
        ("tokens_out", None),
        ("cost_microusd", 1.5),
        ("turns", False),
        ("runtime_s", "1.5"),
        ("decision", 1),
    ],
)
def test_tampered_non_integer_stored_values_fail_closed(tmp_path, field, value):
    journal = AgentEventJournal(root=tmp_path)
    journal.record(_usage())
    path = journal._path("job-1")
    data = json.loads(path.read_text())
    data["events"]["session-1"]["usage-1"][field] = value
    path.write_text(json.dumps(data))
    with pytest.raises(AgentEventError, match="JOURNAL_UNAVAILABLE"):
        journal.summary("job-1")


@pytest.mark.parametrize("field", ["tokens_in", "event_type", "usage_kind", "job_id"])
def test_tampered_missing_required_field_fails_closed(tmp_path, field):
    journal = AgentEventJournal(root=tmp_path)
    journal.record(_usage())
    path = journal._path("job-1")
    data = json.loads(path.read_text())
    del data["events"]["session-1"]["usage-1"][field]
    path.write_text(json.dumps(data))
    with pytest.raises(AgentEventError, match="JOURNAL_UNAVAILABLE"):
        journal.summary("job-1")


def test_byte_budget_rejects_oversized_write_and_preserves_old_journal(
    tmp_path, monkeypatch
):
    import tollgate.agent_events as module

    journal = AgentEventJournal(root=tmp_path)
    journal.record(_usage(event="small"))
    path = journal._path("job-1")
    before = path.read_bytes()
    # Limit just above the current size: a big Unicode label must be rejected,
    # and the already-persisted journal must stay untouched.
    monkeypatch.setattr(module, "MAX_JOURNAL_BYTES", len(before) + 100)
    big = _stop(stop_reason="界" * 100, evidence_ref="🙂" * 80)
    with pytest.raises(AgentEventError, match="JOURNAL_SIZE"):
        journal.record(big)
    assert path.read_bytes() == before
    assert journal.summary("job-1")["events"] == 1


def test_unicode_labels_round_trip_as_utf8(tmp_path):
    journal = AgentEventJournal(root=tmp_path)
    journal.record(
        _stop(stop_reason="Haushalt überschritten – 🙁", evidence_ref="Ref/Konto-ß")
    )
    out = journal.get(AgentEventRef("job-1", "session-1", "stop-1"))
    assert out["stop_reason"] == "Haushalt überschritten – 🙁"
    assert out["evidence_ref"] == "Ref/Konto-ß"
    assert journal.summary("job-1")["stop_reason"] == "Haushalt überschritten – 🙁"


def test_journal_file_permissions_and_no_secret_leak(tmp_path):
    journal = AgentEventJournal(root=tmp_path)
    journal.record(_usage(evidence_ref="provider-bill-42"))
    path = journal._path("job-1")
    assert path.stat().st_mode & 0o777 == 0o600
    assert (path.parent.stat().st_mode & 0o777) == 0o700
    audit = (tmp_path / "User" / "audit.jsonl").read_text(encoding="utf-8")
    assert "provider-bill-42" not in audit  # evidence refs stay out of the ops trail
    # No prompt/content/secret field is persisted in the journal.
    assert "content" not in path.read_text()


def test_summary_is_never_a_budget_grant(tmp_path):
    journal = AgentEventJournal(root=tmp_path)
    journal.record(_usage(event="m", decision="ALLOW"))
    summary = journal.summary("job-1")
    gate = journal.start_guard("job-1")
    assert summary["budget_authorized"] is False
    assert gate["budget_authorized"] is False
    assert gate["blocked"] is False  # attribution is clean, but not a grant


def test_capacity_is_enforced(tmp_path, monkeypatch):
    import tollgate.agent_events as module

    monkeypatch.setattr(module, "MAX_EVENTS_PER_JOB", 2)
    journal = AgentEventJournal(root=tmp_path)
    journal.record(_usage(event="a"))
    journal.record(_usage(event="b"))
    with pytest.raises(AgentEventError, match="JOURNAL_CAPACITY"):
        journal.record(_usage(event="c"))


def test_authority_emit_is_off_by_default_under_pytest(tmp_path, monkeypatch):
    # G4 emit must never run by default: a reader/writer never writes side files.
    monkeypatch.setenv("TOLLGATE_AUTHORITY_EVENTS", "1")
    monkeypatch.setenv("TOLLGATE_AUTHORITY_EVENTS_PATH", str(tmp_path / "auth.jsonl"))
    journal = AgentEventJournal(root=tmp_path)
    journal.record(_stop())
    assert not (tmp_path / "auth.jsonl").exists()
