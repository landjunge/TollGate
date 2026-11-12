"""
Read-only, minimized workflow observation (projection).

Composes the existing read surfaces — ``WorkflowControl.status`` and the
``AgentEventJournal`` readers — into a single allowlisted observation. This
module never reserves/releases/dispatches/settles/stops and never rewrites a
journal. Only safe fields leave it (ids, states, counters, evidenced refs);
prompts, answers, tool args, keys and free native metadata are never exposed.

Honesty guarantees:

* ``source.authenticated`` is always ``False``; the caller owns the source pin
  (the local journals are otherwise unpinned).
* measured / observed / estimated / unknown usage stay separate, and missing or
  unknown cost is reported as ``None`` — never as ``0``.
* a task id is a workflow task identity, never a provider session; the read
  projection exposes ``attempt_id`` from control status, and ``task_id`` only
  when a caller supplies the session key for a specific attempt.
"""

from __future__ import annotations

from typing import Any

from tollgate.agent_events import AgentEventError, AgentEventJournal, AgentEventRef
from tollgate.workflow_control import WorkflowControl, WorkflowScope
from tollgate.workflow_guard import scope_job_id

__all__ = ["observe_attempt", "observe_workflow"]

_ATTEMPT_FIELDS = (
    "attempt_id",
    "state",
    "reason_code",
    "reserved_microusd",
    "unit",
    "dispatch_started",
)
_BUDGET_FIELDS = (
    "actor_id",
    "consumer_id",
    "limit",
    "spent",
    "reserved",
    "available",
    "cost_kind",
    "incident",
)
_EVENT_FIELDS = (
    "event_type",
    "usage_kind",
    "tokens_in",
    "tokens_out",
    "cost_microusd",
    "decision",
    "stop_reason",
    "evidence_ref",
)
_USAGE_KINDS = ("measured", "observed", "estimated", "unknown")


def _source(authenticated: bool = False) -> dict[str, Any]:
    return {
        "authenticated": authenticated,
        "origin": "local workflow_control.status + agent_events (caller-pinned roots)",
    }


def _project_attempt(attempt: dict[str, Any] | None) -> dict[str, Any]:
    if not attempt:
        return {k: None for k in _ATTEMPT_FIELDS}
    return {k: attempt.get(k) for k in _ATTEMPT_FIELDS}


def _project_budget(budget: dict[str, Any]) -> dict[str, Any]:
    return {k: budget.get(k) for k in _BUDGET_FIELDS}


def _project_usage(summary_usage: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for kind in _USAGE_KINDS:
        u = summary_usage.get(kind) or {}
        events = u.get("events", 0)
        # Missing/unknown cost is never reported as 0.
        cost = u.get("cost_microusd") if (kind != "unknown" and events > 0) else None
        out[kind] = {
            "tokens_in": u.get("tokens_in", 0),
            "tokens_out": u.get("tokens_out", 0),
            "cost_microusd": cost,
            "events": events,
        }
    return out


def _project_event(event: dict[str, Any] | None) -> dict[str, Any]:
    if not event:
        return {k: None for k in _EVENT_FIELDS}
    out = {k: event.get(k) for k in _EVENT_FIELDS}
    # Unknown or missing usage is never reported as a 0 cost.
    if out["usage_kind"] not in ("measured", "observed", "estimated"):
        out["cost_microusd"] = None
    return out


def observe_workflow(
    control: WorkflowControl,
    journal: AgentEventJournal,
    scope: WorkflowScope,
) -> dict[str, Any]:
    """Scope-level read-only observation. Raises (fail-closed) on corrupt journals."""
    job_id = scope_job_id(scope)
    status = control.status(scope)
    summary = journal.summary(job_id)
    return {
        "scope": {"project_id": scope.project_id, "workflow_id": scope.workflow_id},
        "job_id": job_id,
        "source": _source(),
        "stopped": bool(status.get("stopped")),
        "stop_reason": summary.get("stop_reason") or None,
        "attempts": [_project_attempt(a) for a in status.get("attempts") or []],
        "budgets": [_project_budget(b) for b in status.get("budgets") or []],
        "usage": _project_usage(summary.get("usage") or {}),
        "turns": summary.get("turns", 0),
        "runtime_s": summary.get("runtime_s", 0.0),
    }


def observe_attempt(
    control: WorkflowControl,
    journal: AgentEventJournal,
    scope: WorkflowScope,
    task_id: str,
    attempt_id: str,
) -> dict[str, Any]:
    """Attempt-level read-only observation.

    ``task_id`` is a workflow task identity (the event-journal session key), never
    a provider session. Raises (fail-closed) on corrupt journals; a genuinely
    missing event is reported as an empty ``event`` projection.
    """
    job_id = scope_job_id(scope)
    status = control.status(scope)
    attempt = next(
        (a for a in status.get("attempts") or [] if a.get("attempt_id") == attempt_id),
        None,
    )
    try:
        event = journal.get(AgentEventRef(job_id, task_id, attempt_id))
    except AgentEventError as exc:
        if exc.code == "EVENT_NOT_FOUND":
            event = None
        else:
            raise  # corrupt/unavailable journal fails closed

    return {
        "scope": {"project_id": scope.project_id, "workflow_id": scope.workflow_id},
        "job_id": job_id,
        "source": _source(),
        "task_id": task_id,  # workflow task, never a provider session
        "attempt_id": attempt_id,
        "control": _project_attempt(attempt),
        "event": _project_event(event),
    }
