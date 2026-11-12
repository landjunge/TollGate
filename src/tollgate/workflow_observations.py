"""
Read-only, minimized workflow observation (projection).

Composes the existing read surfaces — ``WorkflowControl.status`` and the
``AgentEventJournal`` readers — into a single allowlisted observation. This
module never reserves/releases/dispatches/settles/stops and never rewrites a
journal. Only safe fields leave it (ids, states, counters); prompts, answers,
tool args, keys and free native metadata are never exposed. ``stop_reason`` is
omitted entirely, ``evidence_ref`` is reduced to a presence flag, and an attempt
``reason_code`` is mapped through a strict allowlist (unknown codes are reported
as ``unknown``, never as injected free text). Budget ``incident`` values are
exported only as strict booleans; other types become ``None`` (unknown).

Honesty guarantees:

* ``source.authenticated`` is always ``False``; the caller owns the source pin
  (the local journals are otherwise unpinned).
* measured / observed / estimated / unknown usage stay separate, and missing or
  unknown cost is reported as ``None`` — never as ``0``.
* a task id is a workflow task identity, never a provider session.
* control state and the event journal are read from independent journals and are
  reported unlinked (the control projection omits task id, so no task/actor
  binding check is possible read-only); no cross-attribution is asserted.
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
)
_USAGE_KINDS = ("measured", "observed", "estimated", "unknown")

# Strict allowlist of the reason codes ``workflow_control`` can persist. A
# manipulated journal could otherwise smuggle free text (prompts/tokens/keys)
# through this field, which Control._validate does not constrain.
_KNOWN_REASON_CODES = frozenset(
    {
        "OK",
        "WORKFLOW_STOPPED",
        "ACCOUNTING_MISMATCH",
        "BUDGET_EXCEEDED",
        "UNBOUNDED_COST",
        "ADMISSION_DENIED",
        "DAY_LIMIT_DENIED",
        "AWAITING_FINAL_EVIDENCE",
        "OUTCOME_UNKNOWN",
        "PROCESS_START_UNKNOWN",
        "PROCESS_SPAWN_OBSERVED",
    }
)


def _safe_reason_code(code: Any) -> str:
    if isinstance(code, str) and code in _KNOWN_REASON_CODES:
        return code
    return "unknown"


def _source(authenticated: bool = False) -> dict[str, Any]:
    return {
        "authenticated": authenticated,
        "origin": "local workflow_control.status + agent_events (caller-pinned roots)",
    }


def _project_attempt(attempt: dict[str, Any] | None) -> dict[str, Any]:
    if not attempt:
        return {k: None for k in _ATTEMPT_FIELDS}
    out = {k: attempt.get(k) for k in _ATTEMPT_FIELDS}
    out["reason_code"] = _safe_reason_code(attempt.get("reason_code"))
    return out


def _project_budget(budget: dict[str, Any]) -> dict[str, Any]:
    out = {k: budget.get(k) for k in _BUDGET_FIELDS}
    incident = budget.get("incident")
    out["incident"] = incident if type(incident) is bool else None
    return out


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
    out: dict[str, Any] = {k: None for k in _EVENT_FIELDS}
    out["has_evidence_ref"] = False
    if not event:
        return out
    for k in _EVENT_FIELDS:
        out[k] = event.get(k)
    # Unknown or missing usage is never reported as a 0 cost.
    if out["usage_kind"] not in ("measured", "observed", "estimated"):
        out["cost_microusd"] = None
    # Free-text evidence_ref is never exported; only its presence.
    out["has_evidence_ref"] = bool(event.get("evidence_ref"))
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
    """Attempt-level read-only observation, control and event reported unlinked.

    ``task_id`` is the event-journal session key (a workflow task), never a
    provider session. The control attempt (keyed by ``attempt_id``) and the event
    (keyed by ``task_id`` + ``attempt_id``) come from independent journals and
    are **not** cross-verified: the control projection omits ``task_id``, so no
    task/actor binding check is performed here and no cross-attribution is
    asserted. Raises (fail-closed) on corrupt journals; a genuinely missing event
    is reported as an empty ``event`` projection.
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
        "attempt_id": attempt_id,
        "task_id": task_id,  # workflow task, never a provider session
        "control": _project_attempt(attempt),
        "event": _project_event(event),
        "note": (
            "control and event are read from independent journals and are not "
            "cross-verified; control status omits task_id, so no task/actor "
            "binding check is performed here."
        ),
    }
