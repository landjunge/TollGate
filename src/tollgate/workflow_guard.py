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
  other guard dispatches of the same job. It then records exactly one outcome
  event keyed by job/session/event.
* ``WorkflowGuard.stop`` commits the existing stop barrier and records a durable
  ``stop`` event using the control's **actual** stop id.

The guard is authoritative from the control journal (not just the event journal):
an attempt left in ``DISPATCH_ATTEMPTED``/``OUTCOME_UNKNOWN`` blocks new attempts
after a crash even when the event write was lost. Unknown outcomes are never
auto-settled or released; only the existing trusted ``settle`` with final evidence
can resolve them, and this module never calls it.

Identity mapping (unique, deterministic):

* ``job_id``    ← ``scope_job_id(scope)`` (sha256 of the frozen scope, valid id)
* ``session_id``← ``AttemptIdentity.task_id`` (attempts) / reserved ``tollgate-scope`` (stop)
* ``event_id``  ← ``AttemptIdentity.attempt_id`` (attempts) / ``stop:<stop_id>`` (stop)

The session label ``tollgate-scope`` and the ``stop:`` event prefix are reserved:
a task id of exactly ``tollgate-scope`` or an attempt id beginning with ``stop:``
is unsupported and would be a namespace collision.
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
from tollgate.filelock import FileLock
from tollgate.workflow_control import AttemptIdentity, WorkflowControl, WorkflowScope

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
    return {
        "job_id": scope_job_id(identity.scope),
        "session_id": identity.task_id,
        "event_id": identity.attempt_id,
    }


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
        the guard re-derives the authoritative state from the control journal, so
        a concurrent or crashed attempt cannot slip past an unknown/stop/deny.
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
                        recorded = self._safe_record(
                            AgentEvent(
                                **keys,
                                event_type=EventType.USAGE,
                                usage_kind=UsageKind.UNKNOWN,
                            )
                        )
                    else:
                        outcome = "SENT"
                        recorded = self._safe_record(success_event)
                elif state in ("DENIED", "CANCELLED_NO_SEND"):
                    outcome = "DENIED"
                    recorded = self._safe_record(
                        AgentEvent(
                            **keys,
                            event_type=EventType.USAGE,
                            usage_kind=UsageKind.UNKNOWN,
                            decision="DENY",
                            stop_reason=str(result.get("reason_code") or ""),
                        )
                    )
                else:
                    # Replay: no callback ran. Return the stored result, never a
                    # fabricated SENT/ALLOW and never a conflict from new args.
                    outcome = "REPLAYED"
                    recorded = True

                return {
                    "ok": True,
                    "dispatched": called["sent"] and not called["raised"],
                    "state": state,
                    "outcome": outcome,
                    "reason_code": result.get("reason_code"),
                    "recorded": recorded,
                    "attempt": result,
                    "attempt_id": identity.attempt_id,
                }
        except TimeoutError:
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

        Uses the control's actual persisted stop id (not the requested one) so a
        repeat stop is idempotent and never rewrites another barrier's identity.
        Only a confirmed ``EFFECTIVE`` barrier is recorded; ``PENDING`` is not a
        committed stop and is returned unchanged.
        """
        job_id = scope_job_id(scope)
        try:
            with FileLock(self._guard_lock_path(job_id), timeout_s=self.lock_timeout_s):
                result = self.control.stop(scope, stop_id)
                if result.get("status") == "EFFECTIVE":
                    actual = str(result.get("stop_id") or stop_id)
                    self._safe_record(
                        AgentEvent(
                            job_id=job_id,
                            session_id=session_id,
                            event_id=f"{_STOP_PREFIX}{actual}",
                            event_type=EventType.STOP,
                            usage_kind=UsageKind.UNKNOWN,
                            decision="DENY",
                            stop_reason=stop_reason or actual,
                        )
                    )
                return result
        except TimeoutError:
            return {
                "status": "PENDING",
                "further_dispatch_blocked": False,
                "abort_confirmed": False,
                "external_effect": "unknown",
                "reason": "GUARD_LOCK_TIMEOUT",
            }

    def _guard_check(self, identity: AttemptIdentity) -> str:
        """Fail-closed: corrupt journal or unresolved/stopped/denied state blocks."""
        job_id = scope_job_id(identity.scope)
        try:
            ev = self.journal.start_guard(job_id)
        except AgentEventError as exc:
            return exc.code
        if ev["blocked"]:
            return str(ev["reason"])

        # Authoritative control-journal view (survives a crashed event write).
        status = self.control.status(identity.scope)
        if status.get("stopped"):
            return "WORKFLOW_STOPPED"
        for attempt in status.get("attempts") or []:
            if attempt.get("attempt_id") == identity.attempt_id:
                continue
            if attempt.get("state") == "OUTCOME_UNKNOWN":
                return "UNRESOLVED_UNKNOWN"
        return ""

    def _safe_record(self, event: AgentEvent) -> bool:
        """Attribution is best-effort; the authoritative guard reads the control
        journal, so a write failure never crashes the dispatch result."""
        try:
            self.journal.record(event)
            return True
        except AgentEventError:
            return False
