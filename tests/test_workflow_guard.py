"""Synthetic end-to-end tests for the workflow_control + agent_events bridge.

No provider/billing call, no real key, no network, no global process action.
Only isolated temporary journals under ``tmp_path`` are written. Covers the
coordinated integration: serialized replay guard before dispatch, existing
budget admission, unique job/session/event mapping of usage/stop/unknown, and
crash/replay/write-failure/namespace/deny-reconstruction/settle regressions.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest

from tollgate.agent_events import (
    AgentEventError,
    AgentEventJournal,
    AgentEventRef,
    EventType,
    UsageKind,
)
from tollgate.workflow_control import (
    AttemptIdentity,
    Quote,
    WorkflowControl,
    WorkflowScope,
)
from tollgate.workflow_guard import WorkflowGuard, _stop_event_id, scope_job_id

SCOPE = WorkflowScope("project-a", "workflow-a")
QUOTE = Quote("dummy-v1", "dummy", "bounded-send", "local-dummy", 60, "fixed-v1")


def identity(n="a", **changes):
    return replace(
        AttemptIdentity(SCOPE, "task:1", "codex", "codex-lane", n, "a" * 64), **changes
    )


def guard(root, *, admission=None):
    control = WorkflowControl(
        root=root,
        admission=admission if admission is not None else (lambda *_: True),
        registered_quotes={QUOTE.adapter_id: QUOTE},
    )
    journal = AgentEventJournal(root=root)
    return WorkflowGuard(control, journal)


def setup(root, amount=100):
    g = guard(root)
    g.control.configure_budget(SCOPE, "codex", "codex-lane", amount)
    return g


def test_scope_job_id_is_stable_and_distinct():
    a = scope_job_id(WorkflowScope("p", "w"))
    b = scope_job_id(WorkflowScope("p", "w"))
    c = scope_job_id(WorkflowScope("p", "w2"))
    d = scope_job_id(WorkflowScope("p2", "w"))
    assert a == b
    assert a != c and a != d
    assert len(a) == 64 and set(a) <= set("0123456789abcdef")


def test_e2e_duplicate_attempt_no_second_dispatch(tmp_path):
    g = setup(tmp_path)
    g.control.reserve(identity("a"), QUOTE)
    sent = []
    r1 = g.dispatch(identity("a"), lambda: sent.append(1))
    r2 = g.dispatch(identity("a"), lambda: sent.append(2))
    assert sent == [1]  # second dispatch never sends
    assert r1["dispatched"] is True and r1["outcome"] == "SENT"
    assert r2["dispatched"] is False and r2["outcome"] == "REPLAYED"
    assert g.journal.summary(scope_job_id(SCOPE))["events"] == 1


def test_e2e_deny_blocks_subsequent_dispatch_and_never_releases(tmp_path):
    flag = {"allow": True}
    g = guard(tmp_path, admission=lambda *_: flag["allow"])
    g.control.configure_budget(SCOPE, "codex", "codex-lane", 100)
    g.control.reserve(identity("a"), QUOTE)  # admission allows at reserve
    flag["allow"] = False
    sent = []
    r1 = g.dispatch(identity("a"), lambda: sent.append(1))
    assert sent == [] and r1["outcome"] == "DENIED"
    assert r1["state"] == "CANCELLED_NO_SEND"
    assert r1["reason_code"] == "ADMISSION_DENIED"

    g2 = guard(tmp_path)
    g2.control.reserve(identity("b"), QUOTE)
    r2 = g2.dispatch(identity("b"), lambda: sent.append(2))
    assert sent == []
    assert r2["state"] == "GUARD_BLOCKED" and r2["reason"] == "DECISION_DENIED"
    assert g2.control.status(SCOPE)["budgets"][0]["spent"] == 0


def test_e2e_stop_blocks_dispatch_and_is_recorded(tmp_path):
    g = setup(tmp_path)
    g.control.reserve(identity("a"), QUOTE)
    assert g.stop(SCOPE, "stop-1", stop_reason="operator")["status"] == "EFFECTIVE"
    sent = []
    r = g.dispatch(identity("a"), lambda: sent.append(1))
    assert sent == []
    assert r["state"] == "GUARD_BLOCKED" and r["reason"] == "WORKFLOW_STOPPED"
    summary = g.journal.summary(scope_job_id(SCOPE))
    assert summary["stopped"] is True and summary["stop_reason"] == "operator"
    g.stop(SCOPE, "stop-1", stop_reason="operator")
    assert g.journal.summary(scope_job_id(SCOPE))["events"] == 1


def test_e2e_timeout_unknown_blocks_second_dispatch_and_keeps_reservation(tmp_path):
    g = setup(tmp_path, 200)
    g.control.reserve(identity("a"), QUOTE)
    sent = []

    def flaky():
        sent.append(1)
        raise TimeoutError("synthetic")

    r1 = g.dispatch(identity("a"), flaky)
    assert sent == [1] and r1["outcome"] == "UNKNOWN"
    assert g.control.status(SCOPE)["budgets"][0]["reserved"] == 60
    assert g.control.status(SCOPE)["budgets"][0]["spent"] == 0

    g.control.reserve(identity("b"), QUOTE)
    r2 = g.dispatch(identity("b"), lambda: sent.append(2))
    assert sent == [1]
    assert r2["state"] == "GUARD_BLOCKED" and r2["reason"] == "UNRESOLVED_UNKNOWN"
    assert g.control.status(SCOPE)["budgets"][0]["reserved"] == 120
    assert g.control.status(SCOPE)["budgets"][0]["spent"] == 0


def test_e2e_success_records_measured_usage_attribution(tmp_path):
    g = setup(tmp_path)
    g.control.reserve(identity("a"), QUOTE)
    sent = []
    r = g.dispatch(
        identity("a"),
        lambda: sent.append(1),
        usage_kind=UsageKind.MEASURED,
        tokens_in=10,
        tokens_out=20,
        cost_microusd=5,
        turns=1,
        runtime_s=1.5,
    )
    assert sent == [1] and r["outcome"] == "SENT" and r["dispatched"] is True
    usage = g.journal.summary(scope_job_id(SCOPE))["usage"]
    assert usage["measured"]["tokens_in"] == 10
    assert usage["measured"]["tokens_out"] == 20
    assert usage["measured"]["cost_microusd"] == 5
    assert usage["observed"]["events"] == 0


def test_guard_fails_closed_on_corrupt_control_journal(tmp_path):
    g = setup(tmp_path)
    g.control.reserve(identity("a"), QUOTE)
    g.control._path(SCOPE).write_text("{bad-json")
    sent = []
    r = g.dispatch(identity("a"), lambda: sent.append(1))
    assert sent == []
    assert r["state"] == "GUARD_BLOCKED" and r["reason"] == "JOURNAL_UNAVAILABLE"


def test_corrupt_event_journal_does_not_block_dispatch(tmp_path):
    g = setup(tmp_path)
    g.control.reserve(identity("a"), QUOTE)
    path = g.journal._path(scope_job_id(SCOPE))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{bad-json")
    sent = []
    r = g.dispatch(identity("a"), lambda: sent.append(1))
    assert sent == [1] and r["outcome"] == "SENT"
    assert r["recorded"] is False and r["record_error"] == "JOURNAL_UNAVAILABLE"


def test_stop_event_uses_scope_level_identity(tmp_path):
    g = setup(tmp_path)
    assert g.stop(SCOPE, "stop-9", stop_reason="budget")["status"] == "EFFECTIVE"
    stored = g.journal.get(
        AgentEventRef(scope_job_id(SCOPE), "tollgate-scope", _stop_event_id("stop-9"))
    )
    assert stored["event_type"] == EventType.STOP.value
    assert stored["decision"] == "DENY"


def test_replay_unknown_returns_unknown_not_sent(tmp_path):
    g = setup(tmp_path, 200)
    g.control.reserve(identity("a"), QUOTE)
    sent = []

    def flaky():
        sent.append(1)
        raise TimeoutError("synthetic")

    r1 = g.dispatch(identity("a"), flaky)
    assert r1["outcome"] == "UNKNOWN"
    r2 = g.dispatch(identity("a"), lambda: sent.append(2))
    assert sent == [1]
    assert r2["dispatched"] is False and r2["outcome"] == "REPLAYED"
    assert r2["outcome"] != "SENT"
    usage = g.journal.summary(scope_job_id(SCOPE))["usage"]
    assert usage["measured"]["events"] == 0 and usage["observed"]["events"] == 0


def test_replay_with_different_usage_args_returns_stored_result(tmp_path):
    g = setup(tmp_path)
    g.control.reserve(identity("a"), QUOTE)
    sent = []
    g.dispatch(
        identity("a"),
        lambda: sent.append(1),
        usage_kind=UsageKind.MEASURED,
        tokens_in=10,
    )
    r2 = g.dispatch(
        identity("a"),
        lambda: sent.append(2),
        usage_kind=UsageKind.MEASURED,
        tokens_in=999,
    )
    assert sent == [1]
    assert r2["outcome"] == "REPLAYED"
    assert (
        g.journal.summary(scope_job_id(SCOPE))["usage"]["measured"]["tokens_in"] == 10
    )


def test_crash_after_control_marker_blocks_new_attempt(tmp_path):
    g = setup(tmp_path)
    g.control.reserve(identity("a"), QUOTE)
    with g.control._transaction(SCOPE) as (path, data):
        data["attempts"]["a"]["state"] = "DISPATCH_ATTEMPTED"
        data["attempts"]["a"]["reason_code"] = "AWAITING_FINAL_EVIDENCE"
        g.control._commit(path, data)

    g2 = guard(tmp_path)
    g2.control.reserve(identity("b"), QUOTE)
    sent = []
    r = g2.dispatch(identity("b"), lambda: sent.append(1))
    assert sent == []
    assert r["state"] == "GUARD_BLOCKED" and r["reason"] == "UNRESOLVED_UNKNOWN"


def test_lost_deny_reconstructed_from_control(tmp_path):
    g = setup(tmp_path)
    g.control.reserve(identity("a"), QUOTE)
    with g.control._transaction(SCOPE) as (path, data):
        data["attempts"]["a"]["state"] = "CANCELLED_NO_SEND"
        data["attempts"]["a"]["reason_code"] = "ADMISSION_DENIED"
        data["attempts"]["a"]["held"] = 0
        g.control._commit(path, data)

    g2 = guard(tmp_path)
    g2.control.reserve(identity("b"), QUOTE)
    sent = []
    r = g2.dispatch(identity("b"), lambda: sent.append(1))
    assert sent == []
    assert r["state"] == "GUARD_BLOCKED" and r["reason"] == "DECISION_DENIED"


def test_event_lock_timeout_after_send_is_recorded_false_not_busy(
    tmp_path, monkeypatch
):
    g = setup(tmp_path)
    g.control.reserve(identity("a"), QUOTE)
    sent = []

    def slow_record(event):
        raise TimeoutError("journal lock timeout")

    monkeypatch.setattr(g.journal, "record", slow_record)
    r = g.dispatch(identity("a"), lambda: sent.append(1))
    assert sent == [1]
    assert r["outcome"] == "SENT" and r["dispatched"] is True
    assert r["recorded"] is False and r["record_error"] == "EVENT_WRITE_FAILED"


def test_stop_event_timeout_after_barrier_is_still_effective(tmp_path, monkeypatch):
    g = setup(tmp_path)
    g.control.reserve(identity("a"), QUOTE)

    def slow_record(event):
        raise TimeoutError("journal lock timeout")

    monkeypatch.setattr(g.journal, "record", slow_record)
    result = g.stop(SCOPE, "stop-1", stop_reason="op")
    assert result["status"] == "EFFECTIVE"  # barrier committed, not PENDING
    assert g.control.status(SCOPE)["stopped"] is True


def test_guard_serializes_check_and_send_against_concurrent_dispatch(tmp_path):
    g = setup(tmp_path, 400)
    g.control.reserve(identity("a"), QUOTE)
    g.control.reserve(identity("b"), QUOTE)
    sent = []
    entered = threading.Event()
    release = threading.Event()

    def slow_unknown():
        entered.set()
        assert release.wait(3)
        raise TimeoutError("synthetic")

    with ThreadPoolExecutor(2) as pool:
        f_a = pool.submit(g.dispatch, identity("a"), slow_unknown)
        assert entered.wait(2)
        f_b = pool.submit(g.dispatch, identity("b"), lambda: sent.append("b"))
        release.set()
        r_a = f_a.result(5)
        r_b = f_b.result(5)

    assert r_a["outcome"] == "UNKNOWN"
    assert r_b["state"] == "GUARD_BLOCKED"
    assert r_b["reason"] == "UNRESOLVED_UNKNOWN"
    assert sent == []


@pytest.mark.parametrize(
    "bad",
    [
        {"tokens_in": -1},
        {"cost_microusd": 1.5},
        {"turns": False},
        {"runtime_s": float("nan")},
        {"usage_kind": "wat"},
    ],
)
def test_invalid_usage_args_fail_before_dispatch(tmp_path, bad):
    g = setup(tmp_path)
    g.control.reserve(identity("a"), QUOTE)
    sent = []
    with pytest.raises(AgentEventError):
        g.dispatch(identity("a"), lambda: sent.append(1), **bad)
    assert sent == []  # failed before any send


@pytest.mark.parametrize(
    "task,attempt",
    [("tollgate-scope", "a"), ("task:1", "stop:foo")],
)
def test_reserved_namespace_rejected_before_effect(tmp_path, task, attempt):
    g = setup(tmp_path)
    ident = identity("a", task_id=task, attempt_id=attempt)
    g.control.reserve(ident, QUOTE)
    sent = []
    with pytest.raises(AgentEventError, match="RESERVED_IDENTITY"):
        g.dispatch(ident, lambda: sent.append(1))
    assert sent == []


def test_long_stop_id_is_hash_mapped_and_valid(tmp_path):
    g = setup(tmp_path)
    long_id = "x" * 128
    assert g.stop(SCOPE, long_id, stop_reason="op")["status"] == "EFFECTIVE"
    stored = g.journal.get(
        AgentEventRef(scope_job_id(SCOPE), "tollgate-scope", _stop_event_id(long_id))
    )
    assert stored["event_type"] == EventType.STOP.value
    assert stored["stop_reason"] == "op"


def test_invalid_stop_reason_fails_before_barrier(tmp_path):
    g = setup(tmp_path)
    with pytest.raises(AgentEventError):
        g.stop(SCOPE, "stop-1", stop_reason="x" * 201)
    assert g.control.status(SCOPE)["stopped"] is False  # barrier not committed


def test_settle_reconciles_unknown_and_unblocks(tmp_path):
    g = setup(tmp_path, 400)
    g.control.reserve(identity("a"), QUOTE)
    sent = []

    def flaky():
        sent.append(1)
        raise TimeoutError("synthetic")

    r = g.dispatch(identity("a"), flaky)
    assert r["outcome"] == "UNKNOWN"
    # Evidence-bound reconcile: settle transitions the control state to SETTLED.
    g.control.settle(identity("a"), 40, "bill-1", "receipt-1")
    g.control.reserve(identity("b"), QUOTE)
    r2 = g.dispatch(identity("b"), lambda: sent.append(2))
    assert r2["outcome"] == "SENT" and sent == [1, 2]


def test_replay_after_missing_write_reports_missing(tmp_path, monkeypatch):
    g = setup(tmp_path)
    g.control.reserve(identity("a"), QUOTE)
    sent = []

    def fail_record(event):
        raise AgentEventError("EVENT_WRITE_FAILED")

    monkeypatch.setattr(g.journal, "record", fail_record)
    r1 = g.dispatch(identity("a"), lambda: sent.append(1))
    assert r1["outcome"] == "SENT" and r1["recorded"] is False

    r2 = g.dispatch(identity("a"), lambda: sent.append(2))
    assert sent == [1]
    assert r2["outcome"] == "REPLAYED" and r2["recorded"] is False
    assert r2["record_error"] == "EVENT_NOT_FOUND"


def test_replay_read_lock_timeout_preserves_stored_attempt(tmp_path, monkeypatch):
    g = setup(tmp_path)
    g.control.reserve(identity("a"), QUOTE)
    sent = []
    r1 = g.dispatch(identity("a"), lambda: sent.append(1))
    assert r1["outcome"] == "SENT" and sent == [1]

    def get_timeout(ref):
        raise TimeoutError("event journal lock timeout")

    monkeypatch.setattr(g.journal, "get", get_timeout)
    r2 = g.dispatch(identity("a"), lambda: sent.append(2))
    assert sent == [1]  # no second callback
    assert r2["outcome"] == "REPLAYED"
    assert r2["state"] == "OUTCOME_UNKNOWN"  # stored control state preserved
    assert r2["attempt"]["attempt_id"] == "a"
    assert r2["recorded"] is False and r2["record_error"] == "EVENT_READ_FAILED"


def test_replay_read_oserror_preserves_stored_attempt(tmp_path, monkeypatch):
    g = setup(tmp_path)
    g.control.reserve(identity("a"), QUOTE)
    sent = []
    g.dispatch(identity("a"), lambda: sent.append(1))

    def get_oserror(ref):
        raise OSError("event journal read error")

    monkeypatch.setattr(g.journal, "get", get_oserror)
    r2 = g.dispatch(identity("a"), lambda: sent.append(2))
    assert sent == [1]
    assert r2["outcome"] == "REPLAYED"
    assert r2["recorded"] is False and r2["record_error"] == "EVENT_READ_FAILED"


def test_stop_uses_actual_id_and_is_idempotent(tmp_path):
    g = setup(tmp_path)
    g.stop(SCOPE, "stop-1", stop_reason="op")
    result = g.stop(SCOPE, "stop-2", stop_reason="op")
    assert result["status"] == "EFFECTIVE" and result["stop_id"] == "stop-1"
    assert g.journal.summary(scope_job_id(SCOPE))["events"] == 1
    stored = g.journal.get(
        AgentEventRef(scope_job_id(SCOPE), "tollgate-scope", _stop_event_id("stop-1"))
    )
    assert stored["event_type"] == EventType.STOP.value
