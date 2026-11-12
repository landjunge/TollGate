"""
Bind structured agent events to the existing workflow_control dispatch path.

``workflow_control`` already owns budget admission, reservations, the durable
stop barrier and attempt-level replay protection. ``agent_events`` owns the
structured (job_id/session_id/event_id) attribution with the measured / observed /
estimated / unknown split. This module composes both — it adds **no** second
budget ledger, queue or process controller:

* ``WorkflowGuard.dispatch`` checks the replay/stop/deny/unknown guard and calls
  the existing ``WorkflowControl.dispatch`` (real budget admission) **under one
  per-job guard lock**, so the guard decision and the send are serialized against
  other guard dispatches of the same job.
* ``WorkflowGuard.stop`` commits the existing stop barrier and records a durable
  ``stop`` event.

The guard is derived **only** from the authoritative control journal, so it is
independent of a lost attribution write: an attempt left in ``DISPATCH_ATTEMPTED``
/ ``OUTCOME_UNKNOWN`` blocks new attempts (``UNRESOLVED_UNKNOWN``), a denied
attempt (``DENIED``/``CANCELLED_NO_SEND``) is reconstructed as a job-wide deny
(``DECISION_DENIED``), and a committed stop blocks (``WORKFLOW_STOPPED``). The
only way out of ``UNRESOLVED_UNKNOWN`` is the existing evidence-bound
``WorkflowControl.settle``, which transitions the control state to ``SETTLED``;
this module never settles, releases a reservation or reclassifies an event.

Attribution writes are best-effort and happen **after** the effect: an event
write failure is reported as ``recorded=False`` with a safe error code and never
turns an executed send into ``GUARD_BUSY``/``dispatched=False``.

Identity mapping (unique, deterministic):

* ``job_id``    ← ``scope_job_id(scope)`` (sha256 of the frozen scope, valid id)
* ``session_id``← ``AttemptIdentity.task_id`` (attempts) / reserved ``tollgate-scope`` (stop)
* ``event_id``  ← ``AttemptIdentity.attempt_id`` (attempts) / ``stop:<sha256(stop_id)>``

The session label ``tollgate-scope`` and the ``stop:`` event prefix are reserved:
a task id of exactly ``tollgate-scope`` or an attempt id beginning with ``stop:``
is rejected before any effect (``RESERVED_IDENTITY``).
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
    AgentEventRef,
    EventType,
    UsageKind,
)
from tollgate.filelock import FileLock
from tollgate.workflow_control import (
    AttemptIdentity,
    ControlError,
    WorkflowControl,
    WorkflowScope,
)

__all__ = ["WorkflowGuard", "scope_job_id"]

# Reserved session for scope-level events (stop barriers). Task ids are caller
# provided, so this label is documented as reserved and never reused for attempts.
_SCOPE_SESSION = "tollgate-scope"
_STOP_PREFIX = "stop:"


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
    # Reject the reserved scope/stop namespaces before any effect, so an attempt
    # can never collide with a stop event and the error is never swallowed later.
    if identity.task_id == _SCOPE_SESSION:
        raise AgentEventError("RESERVED_IDENTITY")
    if identity.attempt_id.startswith(_STOP_PREFIX):
        raise AgentEventError("RESERVED_IDENTITY")
    return {
        "job_id": scope_job_id(identity.scope),
        "session_id": identity.task_id,
        "event_id": identity.attempt_id,
    }


def _stop_event_id(actual_stop_id: str) -> str:
    """Valid, collision-free event id for a stop barrier (hash of the real id)."""
    return _STOP_PREFIX + hashlib.sha256(actual_stop_id.encode("utf-8")).hexdigest()


class WorkflowGuard:
    """Replay guard in front of ``WorkflowControl.dispatch`` + event attribution."""

    def __init__(
        self,
        control: WorkflowControl,
        journal: AgentEventJournal,
        *,
        lock_timeout_s: float = 1.0,
    ) -> None:
        self.control = control
        self.journal = journal
        self.lock_timeout_s = lock_timeout_s

    def _guard_lock_path(self, job_id: str) -> Any:
        return self.journal.directory / f"{job_id}.guard.lock"

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
        The guard decision and the send are serialized under a per-job lock, and
        the guard derives the authoritative state from the control journal, so a
        concurrent or crashed attempt cannot slip past an unknown/stop/deny.
        """
        keys = _event_keys(identity)
        job_id = keys["job_id"]

        # Validate usage arguments before any effect (fail before send, not after).
        success_event = AgentEvent(
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

        called: dict[str, bool] = {"sent": False, "raised": False}

        def _send() -> Any:
            called["sent"] = True
            try:
                return send()
            except BaseException:
                called["raised"] = True
                raise

        try:
            with FileLock(self._guard_lock_path(job_id), timeout_s=self.lock_timeout_s):
                reason = self._guard_check(identity)
                if reason:
                    return {
                        "ok": False,
                        "dispatched": False,
                        "state": "GUARD_BLOCKED",
                        "outcome": "GUARD_BLOCKED",
                        "reason": reason,
                        "protection": "replay_guard",
                        "attempt_id": identity.attempt_id,
                    }

                result = self.control.dispatch(identity, _send)
                state = str(result.get("state") or "")

                if called["sent"]:
                    if called["raised"]:
                        outcome = "UNKNOWN"
                        event = AgentEvent(
                            **keys,
                            event_type=EventType.USAGE,
                            usage_kind=UsageKind.UNKNOWN,
                        )
                    else:
                        outcome = "SENT"
                        event = success_event
                    recorded, rec_error = self._safe_record(event)
                elif state in ("DENIED", "CANCELLED_NO_SEND"):
                    outcome = "DENIED"
                    recorded, rec_error = self._safe_record(
                        AgentEvent(
                            **keys,
                            event_type=EventType.USAGE,
                            usage_kind=UsageKind.UNKNOWN,
                            decision="DENY",
                            stop_reason=str(result.get("reason_code") or ""),
                        )
                    )
                else:
                    # Replay: no callback ran. Never fabricate SENT/ALLOW; report
                    # whether the prior attribution is actually present.
                    outcome = "REPLAYED"
                    recorded = self._has_event(keys)
                    rec_error = "" if recorded else "EVENT_MISSING"

                return {
                    "ok": True,
                    "dispatched": called["sent"] and not called["raised"],
                    "state": state,
                    "outcome": outcome,
                    "reason_code": result.get("reason_code"),
                    "recorded": recorded,
                    "record_error": rec_error,
                    "attempt": result,
                    "attempt_id": identity.attempt_id,
                }
        except TimeoutError:
            # Only the guard-lock acquisition can reach here (before any effect).
            return {
                "ok": False,
                "dispatched": False,
                "state": "GUARD_BUSY",
                "outcome": "GUARD_BUSY",
                "reason": "GUARD_LOCK_TIMEOUT",
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

        Uses the control's actual persisted stop id (mapped to a valid hash event
        id) so a repeat stop is idempotent. Deterministic metadata is validated
        before the barrier effect. Only an ``EFFECTIVE`` barrier is recorded;
        ``PENDING`` is not a committed stop and is returned unchanged.
        """
        job_id = scope_job_id(scope)
        # Validate deterministic metadata before the barrier effect, so a bad
        # reason/session can never fail after the stop is already committed.
        AgentEvent(
            job_id=job_id,
            session_id=session_id,
            event_id=_stop_event_id(stop_id),
            event_type=EventType.STOP,
            usage_kind=UsageKind.UNKNOWN,
            decision="DENY",
            stop_reason=stop_reason or stop_id,
        )
        try:
            with FileLock(self._guard_lock_path(job_id), timeout_s=self.lock_timeout_s):
                result = self.control.stop(scope, stop_id)
                if result.get("status") == "EFFECTIVE":
                    actual = str(result.get("stop_id") or stop_id)
                    self._safe_record(
                        AgentEvent(
                            job_id=job_id,
                            session_id=session_id,
                            event_id=_stop_event_id(actual),
                            event_type=EventType.STOP,
                            usage_kind=UsageKind.UNKNOWN,
                            decision="DENY",
                            stop_reason=stop_reason or actual,
                        )
                    )
                return result
        except TimeoutError:
            # Only the guard-lock acquisition can reach here (before the barrier).
            return {
                "status": "PENDING",
                "further_dispatch_blocked": False,
                "abort_confirmed": False,
                "external_effect": "unknown",
                "reason": "GUARD_LOCK_TIMEOUT",
            }

    def _guard_check(self, identity: AttemptIdentity) -> str:
        """Authoritative control-journal guard (fail-closed on corruption)."""
        try:
            status = self.control.status(identity.scope)
        except ControlError as exc:
            return exc.code
        if status.get("stopped"):
            return "WORKFLOW_STOPPED"
        for attempt in status.get("attempts") or []:
            if attempt.get("attempt_id") == identity.attempt_id:
                continue
            state = attempt.get("state")
            if state in ("DENIED", "CANCELLED_NO_SEND"):
                return "DECISION_DENIED"
            if state == "OUTCOME_UNKNOWN":
                return "UNRESOLVED_UNKNOWN"
        return ""

    def _has_event(self, keys: dict[str, str]) -> bool:
        try:
            self.journal.get(
                AgentEventRef(keys["job_id"], keys["session_id"], keys["event_id"])
            )
            return True
        except AgentEventError:
            return False

    def _safe_record(self, event: AgentEvent) -> tuple[bool, str]:
        """Attribution is best-effort and runs after the effect; never raises a
        lock timeout or write error out of the dispatch result, and never leaks
        an exception message (safe error code only)."""
        try:
            self.journal.record(event)
            return True, ""
        except AgentEventError as exc:
            return False, exc.code
        except Exception:  # noqa: BLE001 — post-effect attribution must not crash
            return False, "EVENT_WRITE_FAILED"
