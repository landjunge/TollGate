"""
Bind structured agent events to the existing workflow_control dispatch path.

``workflow_control`` already owns budget admission, reservations, the durable
stop barrier and attempt-level replay protection. ``agent_events`` owns the
structured (job_id/session_id/event_id) attribution with the measured / observed /
estimated / unknown split. This module composes both — it adds **no** second
budget ledger, queue or process controller:

* ``WorkflowGuard.dispatch`` runs ``AgentEventJournal.start_guard`` (a replay /
  stop / deny / unknown guard) **before** the existing ``WorkflowControl.dispatch``
  (which still performs real budget admission), then records exactly one outcome
  event keyed by job/session/event.
* ``WorkflowGuard.stop`` commits the existing ``WorkflowControl.stop`` barrier and
  records a durable ``stop`` event.

Identity mapping (unique, deterministic):

* ``job_id``    ← ``scope_job_id(scope)`` (sha256 of the frozen scope, valid id)
* ``session_id``← ``AttemptIdentity.task_id``
* ``event_id``  ← ``AttemptIdentity.attempt_id``

Unknown/timeout outcomes are recorded as ``usage_kind=UNKNOWN`` and then block any
further dispatch for the same job (no invisible replay, no automatic new paid
start). This module never calls ``settle``, never releases a reservation and never
makes a provider/billing call; it only observes and attributes.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from typing import Any, Callable

from tollgate.agent_events import (
    AgentEvent,
    AgentEventError,
    AgentEventJournal,
    EventType,
    UsageKind,
)
from tollgate.workflow_control import AttemptIdentity, WorkflowControl, WorkflowScope

__all__ = ["WorkflowGuard", "scope_job_id"]

# Reserved session for scope-level events (stop barriers). Task ids are caller
# provided, so this label is documented as reserved for the guard.
_SCOPE_SESSION = "scope"


def scope_job_id(scope: WorkflowScope) -> str:
    """Canonical, unambiguous ``job_id`` for a frozen workflow scope.

    The scope fields allow ``:``/``.``, so plain concatenation would be ambiguous;
    the sha256 digest (64 lowercase hex) is a valid ``agent_events`` id and keeps
    the mapping stable across processes.
    """
    raw = json.dumps(asdict(scope), sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(raw).hexdigest()


def _event_keys(identity: AttemptIdentity) -> dict[str, str]:
    return {
        "job_id": scope_job_id(identity.scope),
        "session_id": identity.task_id,
        "event_id": identity.attempt_id,
    }


class WorkflowGuard:
    """Replay guard in front of ``WorkflowControl.dispatch`` + event attribution."""

    def __init__(self, control: WorkflowControl, journal: AgentEventJournal) -> None:
        self.control = control
        self.journal = journal

    def dispatch(
        self,
        identity: AttemptIdentity,
        send: Callable[[], Any],
        *,
        usage_kind: UsageKind = UsageKind.OBSERVED,
        tokens_in: int = 0,
        tokens_out: int = 0,
        cost_microusd: int = 0,
        turns: int = 0,
        runtime_s: float = 0.0,
        evidence_ref: str = "",
    ) -> dict[str, Any]:
        """Replay guard before dispatch, then existing admission + dispatch.

        Requires a prior ``self.control.reserve(identity, quote)`` (unchanged).
        The returned ``send`` callback is invoked at most once; repeats of the
        same attempt, committed stops, DENY decisions and unresolved unknown
        outcomes never re-dispatch.
        """
        keys = _event_keys(identity)
        guard = self._start_guard(keys["job_id"])
        if guard["blocked"]:
            return {
                "ok": False,
                "dispatched": False,
                "state": "GUARD_BLOCKED",
                "outcome": "GUARD_BLOCKED",
                "reason": guard["reason"],
                "protection": "replay_guard",
                "attempt_id": identity.attempt_id,
            }

        # Track actual invocation and whether the callback raised: workflow_control
        # projects both DISPATCH_ATTEMPTED and OUTCOME_UNKNOWN to "OUTCOME_UNKNOWN",
        # so the guard must distinguish them itself.
        called: dict[str, bool] = {"sent": False, "raised": False}

        def _send() -> Any:
            called["sent"] = True
            try:
                return send()
            except BaseException:
                called["raised"] = True
                raise

        result = self.control.dispatch(identity, _send)
        state = str(result.get("state") or "")
        self._record_outcome(
            keys,
            state,
            result,
            raised=called["raised"],
            usage_kind=usage_kind,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_microusd=cost_microusd,
            turns=turns,
            runtime_s=runtime_s,
            evidence_ref=evidence_ref,
        )
        if state in ("DENIED", "CANCELLED_NO_SEND"):
            outcome = "DENIED"
        elif called["raised"]:
            outcome = "UNKNOWN"
        else:
            outcome = "SENT"
        return {
            "ok": True,
            "dispatched": called["sent"] and not called["raised"],
            "state": state,
            "outcome": outcome,
            "reason_code": result.get("reason_code"),
            "attempt": result,
            "attempt_id": identity.attempt_id,
        }

    def stop(
        self,
        scope: WorkflowScope,
        stop_id: str,
        *,
        stop_reason: str = "",
        session_id: str = _SCOPE_SESSION,
    ) -> dict[str, Any]:
        """Commit the existing durable stop barrier and record a ``stop`` event.

        Only a confirmed ``EFFECTIVE`` barrier is recorded; ``PENDING`` is not a
        committed stop and is returned unchanged.
        """
        result = self.control.stop(scope, stop_id)
        if result.get("status") == "EFFECTIVE":
            self.journal.record(
                AgentEvent(
                    job_id=scope_job_id(scope),
                    session_id=session_id,
                    event_id=stop_id,
                    event_type=EventType.STOP,
                    usage_kind=UsageKind.UNKNOWN,
                    decision="DENY",
                    stop_reason=stop_reason or stop_id,
                )
            )
        return result

    def _start_guard(self, job_id: str) -> dict[str, Any]:
        """Fail-closed guard: an unreadable/corrupt journal blocks dispatch."""
        try:
            return self.journal.start_guard(job_id)
        except AgentEventError as exc:
            return {
                "blocked": True,
                "reason": exc.code,
                "stopped": False,
                "stop_reason": "",
                "budget_authorized": False,
            }

    def _record_outcome(
        self,
        keys: dict[str, str],
        state: str,
        result: dict[str, Any],
        *,
        raised: bool,
        usage_kind: UsageKind,
        tokens_in: int,
        tokens_out: int,
        cost_microusd: int,
        turns: int,
        runtime_s: float,
        evidence_ref: str,
    ) -> None:
        if state in ("DENIED", "CANCELLED_NO_SEND"):
            self.journal.record(
                AgentEvent(
                    **keys,
                    event_type=EventType.USAGE,
                    usage_kind=UsageKind.UNKNOWN,
                    decision="DENY",
                    stop_reason=str(result.get("reason_code") or ""),
                )
            )
        elif raised:
            self.journal.record(
                AgentEvent(
                    **keys,
                    event_type=EventType.USAGE,
                    usage_kind=UsageKind.UNKNOWN,
                )
            )
        else:
            self.journal.record(
                AgentEvent(
                    **keys,
                    event_type=EventType.USAGE,
                    usage_kind=usage_kind,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    cost_microusd=cost_microusd,
                    turns=turns,
                    runtime_s=runtime_s,
                    decision="ALLOW",
                    evidence_ref=evidence_ref,
                )
            )
