"""Read-only plan and limit snapshots for the TollGate pilot.

Pilot scope (Big Plan, 10.11.2026): the subscription CLIs Grok (xAI), Codex
(OpenAI) and Claude Code (Anthropic). Only status sources that already exist on
this machine are read:

- Codex: ``codex app-server`` JSON-RPC ``account/rateLimits/read`` (an account
  read, no model request) and ``token_count.rate_limits`` events that Codex
  writes into ``~/.codex/sessions``.
- Claude Code: the ``rate_limits`` object Claude Code pipes into a statusline
  command, ``cachedUsageUtilization`` in ``~/.claude.json`` (written by
  ``/usage``) and the rate-limit messages in ``~/.claude/projects`` logs.
- Grok Build: ``billing: fetched credits config`` and HTTP 402 events in
  ``~/.grok/logs/unified.jsonl``. The xAI billing API reports API spend and is
  never treated as subscription quota.

Nothing here sends a model request, buys credits or opens a credential file.
Account ids become a one-way reference. Provider percentages are never turned
into token counts: ``absolute_quota`` stays ``unknown``.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator
from zoneinfo import ZoneInfo

SCHEMA = "tollgate-plan-snapshot-v1"
PROVIDERS = ("codex", "claude", "grok")
LOG_NAME = "plan_status.jsonl"
# Pilot parameters, not provider values.
TIGHT_PERCENT = 90.0
MAX_AGE = timedelta(hours=6)

CONFIRMED, ESTIMATED, UNKNOWN = "confirmed", "estimated", "unknown"
_API_ENV = ("OPENAI_API_KEY", "CODEX_API_KEY", "OPENAI_BASE_URL")


def _iso(value: datetime | None) -> str | None:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") if value else None


def _parse_time(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else None
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        seconds = value / 1000 if value > 10**11 else value
        return datetime.fromtimestamp(seconds, timezone.utc)
    if isinstance(value, str) and value:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo else None
    return None


def account_ref(provider: str, raw_id: str | None) -> str | None:
    """One-way reference; the raw id never leaves this function."""
    if not raw_id:
        return None
    digest = hashlib.sha256(f"{provider}:{raw_id}".encode()).hexdigest()[:12]
    return f"{provider}:acct-{digest}"


def _window(name: str, minutes: int | None, used: Any, resets: Any,
            quality: str = CONFIRMED) -> dict[str, Any]:
    pct = float(used) if isinstance(used, (int, float)) and not isinstance(used, bool) else None
    return {"window": name, "minutes": minutes, "used_percent": pct,
            "resets_at": _iso(_parse_time(resets)), "quality": quality if pct is not None else UNKNOWN}


def _name_for(minutes: int | None) -> str:
    return {300: "5h", 1440: "day", 10080: "7d"}.get(minutes or 0, f"{minutes}m" if minutes else "unknown")


def _limit_status(windows: list[dict[str, Any]], reached: bool = False) -> str:
    known = [w["used_percent"] for w in windows if w["used_percent"] is not None]
    if reached or any(p >= 100 for p in known):
        return "exhausted"
    if not known:
        return UNKNOWN
    return "tight" if max(known) >= TIGHT_PERCENT else "available"


def snapshot(provider: str, *, source: str, source_kind: str, evidence_at: datetime | None,
             windows: list[dict[str, Any]], plan: str | None = None, plan_confidence: str = UNKNOWN,
             account: str | None = None, model: str | None = None, reached: bool = False,
             notes: Iterable[str] = (), now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    return {
        "schema": SCHEMA,
        "observed_at": _iso(now),
        "evidence_at": _iso(evidence_at),
        "provider": provider,
        "source": source,
        "source_kind": source_kind,
        "account_ref": account,
        "model": model,
        "plan": {"name": plan, "confidence": plan_confidence if plan else UNKNOWN},
        "windows": windows,
        "limit_status": _limit_status(windows, reached),
        "quality": CONFIRMED if any(w["quality"] == CONFIRMED for w in windows) else UNKNOWN,
        "absolute_quota": UNKNOWN,
        "notes": list(notes),
    }


# ----------------------------------------------------------------- Codex

def _codex_windows(rate: dict[str, Any], camel: bool) -> list[dict[str, Any]]:
    used, mins, resets = (("usedPercent", "windowDurationMins", "resetsAt") if camel
                          else ("used_percent", "window_minutes", "resets_at"))
    out = []
    for key in ("primary", "secondary"):
        w = rate.get(key)
        if isinstance(w, dict):
            out.append(_window(_name_for(w.get(mins)), w.get(mins), w.get(used), w.get(resets)))
    return out


def _app_server(codex: str, payload: str, timeout: float) -> list[str]:
    """Keep stdin open until the answer arrives; the server stops on EOF."""
    env = {k: v for k, v in os.environ.items() if k not in _API_ENV}
    try:
        proc = subprocess.Popen([codex, "app-server"], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                text=True, env=env)
    except OSError:
        return []
    timer = threading.Timer(timeout, proc.kill)
    timer.start()
    lines: list[str] = []
    try:
        proc.stdin.write(payload)
        proc.stdin.flush()
        for line in proc.stdout:
            lines.append(line)
            if '"id":2' in line.replace(" ", ""):
                break
    except OSError:
        pass
    finally:
        timer.cancel()
        proc.kill()
        proc.wait()
    return lines


def codex_rpc(codex: str = "codex", *, timeout: float = 15.0, now: datetime | None = None,
              runner: Any = None) -> dict[str, Any]:
    """``account/rateLimits/read`` via a short-lived app-server (no model call)."""
    requests = [
        {"id": 1, "method": "initialize",
         "params": {"clientInfo": {"name": "tollgate_plan_status", "version": "1"}}},
        {"method": "initialized", "params": {}},
        {"id": 2, "method": "account/rateLimits/read", "params": {}},
    ]
    payload = "".join(json.dumps(r) + "\n" for r in requests)
    lines = runner(payload) if runner else _app_server(codex, payload, timeout)
    result = None
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if row.get("id") == 2:
            result = row.get("result")
    source = "codex app-server account/rateLimits/read"
    if not isinstance(result, dict):
        return snapshot("codex", source=source, source_kind="cli_rpc", evidence_at=None,
                        windows=[], notes=["no answer from app-server"], now=now)
    rate = result.get("rateLimits") or {}
    plan = rate.get("planType")
    notes = []
    if rate.get("rateLimitReachedType"):
        notes.append(f"rate_limit_reached_type={rate['rateLimitReachedType']}")
    if result.get("ordinaryUsageAllowed") is False:
        notes.append("ordinaryUsageAllowed=false")
    credits = rate.get("credits") or {}
    if credits.get("hasCredits") is False:
        notes.append("no extra credits")
    return snapshot(
        "codex", source=source, source_kind="cli_rpc", evidence_at=now or datetime.now(timezone.utc),
        windows=_codex_windows(rate, camel=True), plan=plan,
        plan_confidence=CONFIRMED if plan and plan != "api" else UNKNOWN,
        account=account_ref("codex", result.get("accountId")),
        model=rate.get("normalModelSlug"),
        reached=bool(rate.get("rateLimitReachedType") or rate.get("spendControlReached")
                     or result.get("ordinaryUsageAllowed") is False),
        notes=notes, now=now)


def _recent_files(root: Path, since: datetime | None) -> list[Path]:
    if not root.is_dir():
        return []
    cutoff = since.timestamp() if since else 0
    return sorted((p for p in root.rglob("*.jsonl")
                   if not p.is_symlink() and p.stat().st_mtime >= cutoff),
                  key=lambda p: p.stat().st_mtime)


def codex_log_events(root: Path | None = None, since: datetime | None = None,
                     now: datetime | None = None) -> Iterator[tuple[dict[str, Any], dict[str, Any]]]:
    """Yield (snapshot, outcome) for each ``token_count`` event Codex logged.

    A logged token_count means a turn was answered: outcome ``ok``.
    """
    root = root or Path.home() / ".codex/sessions"
    for path in _recent_files(root, since):
        with path.open("rb") as handle:
            for raw in handle:
                if b'"token_count"' not in raw and b"usage limit" not in raw.lower():
                    continue
                try:
                    event = json.loads(raw)
                except ValueError:
                    continue
                payload = event.get("payload") or {}
                at = _parse_time(event.get("timestamp"))
                if at is None or (since and at < since) or event.get("type") != "event_msg":
                    continue
                if payload.get("type") == "token_count":
                    rate = payload.get("rate_limits") or {}
                    if rate.get("limit_id") not in (None, "codex"):
                        continue
                    snap = snapshot(
                        "codex", source="codex session log token_count", source_kind="cli_log",
                        evidence_at=at, windows=_codex_windows(rate, camel=False),
                        plan=rate.get("plan_type"),
                        plan_confidence=CONFIRMED if rate.get("plan_type") else UNKNOWN,
                        reached=bool(rate.get("rate_limit_reached_type")), now=now)
                    yield snap, {"provider": "codex", "at": _iso(at), "result": "ok"}
                elif payload.get("type") == "error" and "limit" in str(payload.get("message", "")).lower():
                    yield {}, {"provider": "codex", "at": _iso(at), "result": "limit"}


def codex_log_latest(root: Path | None = None, since: datetime | None = None,
                     now: datetime | None = None) -> dict[str, Any] | None:
    latest = None
    for snap, _ in codex_log_events(root, since, now):
        if snap and (latest is None or snap["evidence_at"] >= latest["evidence_at"]):
            latest = snap
    return latest


# ---------------------------------------------------------------- Claude

def claude_statusline(data: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    """Parse the JSON Claude Code pipes into a statusline command."""
    limits = data.get("rate_limits") or {}
    windows = []
    for key, name, minutes in (("five_hour", "5h", 300), ("seven_day", "7d", 10080)):
        w = limits.get(key)
        if isinstance(w, dict):
            windows.append(_window(name, minutes, w.get("used_percentage"), w.get("resets_at")))
    model = data.get("model") or {}
    notes = [] if windows else ["statusline input without rate_limits (API key, gateway or no response yet)"]
    return snapshot("claude", source="claude code statusline rate_limits", source_kind="statusline",
                    evidence_at=now or datetime.now(timezone.utc), windows=windows,
                    model=model.get("id") if isinstance(model, dict) else None, notes=notes, now=now)


def claude_cache(path: Path | None = None, now: datetime | None = None) -> dict[str, Any]:
    """``cachedUsageUtilization`` from ``~/.claude.json`` (last ``/usage`` fetch)."""
    path = path or Path.home() / ".claude.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    cache = data.get("cachedUsageUtilization") or {}
    util = cache.get("utilization") or {}
    windows = []
    for key, name, minutes in (("five_hour", "5h", 300), ("seven_day", "7d", 10080)):
        w = util.get(key)
        if isinstance(w, dict):
            windows.append(_window(name, minutes, w.get("utilization"), w.get("resets_at")))
    account = data.get("oauthAccount") or {}
    plan = account.get("organizationType")
    notes = [f"billing={account['billingType']}"] if account.get("billingType") else []
    reset_cache = data.get("unusedLimitResetStatusCache") or {}
    if reset_cache.get("holdsUnusedReset"):
        notes.append("holds an unused one-time limit reset")
    return snapshot("claude", source="~/.claude.json cachedUsageUtilization", source_kind="cli_cache",
                    evidence_at=_parse_time(cache.get("fetchedAtMs")), windows=windows,
                    plan=plan, plan_confidence=CONFIRMED if plan else UNKNOWN,
                    account=account_ref("claude", account.get("accountUuid") or cache.get("accountUuid")),
                    notes=notes, now=now)


_CLAUDE_LIMIT = re.compile(
    r"hit your (?P<kind>[\w-]+) limit\s*·\s*resets\s+(?:(?P<date>[A-Z][a-z]{2} \d{1,2}),?\s+)?"
    r"(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?\s*(?P<ampm>am|pm)(?:\s*\((?P<tz>[^)]+)\))?",
    re.IGNORECASE)


def parse_claude_limit(text: str, at: datetime) -> dict[str, Any] | None:
    """Reset time from e.g. "You've hit your 5-hour limit · resets 8:10am (Europe/Berlin)"."""
    m = _CLAUDE_LIMIT.search(text or "")
    if not m:
        return None
    try:
        zone = ZoneInfo(m["tz"]) if m["tz"] else timezone.utc
    except (KeyError, ValueError):
        zone = timezone.utc
    hour = int(m["hour"]) % 12 + (12 if m["ampm"].lower() == "pm" else 0)
    local = at.astimezone(zone)
    if m["date"]:
        try:
            day = datetime.strptime(f"{m['date']} {local.year}", "%b %d %Y").date()
        except ValueError:
            return None
        reset = datetime(day.year, day.month, day.day, hour, int(m["minute"] or 0), tzinfo=zone)
        if reset < local:
            reset = reset.replace(year=reset.year + 1)
    else:
        reset = local.replace(hour=hour, minute=int(m["minute"] or 0), second=0, microsecond=0)
        if reset <= local:
            reset += timedelta(days=1)
    kind = m["kind"].lower()
    name, minutes = ("5h", 300) if kind.startswith("5") else (("7d", 10080) if "week" in kind else (kind, None))
    return {"window": name, "minutes": minutes, "resets_at": reset.astimezone(timezone.utc)}


def claude_log_events(root: Path | None = None, since: datetime | None = None,
                      now: datetime | None = None) -> Iterator[tuple[dict[str, Any], dict[str, Any]]]:
    """Yield (snapshot, outcome) from Claude Code project logs.

    A real answer is outcome ``ok``; a synthetic ``rate_limit`` answer is
    outcome ``limit`` and also a snapshot: window exhausted until its reset.
    """
    root = root or Path.home() / ".claude/projects"
    for path in _recent_files(root, since):
        with path.open("rb") as handle:
            for raw in handle:
                if b'"assistant"' not in raw:
                    continue
                try:
                    event = json.loads(raw)
                except ValueError:
                    continue
                if event.get("type") != "assistant":
                    continue
                at = _parse_time(event.get("timestamp"))
                if at is None or (since and at < since):
                    continue
                message = event.get("message") or {}
                model = str(message.get("model") or "")
                if event.get("isApiErrorMessage"):
                    if event.get("error") != "rate_limit":
                        continue
                    content = message.get("content")
                    text = " ".join(c.get("text", "") for c in content if isinstance(c, dict)) \
                        if isinstance(content, list) else str(content or "")
                    parsed = parse_claude_limit(text, at)
                    snap = {}
                    if parsed:
                        snap = snapshot(
                            "claude", source="claude code limit message", source_kind="limit_message",
                            evidence_at=at,
                            windows=[_window(parsed["window"], parsed["minutes"], 100, parsed["resets_at"])],
                            reached=True, now=now)
                    yield snap, {"provider": "claude", "at": _iso(at), "result": "limit"}
                elif model and not model.startswith("<"):
                    yield {}, {"provider": "claude", "at": _iso(at), "result": "ok", "model": model}


# ------------------------------------------------------------------ Grok

def grok_log_events(path: Path | None = None, since: datetime | None = None,
                    now: datetime | None = None) -> Iterator[tuple[dict[str, Any], dict[str, Any]]]:
    """Yield (snapshot, outcome) from ``~/.grok/logs/unified.jsonl``."""
    path = path or Path.home() / ".grok/logs/unified.jsonl"
    if not path.is_file():
        return
    user = model = None
    with path.open("rb") as handle:
        for raw in handle:
            try:
                event = json.loads(raw)
            except ValueError:
                continue
            msg, ctx = event.get("msg"), event.get("ctx") or {}
            if not isinstance(ctx, dict):
                continue
            if msg == "auth init user_info check" and ctx.get("user_id"):
                user = str(ctx["user_id"])
                continue
            if msg == "model catalog: notifying clients" and ctx.get("current_model_id"):
                model = str(ctx["current_model_id"])
                continue
            at = _parse_time(event.get("ts"))
            if at is None or (since and at < since):
                continue
            if msg == "billing: fetched credits config":
                config = ctx.get("config") or {}
                period = config.get("currentPeriod") or {}
                start, end = _parse_time(period.get("start")), _parse_time(period.get("end"))
                minutes = int((end - start).total_seconds() // 60) if start and end else None
                kind = str(period.get("type") or "")
                name = "7d" if "WEEKLY" in kind else _name_for(minutes)
                notes = []
                if (config.get("prepaidBalance") or {}).get("val") == 0:
                    notes.append("prepaid balance 0")
                snap = snapshot(
                    "grok", source="grok cli billing credits config", source_kind="cli_log",
                    evidence_at=at, windows=[_window(name, minutes, config.get("creditUsagePercent"), end)],
                    plan=ctx.get("subscriptionTier"),
                    plan_confidence=CONFIRMED if ctx.get("subscriptionTier") else UNKNOWN,
                    account=account_ref("grok", user), model=model, notes=notes, now=now)
                yield snap, {}
            elif msg == "shell.turn.inference_done":
                yield {}, {"provider": "grok", "at": _iso(at), "result": "ok"}
            elif msg == "shell.turn.inference_failed" and ctx.get("status_code") == 402:
                yield {}, {"provider": "grok", "at": _iso(at), "result": "limit"}


def _latest(events: Iterable[tuple[dict[str, Any], dict[str, Any]]]) -> dict[str, Any] | None:
    latest = None
    for snap, _ in events:
        if snap and (latest is None or snap["evidence_at"] >= latest["evidence_at"]):
            latest = snap
    return latest


# ------------------------------------------------------ forecast / check

def forecast(snap: dict[str, Any] | None, at: datetime, max_age: timedelta = MAX_AGE) -> dict[str, str]:
    """Does a new job still fit? ``fits`` / ``tight`` / ``no`` / ``unknown``."""
    evidence = _parse_time((snap or {}).get("evidence_at"))
    if not snap or evidence is None or not snap.get("windows"):
        return {"forecast": UNKNOWN, "basis": UNKNOWN}
    open_windows = [w for w in snap["windows"]
                    if not (_parse_time(w.get("resets_at")) and _parse_time(w["resets_at"]) <= at)]
    # A reached flag without a 100 % window blocks until every window has reset.
    flag_only = snap.get("limit_status") == "exhausted" and not any(
        (w.get("used_percent") or 0) >= 100 for w in snap["windows"])
    if any((w.get("used_percent") or 0) >= 100 for w in open_windows) or (
            flag_only and len(open_windows) == len(snap["windows"])):
        return {"forecast": "no", "basis": CONFIRMED}
    if at - evidence > max_age:
        return {"forecast": UNKNOWN, "basis": "stale"}
    if not open_windows:
        return {"forecast": "fits", "basis": ESTIMATED}
    known = [w["used_percent"] for w in open_windows if w.get("used_percent") is not None]
    if not known:
        return {"forecast": UNKNOWN, "basis": UNKNOWN}
    basis = CONFIRMED if len(known) == len(open_windows) else ESTIMATED
    return {"forecast": "tight" if max(known) >= TIGHT_PERCENT else "fits", "basis": basis}


_VERDICT = {("no", "limit"): "correct_block", ("no", "ok"): "false_alarm",
            ("fits", "ok"): "correct_fit", ("tight", "ok"): "correct_fit",
            ("fits", "limit"): "false_availability", ("tight", "limit"): "warned_limit"}


def evaluate(events: Iterable[tuple[dict[str, Any], dict[str, Any]]],
             max_age: timedelta = MAX_AGE) -> dict[str, Any]:
    """Compare each real outcome with the forecast from the last earlier snapshot."""
    snaps, outcomes = [], []
    for snap, outcome in events:
        if snap:
            snaps.append(snap)
        if outcome:
            outcomes.append(outcome)
    snaps.sort(key=lambda s: s["evidence_at"])
    counts: dict[str, int] = {}
    details = []
    for outcome in sorted(outcomes, key=lambda o: o["at"]):
        prior = [s for s in snaps if s["evidence_at"] < outcome["at"]]
        at = _parse_time(outcome["at"])
        guess = forecast(prior[-1] if prior else None, at, max_age)
        verdict = _VERDICT.get((guess["forecast"], outcome["result"]), "no_data")
        counts[verdict] = counts.get(verdict, 0) + 1
        if verdict != "correct_fit" and (outcome["result"] == "limit" or verdict == "false_alarm"):
            last = prior[-1] if prior else {}
            details.append({"at": outcome["at"], "result": outcome["result"], "verdict": verdict,
                            "forecast": guess, "snapshot_at": last.get("evidence_at"),
                            "snapshot_windows": last.get("windows")})
    return {"outcomes": len(outcomes), "snapshots": len(snaps), "counts": counts,
            "details": details[:20]}


# ------------------------------------------------------------- entrypoints

def collect(providers: Iterable[str] = PROVIDERS, *, live: bool = True, codex: str = "codex",
            since: datetime | None = None, now: datetime | None = None) -> list[dict[str, Any]]:
    """Current snapshot per provider and source, newest evidence only."""
    now = now or datetime.now(timezone.utc)
    since = since or now - timedelta(days=8)
    out: list[dict[str, Any]] = []
    for provider in providers:
        if provider == "codex":
            if live:
                out.append(codex_rpc(codex, now=now))
            latest = codex_log_latest(since=since, now=now)
            if latest:
                out.append(latest)
        elif provider == "claude":
            out.append(claude_cache(now=now))
            latest = _latest(claude_log_events(since=since, now=now))
            if latest:
                out.append(latest)
        elif provider == "grok":
            latest = _latest(grok_log_events(since=since, now=now))
            out.append(latest or snapshot("grok", source="grok cli billing credits config",
                                          source_kind="cli_log", evidence_at=None, windows=[],
                                          notes=["no billing entry in grok log"], now=now))
    for snap in out:
        snap["forecast_now"] = forecast(snap, now)
    return out


def evaluate_logs(providers: Iterable[str] = PROVIDERS, *, since: datetime,
                  now: datetime | None = None) -> dict[str, Any]:
    readers = {"codex": codex_log_events, "claude": claude_log_events, "grok": grok_log_events}
    return {p: evaluate(readers[p](since=since, now=now)) for p in providers}


def log_path() -> Path:
    from tollgate.paths import user_dir
    return user_dir() / LOG_NAME


def append_log(rows: Iterable[dict[str, Any]], path: Path | None = None) -> Path:
    path = path or log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return path
