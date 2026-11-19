"""Read-only agent gate: may this agent start work today?

Only a user-set ``consumer_envelopes.<consumer>.max_usd_day`` can deny. Plan
exhaustion is reported, never denied. Reuses the existing files and formats
(keys_app.json, keys_usage.json day bucket, plan_status.jsonl); writes nothing,
holds no locks, never raises.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from tollgate.app_config import CONFIG_NAME
from tollgate.usage_ledger import USAGE_NAME
from tollgate.provider_ops.plan_status import LOG_NAME, MAX_AGE, _parse_time

_UNAVAILABLE = "tollgate_unavailable"


def _now_dt(now: Any) -> datetime:
    if isinstance(now, datetime):
        return now.astimezone()
    if isinstance(now, (int, float)) and not isinstance(now, bool):
        return datetime.fromtimestamp(float(now)).astimezone()
    return datetime.now().astimezone()


def _read_json(path: Path) -> Any:
    """Plain read; missing file -> None, unreadable/corrupt -> raises."""
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _default_user_dir() -> Path:
    """The User dir TollGate would use, resolved without creating anything.

    ``paths.data_home()`` may create a portable sibling directory; a read-only gate must not.
    A portable layout that does not exist yet counts as unavailable.
    """
    from tollgate import paths

    for env in ("TOLLGATE_HOME", "GNOM_WS"):
        value = (os.environ.get(env) or "").strip()
        if value:
            return Path(value).expanduser().resolve() / "User"
    if paths.is_portable_mode():
        hub = paths.project_root()
        for cand in paths.portable_data_candidates(hub):
            if (cand / "User").is_dir() or (cand / "User" / "Key.txt").is_file():
                return cand.resolve() / "User"
        for cand in paths.portable_data_candidates(hub):
            if cand.is_dir() and cand != hub:
                return cand.resolve() / "User"
        raise FileNotFoundError("portable data directory does not exist")
    return (Path.home() / ".tollgate").resolve() / "User"


def _paths(user_dir: Any) -> tuple[Path, Path, Path]:
    if user_dir is None:
        base = _default_user_dir()
        cfg = None
        for key in ("TOLLGATE_CONFIG", "GNOM_KEYS_CONFIG"):
            env = (os.environ.get(key) or "").strip()
            if env:
                cfg = Path(env).expanduser().resolve()
                break
        return cfg or base / CONFIG_NAME, base / USAGE_NAME, base / LOG_NAME
    base = Path(user_dir)
    return base / CONFIG_NAME, base / USAGE_NAME, base / LOG_NAME


def _user_limit(cfg: Any, consumer: str) -> float | None:
    """max_usd_day of a user-set (non-``_default``) envelope, else None."""
    if cfg is None:
        return None
    if not isinstance(cfg, dict):
        raise ValueError("config not an object")
    envs = cfg.get("consumer_envelopes")
    if envs is None:
        return None
    if not isinstance(envs, dict):
        raise ValueError("consumer_envelopes not an object")
    if consumer == "_default":
        return None
    block = envs.get(consumer)
    if not isinstance(block, dict):
        return None
    limit = float(block.get("max_usd_day") or 0.0)
    return limit if limit > 0 else None


def _day_spend(usage: Any, consumer: str, today: date) -> tuple[float | None, str]:
    """(spent_usd, usd_kind) from today's ledger bucket.

    The ledger does not tag measured vs. estimated usd, so recorded usd is
    reported as "estimated". No entry for today, or calls without any usd,
    is unknown (agents such as the claude CLI may spend outside TollGate).
    """
    if usage is None:
        return None, "unknown"
    if not isinstance(usage, dict) or usage.get("_corrupt"):
        raise ValueError("ledger corrupt")
    if usage.get("day") != today.isoformat():
        return None, "unknown"
    consumers = usage.get("consumers")
    entry = consumers.get(consumer) if isinstance(consumers, dict) else None
    if not isinstance(entry, dict):
        return None, "unknown"
    usd = float(entry.get("usd") or 0.0)
    if usd <= 0.0:
        return None, "unknown"
    return usd, "estimated"


def _plan(path: Path, consumer: str, now: datetime) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    latest: dict[str, Any] | None = None
    latest_at: datetime | None = None
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if not isinstance(row, dict) or row.get("provider") != consumer:
                continue
            at = _parse_time(row.get("evidence_at"))
            if at is None:
                continue
            if latest_at is None or at >= latest_at:
                latest, latest_at = row, at
    if latest is None or latest_at is None:
        return None
    status = latest.get("limit_status")
    if status not in ("available", "exhausted", "unknown", "tight"):
        status = "unknown"
    fresh = (now - latest_at) <= MAX_AGE
    resets: datetime | None = None
    if status == "exhausted":
        windows = [w for w in (latest.get("windows") or []) if isinstance(w, dict)]
        hit = [w for w in windows if (w.get("used_percent") or 0) >= 100] or windows
        # Each exhausted window counts while it has not reset. A reset of the shorter
        # window must not hide a longer one that is still exhausted; the plan stays
        # exhausted until the last of them resets.
        active = []
        for w in hit:
            span = w.get("minutes")
            if isinstance(span, (int, float)) and span > 0 and (now - latest_at) > timedelta(minutes=span):
                continue
            reset = _parse_time(w.get("resets_at"))
            if reset is not None and reset <= now:
                continue
            active.append(reset)
        if hit:
            if not active:
                fresh = False
            else:
                known = [r for r in active if r is not None]
                resets = max(known) if known else None
                if resets is not None:
                    fresh = True  # an explicit future reset date is the evidence's validity
    return {
        "limit_status": status,
        "evidence_at": latest.get("evidence_at"),
        "fresh": bool(fresh),
        "_resets": resets,
    }


def _result(decision: str, reason: str, source: str, spent: float | None, limit: float | None,
            kind: str, plan: dict[str, Any] | None, valid_until: float | None) -> dict[str, Any]:
    return {
        "decision": decision,
        "reason": reason,
        "limit_source": source,
        "day": {"spent_usd": spent, "limit_usd": limit, "usd_kind": kind},
        "plan": plan,
        "valid_until": valid_until,
    }


def agent_gate(consumer: str, *, user_dir: Any = None, now: Any = None) -> dict[str, Any]:
    """Read-only admission hint for an agent. Never raises, never writes.

    ``user_dir``: directory holding keys_app.json / keys_usage.json /
    plan_status.jsonl (default: TollGate's User dir). ``now``: epoch seconds or
    datetime (default: current time).
    """
    try:
        from tollgate.consumers import normalize_consumer_id

        # Same lane id as the ledger and the envelope lookup use (empty/invalid -> anonymous).
        cid = normalize_consumer_id(consumer)
        when = _now_dt(now)
        cfg_p, usage_p, plan_p = _paths(user_dir)
        limit = _user_limit(_read_json(cfg_p), cid)
        usage = _read_json(usage_p)
        plan = _plan(plan_p, cid, when)

        midnight = datetime.combine(when.date() + timedelta(days=1), datetime.min.time()).astimezone()
        until: float | None = None
        reason = "no_envelope"
        decision = "allow"
        source = "none"
        spent: float | None = None
        kind = "unknown"
        if limit is not None:
            source = "user_envelope"
            until = midnight.timestamp()
            spent, kind = _day_spend(usage, cid, when.date())
            if spent is None:
                reason = "spend_unknown"
            elif spent >= limit:
                decision, reason = "deny", "day_budget_reached"
            else:
                reason = "within_budget"
        if plan is not None and plan["limit_status"] == "exhausted" and plan["fresh"] and decision == "allow":
            reason = "plan_exhausted_observed"
            r = plan["_resets"]
            if r is not None:
                until = r.timestamp() if until is None else min(until, r.timestamp())
        if plan is not None:
            plan = {k: v for k, v in plan.items() if not k.startswith("_")}
        return _result(decision, reason, source, spent, limit, kind, plan, until)
    except Exception:  # noqa: BLE001 - contract: never raise
        return _result("unknown", _UNAVAILABLE, "unavailable", None, None, "unknown", None, None)
