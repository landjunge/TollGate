"""
Structured agent events — idempotent attribution of prompt/usage/stop.

A local, durable, per-job attribution journal for structured agent events that
an explicit trusted adapter (e.g. a future ACP / KiraBridge path) hands to
TollGate. It is **not** a queue, scheduler, provider client or global process
controller: it only de-duplicates and classifies events so that measured usage,
observed provider values, estimates and unknown outcomes stay strictly apart.

Contract (TollGate working board ``dd26e513fd3f``, Big Plan ``30f80f0e050e``):

* Every event carries ``job_id``, ``session_id`` and ``event_id``. The triple is
  the durable identity: repeating the same event is idempotent, changed content
  under the same identity is a conflict. No automatic replay.
* ``prompt`` records an accepted input; ``usage`` records tokens/cost/runtime;
  ``stop`` records a durable stop reason / budget decision. ``tool`` records an
  observed model turn.
* ``usage_kind`` separates ``measured`` (locally measured), ``observed``
  (provider-reported values), ``estimated`` (our own estimate) and ``unknown``.
  Unknown is never merged into measured/spent totals.
* An ``unknown`` usage/tool outcome, a committed ``stop`` or a ``DENY`` budget
  decision blocks ``start_guard`` (a replay/start guard) until the adapter
  supplies trusted evidence. This is **not** a budget release: real budget
  admission stays in ``gateway.admit`` / ``workflow_control``, which a caller
  must still pass before any actual paid dispatch.

This module deliberately makes no provider HTTP call and claims no live billing
adapter. It is event attribution only — it never grants a budget and never
replaces the existing admission path. Amounts are integer USD microdollars,
mirroring ``workflow_control``.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterator

from tollgate.audit_log import append_audit
from tollgate.filelock import FileLock
from tollgate.paths import user_dir

__all__ = [
    "AgentEvent",
    "AgentEventError",
    "AgentEventJournal",
    "AgentEventRef",
    "EventType",
    "UsageKind",
]

UNIT = "USD_MICRO"
MAX_AMOUNT = 10**15
MAX_TOKENS = 10**12
MAX_EVENTS_PER_JOB = 10_000
MAX_JOURNAL_BYTES = 8_000_000

_ID = re.compile(r"[A-Za-z0-9_.:-]{1,128}\Z")


class AgentEventError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class EventType(str, Enum):
    PROMPT = "prompt"
    USAGE = "usage"
    STOP = "stop"
    TOOL = "tool"


class UsageKind(str, Enum):
    MEASURED = "measured"
    OBSERVED = "observed"
    ESTIMATED = "estimated"
    UNKNOWN = "unknown"


_DECISIONS = frozenset({"", "ALLOW", "DENY"})


def _id(value: str) -> None:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise AgentEventError("INVALID_ID")


def _uint(value: int, bound: int) -> None:
    if type(value) is not int or not 0 <= value <= bound:
        raise AgentEventError("INVALID_AMOUNT")


def _label(value: str, bound: int = 200) -> None:
    if not isinstance(value, str) or len(value) > bound:
        raise AgentEventError("INVALID_ID")


@dataclass(frozen=True)
class AgentEventRef:
    """Durable identity of one structured agent event."""

    job_id: str
    session_id: str
    event_id: str

    def __post_init__(self) -> None:
        for value in (self.job_id, self.session_id, self.event_id):
            _id(value)

    def as_dict(self) -> dict[str, str]:
        return {
            "job_id": self.job_id,
            "session_id": self.session_id,
            "event_id": self.event_id,
        }


@dataclass(frozen=True)
class AgentEvent:
    """One structured event. Enums are stored/read as their string values."""

    job_id: str
    session_id: str
    event_id: str
    event_type: EventType
    usage_kind: UsageKind = UsageKind.UNKNOWN
    tokens_in: int = 0
    tokens_out: int = 0
    cost_microusd: int = 0
    turns: int = 0
    runtime_s: float = 0.0
    decision: str = ""
    stop_reason: str = ""
    evidence_ref: str = ""

    def __post_init__(self) -> None:
        _id(self.job_id)
        _id(self.session_id)
        _id(self.event_id)
        if not isinstance(self.event_type, EventType):
            raise AgentEventError("INVALID_TYPE")
        if not isinstance(self.usage_kind, UsageKind):
            raise AgentEventError("INVALID_KIND")
        for value in (self.tokens_in, self.tokens_out, self.turns):
            _uint(value, MAX_TOKENS)
        _uint(self.cost_microusd, MAX_AMOUNT)
        if (
            type(self.runtime_s) not in (int, float)
            or not math.isfinite(float(self.runtime_s))
            or float(self.runtime_s) < 0
        ):
            raise AgentEventError("INVALID_AMOUNT")
        if self.decision not in _DECISIONS:
            raise AgentEventError("INVALID_DECISION")
        _label(self.stop_reason)
        _label(self.evidence_ref, 300)

    def ref(self) -> AgentEventRef:
        return AgentEventRef(self.job_id, self.session_id, self.event_id)

    def as_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "session_id": self.session_id,
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "usage_kind": self.usage_kind.value,
            "tokens_in": int(self.tokens_in),
            "tokens_out": int(self.tokens_out),
            "cost_microusd": int(self.cost_microusd),
            "turns": int(self.turns),
            "runtime_s": float(self.runtime_s),
            "decision": self.decision,
            "stop_reason": self.stop_reason,
            "evidence_ref": self.evidence_ref,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentEvent":
        """Strict reconstruction from persisted raw values.

        No coercion: bool/string/fraction/null or missing fields are rejected by
        the constructor's type checks, so a tampered journal fails closed instead
        of being silently normalized (mirrors ``workflow_control._money``).
        """
        try:
            return cls(
                job_id=data["job_id"],
                session_id=data["session_id"],
                event_id=data["event_id"],
                event_type=EventType(data["event_type"]),
                usage_kind=UsageKind(data["usage_kind"]),
                tokens_in=data["tokens_in"],
                tokens_out=data["tokens_out"],
                cost_microusd=data["cost_microusd"],
                turns=data["turns"],
                runtime_s=data["runtime_s"],
                decision=data["decision"],
                stop_reason=data["stop_reason"],
                evidence_ref=data["evidence_ref"],
            )
        except AgentEventError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise AgentEventError("JOURNAL_UNAVAILABLE") from exc


def _unique_pairs(pairs: Any) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("duplicate key")
        out[key] = value
    return out


class AgentEventJournal:
    """Durable, idempotent attribution of structured agent events.

    Storage reuses the existing ``User/`` data home, ``FileLock`` and the ops
    ``audit.jsonl``. Journals are per-job (``User/agent_events/<hash>.json``,
    0600), atomically replaced and fsync'd, exactly like ``workflow_control``.
    No parallel queue, no second ledger, no provider call.
    """

    def __init__(
        self,
        *,
        root: Path | None = None,
        lock_timeout_s: float = 1.0,
        emit_authority: bool = False,
    ) -> None:
        if (
            type(lock_timeout_s) not in (int, float)
            or not 0 < lock_timeout_s <= 30
            or not math.isfinite(lock_timeout_s)
        ):
            raise AgentEventError("INVALID_LOCK_TIMEOUT")
        self.root = root
        self.directory = user_dir(root) / "agent_events"
        self.lock_timeout_s = lock_timeout_s
        # Opt-in envelope emit (reuses G4 authority_emit); off by default so a
        # plain reader never writes side files. Never changes any decision.
        self.emit_authority = emit_authority

    def _path(self, job_id: str) -> Path:
        digest = hashlib.sha256(job_id.encode("utf-8")).hexdigest()
        return self.directory / (digest + ".json")

    def _empty(self, job_id: str) -> dict[str, Any]:
        return {"schema": 1, "job_id": job_id, "seq": 0, "events": {}}

    def _validate(self, data: dict[str, Any], job_id: str) -> None:
        if (
            data.get("schema") != 1
            or data.get("job_id") != job_id
            or type(data.get("seq")) is not int
            or not isinstance(data.get("events"), dict)
        ):
            raise ValueError("schema")
        events = data["events"]
        if len(events) > MAX_EVENTS_PER_JOB:
            raise ValueError("capacity")
        seen = 0
        for session_id, by_event in events.items():
            _id(session_id)
            if not isinstance(by_event, dict):
                raise ValueError("events")
            for event_id, stored in by_event.items():
                _id(event_id)
                if not isinstance(stored, dict):
                    raise ValueError("event")
                # Re-validate the stored content; unknown/invalid fields fail closed.
                parsed = AgentEvent.from_dict(stored)
                # Persisted identity must match the journal job and its key path;
                # a tampered/mismatched entry is rejected, never silently read.
                if (
                    parsed.job_id != job_id
                    or parsed.session_id != session_id
                    or parsed.event_id != event_id
                ):
                    raise ValueError("identity")
                seen += 1
        if seen > MAX_EVENTS_PER_JOB:
            raise ValueError("capacity")

    @staticmethod
    def _commit(path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        data["seq"] = int(data.get("seq") or 0) + 1
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        # Serialize first and bound the actual UTF-8 bytes, so a write can never
        # succeed and then poison the journal past the read limit. On rejection
        # the previous journal file is left untouched.
        payload = json.dumps(data, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
        if len(payload) > MAX_JOURNAL_BYTES:
            raise AgentEventError("JOURNAL_SIZE")
        fd, name = tempfile.mkstemp(
            dir=path.parent, prefix=".agent-events-", suffix=".tmp"
        )
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, path)
            if os.name != "nt":
                dirfd = os.open(path.parent, os.O_RDONLY)
                try:
                    os.fsync(dirfd)
                finally:
                    os.close(dirfd)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def _audit(self, event: str, job_id: str, *, code: str = "OK") -> None:
        # No prompt/content/payload/secret leaves the journal.
        append_audit(
            "agent_" + event,
            op=event,
            ok=code == "OK",
            error=code,
            extra={"job_ref": self._path(job_id).stem},
            root=self.root,
        )

    @contextmanager
    def _transaction(self, job_id: str) -> Iterator[tuple[Path, dict[str, Any]]]:
        path = self._path(job_id)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with FileLock(path, timeout_s=self.lock_timeout_s):
            if path.exists():
                try:
                    if path.stat().st_size > MAX_JOURNAL_BYTES:
                        raise ValueError("size")
                    data = json.loads(
                        path.read_text(encoding="utf-8"),
                        object_pairs_hook=_unique_pairs,
                    )
                    self._validate(data, job_id)
                except Exception as exc:
                    raise AgentEventError("JOURNAL_UNAVAILABLE") from exc
            else:
                data = self._empty(job_id)
            yield path, data

    def _project(self, stored: dict[str, Any], *, deduplicated: bool) -> dict[str, Any]:
        out = dict(stored)
        out["deduplicated"] = bool(deduplicated)
        return out

    def record(self, event: AgentEvent) -> dict[str, Any]:
        """Idempotently record one event. Repeats read the same entry; changed
        content under the same (job_id, session_id, event_id) is a conflict.
        """
        _id(event.job_id)
        stored = event.as_dict()
        with self._transaction(event.job_id) as (path, data):
            events = data.setdefault("events", {})
            by_event = events.setdefault(event.session_id, {})
            existing = by_event.get(event.event_id)
            if existing is not None:
                if existing != stored:
                    raise AgentEventError("IDEMPOTENCY_CONFLICT")
                self._audit("record", event.job_id)
                return self._project(existing, deduplicated=True)
            if sum(len(v) for v in events.values()) >= MAX_EVENTS_PER_JOB:
                raise AgentEventError("JOURNAL_CAPACITY")
            by_event[event.event_id] = stored
            self._commit(path, data)
            result = self._project(stored, deduplicated=False)
        self._audit("record", event.job_id)
        if self.emit_authority and event.event_type in (EventType.STOP,):
            self._emit_stop(event)
        return result

    def get(self, ref: AgentEventRef) -> dict[str, Any]:
        _id(ref.job_id)
        with self._transaction(ref.job_id) as (_, data):
            by_event = data.get("events", {}).get(ref.session_id)
            if not by_event or ref.event_id not in by_event:
                raise AgentEventError("EVENT_NOT_FOUND")
            return self._project(by_event[ref.event_id], deduplicated=True)

    def summary(self, job_id: str) -> dict[str, Any]:
        """Aggregate one job, keeping the four usage kinds strictly separate."""
        _id(job_id)
        with self._transaction(job_id) as (_, data):
            return self._summary_locked(job_id, data)

    def _summary_locked(self, job_id: str, data: dict[str, Any]) -> dict[str, Any]:
        usage: dict[str, dict[str, Any]] = {
            kind.value: {
                "tokens_in": 0,
                "tokens_out": 0,
                "cost_microusd": 0,
                "events": 0,
            }
            for kind in UsageKind
        }
        turns = 0
        runtime = 0.0
        stopped = False
        stop_reason = ""
        decisions: dict[str, int] = {"ALLOW": 0, "DENY": 0}
        unknown_outcome = False
        sessions = set()
        event_count = 0
        for session_id, by_event in data.get("events", {}).items():
            sessions.add(session_id)
            for stored in by_event.values():
                event_count += 1
                # Values are already strict-typed by _validate; read them raw so
                # the projection and the summary can never diverge.
                et = stored["event_type"]
                kind = stored["usage_kind"]
                decision = stored["decision"]
                if decision in decisions:
                    decisions[decision] += 1
                if et == EventType.STOP.value:
                    stopped = True
                    stop_reason = stored["stop_reason"] or stop_reason
                if et in (EventType.USAGE.value, EventType.TOOL.value):
                    turns += stored["turns"]
                    runtime += stored["runtime_s"]
                if et == EventType.USAGE.value and kind in usage:
                    usage[kind]["tokens_in"] += stored["tokens_in"]
                    usage[kind]["tokens_out"] += stored["tokens_out"]
                    usage[kind]["cost_microusd"] += stored["cost_microusd"]
                    usage[kind]["events"] += 1
                if kind == UsageKind.UNKNOWN.value and et in (
                    EventType.USAGE.value,
                    EventType.TOOL.value,
                ):
                    unknown_outcome = True

        denied = decisions.get("DENY", 0) > 0
        if stopped:
            start_reason = "WORKFLOW_STOPPED"
        elif denied:
            start_reason = "DECISION_DENIED"
        elif unknown_outcome:
            start_reason = "UNKNOWN_OUTCOME"
        else:
            start_reason = "OK"
        return {
            "job_id": job_id,
            "schema": 1,
            "unit": UNIT,
            "events": event_count,
            "sessions": len(sessions),
            "turns": turns,
            "runtime_s": runtime,
            "usage": usage,
            "stopped": stopped,
            "stop_reason": stop_reason,
            "decisions": decisions,
            "replay_blocked": start_reason != "OK",
            "replay_reason": start_reason,
            # Attribution only: this summary is never a budget grant.
            "budget_authorized": False,
        }

    def start_guard(self, job_id: str) -> dict[str, Any]:
        """Replay/stop/deny/unknown guard for a new start — never a budget grant.

        A trusted caller must still pass the existing ``gateway.admit`` /
        ``workflow_control`` admission and budget journal before any real paid
        dispatch. This guard only blocks replays, committed stops, ``DENY``
        decisions and unresolved unknown outcomes in the event attribution.
        """
        s = self.summary(job_id)
        return {
            "blocked": bool(s["replay_blocked"]),
            "reason": s["replay_reason"],
            "stopped": s["stopped"],
            "stop_reason": s["stop_reason"],
            "budget_authorized": False,
        }

    def _emit_stop(self, event: AgentEvent) -> None:
        try:
            from tollgate.authority_emit import emit

            emit(
                "agent.stop",
                decision="DENY" if event.decision == "DENY" else None,
                reason_code=event.stop_reason or None,
                action="stop",
                resource=f"agent:{event.job_id}",
                budget_ref="budget:agent",
            )
        except Exception:  # noqa: BLE001 — envelope emit never changes the decision
            return
