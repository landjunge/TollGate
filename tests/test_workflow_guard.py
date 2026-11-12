"""Synthetic end-to-end tests for the workflow_control + agent_events bridge.

No provider/billing call, no real key, no network, no global process action.
Only isolated temporary journals under ``tmp_path`` are written. Covers the
coordinated integration: replay guard before dispatch, existing budget
admission, and unique job/session/event mapping of usage/stop/unknown.
"""

from __future__ import annotations

from dataclasses import replace

from tollgate.agent_events import AgentEventJournal, EventType, UsageKind
from tollgate.workflow_control import (
    AttemptIdentity,
    Quote,
    WorkflowControl,
    WorkflowScope,
)
from tollgate.workflow_guard import WorkflowGuard, scope_job_id

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
    assert r2["dispatched"] is False
    # Exactly one attributed event for the attempt.
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

    # A fresh (permissive) guard on the same root must honour the recorded DENY.
    g2 = guard(tmp_path)
    g2.control.reserve(identity("b"), QUOTE)
    r2 = g2.dispatch(identity("b"), lambda: sent.append(2))
    assert sent == []
    assert r2["state"] == "GUARD_BLOCKED" and r2["reason"] == "DECISION_DENIED"
    # No false budget release: nothing was spent.
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
    # Repeated stop is idempotent — still one stop event.
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
    # Unknown reservation is held, never released or auto-settled.
    assert g.control.status(SCOPE)["budgets"][0]["reserved"] == 60
    assert g.control.status(SCOPE)["budgets"][0]["spent"] == 0

    # A new attempt in the same job is blocked by the unknown outcome.
    g.control.reserve(identity("b"), QUOTE)
    r2 = g.dispatch(identity("b"), lambda: sent.append(2))
    assert sent == [1]
    assert r2["state"] == "GUARD_BLOCKED" and r2["reason"] == "UNKNOWN_OUTCOME"
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


def test_guard_fails_closed_on_corrupt_event_journal(tmp_path):
    g = setup(tmp_path)
    g.control.reserve(identity("a"), QUOTE)
    path = g.journal._path(scope_job_id(SCOPE))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{bad-json")
    sent = []
    r = g.dispatch(identity("a"), lambda: sent.append(1))
    assert sent == []
    assert r["state"] == "GUARD_BLOCKED" and r["reason"] == "JOURNAL_UNAVAILABLE"


def test_stop_event_uses_scope_level_identity(tmp_path):
    g = setup(tmp_path)
    assert g.stop(SCOPE, "stop-9", stop_reason="budget")["status"] == "EFFECTIVE"
    from tollgate.agent_events import AgentEventRef

    stored = g.journal.get(AgentEventRef(scope_job_id(SCOPE), "scope", "stop-9"))
    assert stored["event_type"] == EventType.STOP.value
    assert stored["decision"] == "DENY"
