"""One disposable workflow-guard demo; no keys, providers, network or persistent user data.

Exercises the structured event guard lifecycle with an owned temporary journal
and dummy callbacks only:

  reserve -> single dispatch (unknown timeout) -> replay does not re-send ->
  a new attempt is blocked until evidence-bound settlement reconciles it ->
  a separate scope demonstrates a committed stop.

Amounts are synthetic microdollar units, not provider bills or a hard cost cap.
``task_id``/``attempt_id`` are workflow identities; they are never provider
session ids.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from tollgate.agent_events import AgentEventJournal
from tollgate.workflow_control import (
    AttemptIdentity,
    Quote,
    WorkflowControl,
    WorkflowScope,
)
from tollgate.workflow_guard import WorkflowGuard


def _ident(scope: WorkflowScope, attempt_id: str) -> AttemptIdentity:
    # workflow identities only — task_id/attempt_id are not provider session ids.
    return AttemptIdentity(
        scope, "dummy-task", "codex", "codex-lane", attempt_id, "d" * 64
    )


def main() -> None:
    quote = Quote(
        "dummy-v1", "dummy", "bounded-send", "local-dummy", 60, "fixed-dummy-v1"
    )
    with TemporaryDirectory(prefix="tollgate-guard-demo-") as directory:
        os.environ["TOLLGATE_HOME"] = directory
        root = Path(directory)

        # ---- Scope A: unknown -> replay blocked -> settlement after evidence ----
        scope_a = WorkflowScope("dummy-project", "dummy-workflow-a")
        # Test-only admission: production must use existing admit(), not this lambda.
        control_a = WorkflowControl(
            root=root / "a",
            admission=lambda *_: True,
            registered_quotes={quote.adapter_id: quote},
        )
        journal_a = AgentEventJournal(root=root / "a")
        guard_a = WorkflowGuard(control_a, journal_a)
        control_a.configure_budget(scope_a, "codex", "codex-lane", 1000)

        effects_a: list[str] = []
        identity_a = _ident(scope_a, "attempt-a1")
        control_a.reserve(identity_a, quote)

        def flaky() -> None:
            effects_a.append("synthetic-dispatch")
            raise TimeoutError("synthetic timeout")

        unknown = guard_a.dispatch(identity_a, flaky)
        replay = guard_a.dispatch(
            identity_a, lambda: effects_a.append("would-be-duplicate")
        )

        identity_b = _ident(scope_a, "attempt-a2")
        control_a.reserve(identity_b, quote)
        blocked = guard_a.dispatch(
            identity_b, lambda: effects_a.append("blocked-should-not-run")
        )

        # Synthetic test evidence only, not a provider bill or real cost claim.
        settled = control_a.settle(
            identity_a, 40, "synthetic-settlement", "synthetic-evidence"
        )
        reconciled = guard_a.dispatch(
            identity_b, lambda: effects_a.append("reconciled-dispatch")
        )

        # ---- Scope B: a committed stop blocks further dispatch ----
        scope_b = WorkflowScope("dummy-project", "dummy-workflow-b")
        control_b = WorkflowControl(
            root=root / "b",
            admission=lambda *_: True,
            registered_quotes={quote.adapter_id: quote},
        )
        journal_b = AgentEventJournal(root=root / "b")
        guard_b = WorkflowGuard(control_b, journal_b)
        control_b.configure_budget(scope_b, "codex", "codex-lane", 1000)
        identity_c = _ident(scope_b, "attempt-b1")
        control_b.reserve(identity_c, quote)
        stop = guard_b.stop(scope_b, "stop-1", stop_reason="operator")
        effects_b: list[str] = []
        stopped = guard_b.dispatch(
            identity_c, lambda: effects_b.append("stopped-should-not-run")
        )

        result = {
            "synthetic_only": True,
            "scope_a": {
                "unknown_outcome": unknown["outcome"],
                "replay_outcome": replay["outcome"],
                "blocked_reason": blocked["reason"],
                "settled_state": settled["state"],
                "reconciled_outcome": reconciled["outcome"],
                "effects": effects_a,
            },
            "scope_b": {
                "stop_status": stop["status"],
                "blocked_reason": stopped["reason"],
                "effects": effects_b,
            },
        }

        # A real controlled dummy effect: one dispatch, one reconciled dispatch.
        assert effects_a == ["synthetic-dispatch", "reconciled-dispatch"]
        assert effects_b == []
        assert unknown["outcome"] == "UNKNOWN"
        assert replay["outcome"] == "REPLAYED"
        assert blocked["reason"] == "UNRESOLVED_UNKNOWN"
        assert settled["state"] == "SETTLED"
        assert reconciled["outcome"] == "SENT"
        assert stop["status"] == "EFFECTIVE"
        assert stopped["reason"] == "WORKFLOW_STOPPED"

        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
