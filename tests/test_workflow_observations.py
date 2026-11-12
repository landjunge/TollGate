"""Focused read-only observation tests (isolated temp journals, dummy callbacks)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tollgate.agent_events import AgentEventError, AgentEventJournal, UsageKind
from tollgate.workflow_control import (
    AttemptIdentity,
    ControlError,
    Quote,
    WorkflowControl,
    WorkflowScope,
)
from tollgate.workflow_guard import WorkflowGuard, scope_job_id
from tollgate.workflow_observations import observe_attempt, observe_workflow

SCOPE = WorkflowScope("project-a", "workflow-a")
QUOTE = Quote("dummy-v1", "dummy", "bounded-send", "local-dummy", 60, "fixed-v1")


def identity(n="a", **changes):
    return replace(
        AttemptIdentity(SCOPE, "task:1", "codex", "codex-lane", n, "a" * 64), **changes
    )


def setup(root, amount=400):
    control = WorkflowControl(
        root=root,
        admission=lambda *_: True,
        registered_quotes={QUOTE.adapter_id: QUOTE},
    )
    journal = AgentEventJournal(root=root)
    guard = WorkflowGuard(control, journal)
    control.configure_budget(SCOPE, "codex", "codex-lane", amount)
    return control, journal, guard


def _flatten_keys(obj, prefix=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _flatten_keys(v, f"{prefix}.{k}" if prefix else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _flatten_keys(v, f"{prefix}[{i}]")
    else:
        yield prefix


def test_observe_is_read_only_and_journals_unchanged(tmp_path):
    control, journal, guard = setup(tmp_path)
    control.reserve(identity("a"), QUOTE)
    guard.dispatch(identity("a"), lambda: None)
    cpath = control._path(SCOPE)
    jpath = journal._path(scope_job_id(SCOPE))
    before_c, before_j = cpath.read_bytes(), jpath.read_bytes()

    observe_workflow(control, journal, SCOPE)
    observe_attempt(control, journal, SCOPE, "task:1", "a")

    assert cpath.read_bytes() == before_c
    assert jpath.read_bytes() == before_j


def test_observe_reflects_unknown_stop_and_settlement(tmp_path):
    control, journal, guard = setup(tmp_path)
    control.reserve(identity("a"), QUOTE)

    def flaky():
        raise TimeoutError("synthetic")

    r = guard.dispatch(identity("a"), flaky)
    assert r["outcome"] == "UNKNOWN"

    obs = observe_workflow(control, journal, SCOPE)
    assert obs["source"]["authenticated"] is False
    assert obs["stopped"] is False
    assert [a["attempt_id"] for a in obs["attempts"]] == ["a"]
    assert obs["attempts"][0]["state"] == "OUTCOME_UNKNOWN"
    assert obs["usage"]["unknown"]["events"] == 1
    assert obs["usage"]["unknown"]["cost_microusd"] is None  # never 0
    assert obs["usage"]["measured"]["cost_microusd"] is None  # missing, never 0

    # settlement after evidence reconciles; observation reflects it
    control.settle(identity("a"), 40, "bill-1", "receipt-1")
    assert (
        observe_workflow(control, journal, SCOPE)["attempts"][0]["state"] == "SETTLED"
    )

    # a committed stop is visible
    guard.stop(SCOPE, "stop-1", stop_reason="operator")
    stopped = observe_workflow(control, journal, SCOPE)
    assert stopped["stopped"] is True and stopped["stop_reason"] == "operator"


def test_observe_attempt_maps_event_and_task_id(tmp_path):
    control, journal, guard = setup(tmp_path)
    control.reserve(identity("a"), QUOTE)
    guard.dispatch(
        identity("a"),
        lambda: None,
        usage_kind=UsageKind.MEASURED,
        tokens_in=10,
        tokens_out=20,
        cost_microusd=5,
        evidence_ref="receipt-1",
    )
    obs = observe_attempt(control, journal, SCOPE, "task:1", "a")
    assert obs["task_id"] == "task:1"  # workflow task, never a provider session
    assert "provider_session" not in obs and "session" not in obs
    assert obs["attempt_id"] == "a"
    assert obs["control"]["state"] == "OUTCOME_UNKNOWN"  # projected dispatch state
    assert obs["event"]["event_type"] == "usage"
    assert obs["event"]["usage_kind"] == "measured"
    assert obs["event"]["tokens_in"] == 10 and obs["event"]["cost_microusd"] == 5
    assert obs["event"]["evidence_ref"] == "receipt-1"


def test_observe_attempt_missing_event_is_empty_projection(tmp_path):
    control, journal, guard = setup(tmp_path)
    control.reserve(identity("a"), QUOTE)
    obs = observe_attempt(control, journal, SCOPE, "task:1", "a")
    assert obs["event"]["event_type"] is None
    assert obs["event"]["cost_microusd"] is None
    assert obs["event"]["evidence_ref"] is None


def test_observe_missing_scope_returns_empty(tmp_path):
    control, journal, _guard = setup(tmp_path)
    other = WorkflowScope("project-a", "never-created")
    obs = observe_workflow(control, journal, other)
    assert obs["stopped"] is False
    assert obs["attempts"] == [] and obs["budgets"] == []


def test_corrupt_control_journal_fails_closed(tmp_path):
    control, journal, _guard = setup(tmp_path)
    control.reserve(identity("a"), QUOTE)
    control._path(SCOPE).write_text("{bad-json")
    with pytest.raises(ControlError):
        observe_workflow(control, journal, SCOPE)


def test_corrupt_and_truncated_event_journal_fail_closed(tmp_path):
    control, journal, _guard = setup(tmp_path)
    control.reserve(identity("a"), QUOTE)
    path = journal._path(scope_job_id(SCOPE))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{bad-json")
    with pytest.raises(AgentEventError):
        observe_workflow(control, journal, SCOPE)

    path.write_text('{"schema": 1, "job_id": "trunc')
    with pytest.raises(AgentEventError):
        observe_workflow(control, journal, SCOPE)


def test_no_secret_fields_in_observation(tmp_path):
    control, journal, guard = setup(tmp_path)
    control.reserve(identity("a"), QUOTE)
    guard.dispatch(identity("a"), lambda: None, evidence_ref="provider-bill-42")
    guard.stop(SCOPE, "stop-1", stop_reason="operator")

    obs = observe_workflow(control, journal, SCOPE)
    obs.update(observe_attempt(control, journal, SCOPE, "task:1", "a"))

    keys = list(_flatten_keys(obs))
    # token counts (tokens_in/out) are allowlisted integers; only secret-shaped
    # fields must be absent.
    for bad in ("api_key", "secret", "content", "prompt", "message", "request_hash"):
        assert not any(bad in k.lower() for k in keys), bad
    # evidenced refs are allowlisted, but nothing else leaks.
    assert obs["event"]["evidence_ref"] == "provider-bill-42"
    assert obs["event"]["stop_reason"] in (None, "")


def test_missing_cost_never_zero(tmp_path):
    control, journal, guard = setup(tmp_path)
    control.reserve(identity("a"), QUOTE)

    def flaky():
        raise TimeoutError("synthetic")

    guard.dispatch(identity("a"), flaky)
    obs = observe_workflow(control, journal, SCOPE)
    for kind in ("measured", "observed", "estimated", "unknown"):
        if obs["usage"][kind]["events"] == 0 or kind == "unknown":
            assert obs["usage"][kind]["cost_microusd"] is None
    attempt = observe_attempt(control, journal, SCOPE, "task:1", "a")
    assert attempt["event"]["cost_microusd"] is None  # unknown outcome, never 0
