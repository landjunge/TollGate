"""OpenRouter — multi-key chain, credit probe, free-model policy."""

from __future__ import annotations

import os
from typing import Any

from tollgate.secrets import is_usable_api_key
from tollgate.base import as_status, get_env, mask_secret
from tollgate.httputil import http_json
from tollgate.research_notes import research_for

BASE = "https://openrouter.ai/api/v1"

# Prefer primary, then known hub aliases (legacy keys often 401 User not found)
ENV_CHAIN = (
    "OPENROUTER_API_KEY",
    "OPENROUTER_API_KEY_GNOM_CONFIG",
    "OPENROUTER_API_KEY_GNOMHUB",
    "OPENROUTER_API_KEY_HERMES",
)


def free_only() -> bool:
    return get_env("OPENROUTER_FREE_ONLY", default="0").lower() in ("1", "true", "yes")


def resolve_key() -> tuple[str, str]:
    """Return (env_name, key) for first usable non-empty key in chain."""
    for name in ENV_CHAIN:
        v = (os.environ.get(name) or "").strip()
        if is_usable_api_key(v):
            return name, v
    return "", ""


def credits(*, force_env: str | None = None) -> dict[str, Any]:
    """
    GET /api/v1/key — credit limits for the active key.

    Tries env chain until one authenticates (skips dead legacy keys).
    """
    tried: list[dict[str, Any]] = []
    names = [force_env] if force_env else list(ENV_CHAIN)
    for name in names:
        if not name:
            continue
        key = (os.environ.get(name) or "").strip()
        if not is_usable_api_key(key):
            continue
        r = http_json(
            "GET",
            f"{BASE}/key",
            headers={"Authorization": f"Bearer {key}"},
        )
        entry = {"env": name, "status": r["status"], "ok": r["ok"], "error": r.get("error")}
        tried.append(entry)
        if not r["ok"]:
            continue
        data = (r["data"] or {}).get("data") if isinstance(r["data"], dict) else None
        if not isinstance(data, dict):
            data = r["data"] if isinstance(r["data"], dict) else {}
        return {
            "ok": True,
            "env": name,
            "label": data.get("label"),
            "limit": data.get("limit"),
            "limit_remaining": data.get("limit_remaining"),
            "usage": data.get("usage"),
            "usage_daily": data.get("usage_daily"),
            "usage_monthly": data.get("usage_monthly"),
            "is_free_tier": data.get("is_free_tier"),
            "free_only_policy": free_only(),
            "research": research_for("openrouter").get("limits"),
            "tried": tried,
        }
    return {
        "ok": False,
        "error": "no live OpenRouter key in chain",
        "tried": tried,
        "research": research_for("openrouter").get("limits"),
    }


def models(*, free_only_filter: bool | None = None) -> dict[str, Any]:
    name, key = resolve_key()
    if not key:
        return {"ok": False, "error": "no OpenRouter key", "models": []}
    r = http_json(
        "GET",
        f"{BASE}/models",
        headers={"Authorization": f"Bearer {key}"},
    )
    if not r["ok"]:
        return {"ok": False, "error": r["error"], "models": []}
    data = r["data"] if isinstance(r["data"], dict) else {}
    ids = [m.get("id") for m in (data.get("data") or []) if isinstance(m, dict)]
    fo = free_only() if free_only_filter is None else free_only_filter
    free_ids = [i for i in ids if isinstance(i, str) and i.endswith(":free")]
    return {
        "ok": True,
        "env": name,
        "total": len(ids),
        "free_count": len(free_ids),
        "free_models": free_ids[:40],
        "free_only_policy": fo,
        "sample": (free_ids if fo else ids)[:15],
    }


def chat(
    messages: list[dict[str, str]] | str = "hi",
    *,
    model: str = "openrouter/free",
    max_tokens: int = 1024,
    temperature: float = 0.7,
    **_kw: Any,
) -> dict[str, Any]:
    """OpenRouter chat/completions (prefer :free models when free_only)."""
    name, key = resolve_key()
    if not key:
        return {"ok": False, "error": "no OpenRouter key in env chain"}
    if isinstance(messages, str):
        msgs: list[dict[str, str]] = [{"role": "user", "content": messages[:8000]}]
    else:
        msgs = [
            {"role": str(m.get("role") or "user"), "content": str(m.get("content") or "")[:16000]}
            for m in (messages or [])
            if isinstance(m, dict)
        ]
        if not msgs:
            msgs = [{"role": "user", "content": "hi"}]
    mid = (model or "openrouter/free").strip()
    if free_only() and ":" in mid and not mid.endswith(":free") and "free" not in mid.lower():
        return {
            "ok": False,
            "error": f"OPENROUTER_FREE_ONLY blocks paid model {mid}",
            "model": mid,
        }
    r = http_json(
        "POST",
        f"{BASE}/chat/completions",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/landjunge/TollGate",
            "X-Title": "Tollgate",
        },
        body={
            "model": mid,
            "messages": msgs,
            "stream": False,
            "temperature": float(temperature),
            "max_tokens": max(1, min(128_000, int(max_tokens or 1024))),
        },
        timeout=120.0,
    )
    if not r.get("ok"):
        return {
            "ok": False,
            "error": r.get("error") or f"HTTP {r.get('status')}",
            "status": r.get("status"),
            "model": mid,
            "provider": "openrouter",
            "env": name,
        }
    data = r.get("data") if isinstance(r.get("data"), dict) else {}
    choices = data.get("choices") or []
    content = ""
    if choices and isinstance(choices[0], dict):
        msg = choices[0].get("message") or {}
        content = str(msg.get("content") or "")
    usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
    return {
        "ok": True,
        "provider": "openrouter",
        "env": name,
        "model": data.get("model") or mid,
        "content": content,
        "usage": usage,
        "prompt_tokens": int(usage.get("prompt_tokens") or 0),
        "completion_tokens": int(usage.get("completion_tokens") or 0),
    }


def status(*, live: bool = False) -> dict[str, Any]:
    name, key = resolve_key()
    masked = {
        "OPENROUTER_API_KEY": mask_secret(get_env("OPENROUTER_API_KEY")),
        "OPENROUTER_FREE_ONLY": "1" if free_only() else "0",
        "active_env": name or "(none)",
        "active_key": mask_secret(key),
    }
    if not key:
        return as_status(
            id="openrouter",
            ready=False,
            error="no OpenRouter key in env chain",
            masked=masked,
            detail={"research": research_for("openrouter"), "env_chain": list(ENV_CHAIN)},
        )
    if not live:
        return as_status(
            id="openrouter",
            ready=True,
            masked=masked,
            detail={
                "live": False,
                "free_only": free_only(),
                "note": "live=1 runs GET /key credit probe + skips dead aliases",
            },
        )
    cr = credits()
    if not cr.get("ok"):
        # models may still work with some keys — try
        m = models()
        return as_status(
            id="openrouter",
            ready=bool(m.get("ok")),
            error=cr.get("error"),
            masked=masked,
            detail={"live": True, "credits": cr, "models": m if m.get("ok") else None},
        )
    return as_status(
        id="openrouter",
        ready=True,
        masked={**masked, "active_env": cr.get("env")},
        detail={
            "live": True,
            "limit_remaining": cr.get("limit_remaining"),
            "limit": cr.get("limit"),
            "usage": cr.get("usage"),
            "is_free_tier": cr.get("is_free_tier"),
            "free_only": free_only(),
            "credits": cr,
            "research_limits": research_for("openrouter").get("limits"),
        },
    )
