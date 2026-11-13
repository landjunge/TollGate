"""HTTP helpers for key probes (rate-limit headers, safe JSON)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


def parse_rate_headers(headers: Any) -> dict[str, Any]:
    """Parse Brave/Cloudflare-style X-RateLimit-* multi-window headers."""
    if headers is None:
        return {}

    def _get(name: str) -> str:
        # email.message.Message / http.client.HTTPMessage are case-insensitive
        try:
            return (headers.get(name) or headers.get(name.lower()) or "").strip()
        except Exception:  # noqa: BLE001
            return ""

    limit = _get("X-RateLimit-Limit")
    remaining = _get("X-RateLimit-Remaining")
    reset = _get("X-RateLimit-Reset")
    policy = _get("X-RateLimit-Policy")
    if not any((limit, remaining, reset, policy)):
        return {}

    def _split_ints(s: str) -> list[int | None]:
        out: list[int | None] = []
        for part in s.split(","):
            part = part.strip()
            if not part:
                continue
            try:
                out.append(int(part))
            except ValueError:
                out.append(None)
        return out

    lims = _split_ints(limit)
    rems = _split_ints(remaining)
    resets = _split_ints(reset)
    # Brave convention: first = per-second, second = monthly (if present)
    out: dict[str, Any] = {"raw": {}}
    if limit:
        out["raw"]["limit"] = limit
    if remaining:
        out["raw"]["remaining"] = remaining
    if reset:
        out["raw"]["reset"] = reset
    if policy:
        out["raw"]["policy"] = policy
    if len(lims) >= 1:
        out["per_second_limit"] = lims[0]
    if len(lims) >= 2:
        out["period_limit"] = lims[1]
    if len(rems) >= 1:
        out["per_second_remaining"] = rems[0]
    if len(rems) >= 2:
        out["period_remaining"] = rems[1]
    if len(resets) >= 1:
        out["per_second_reset_s"] = resets[0]
    if len(resets) >= 2:
        out["period_reset_s"] = resets[1]
    return out


def http_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
    timeout: float = 20.0,
) -> dict[str, Any]:
    """
    Perform HTTP request → {ok, status, data, error, rate}.

    Never raises for HTTP errors.
    """
    data = None if body is None else json.dumps(body).encode("utf-8")
    hdrs = dict(headers or {})
    if body is not None:
        hdrs.setdefault("Content-Type", "application/json")
    hdrs.setdefault("Accept", "application/json")
    # Default UA — Cloudflare 1010 blocks empty/python-urllib signatures on some hosts
    hdrs.setdefault(
        "User-Agent",
        "Mozilla/5.0 (compatible; Tollgate/0.1; +https://github.com/landjunge/TollGate)",
    )
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                parsed: Any = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                parsed = {"raw": raw[:400]}
            return {
                "ok": 200 <= resp.status < 300,
                "status": resp.status,
                "data": parsed,
                "error": None,
                "rate": parse_rate_headers(resp.headers),
            }
    except urllib.error.HTTPError as e:
        try:
            raw = e.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                parsed = {"raw": raw[:400]}
        except Exception:  # noqa: BLE001
            parsed = {}
            raw = str(e)
        err_msg = None
        if isinstance(parsed, dict):
            if isinstance(parsed.get("error"), dict):
                err_msg = parsed["error"].get("message") or str(parsed["error"])
            elif parsed.get("detail"):
                err_msg = str(parsed.get("detail"))[:300]
            elif parsed.get("base_resp"):
                err_msg = str(parsed["base_resp"])[:300]
        if not err_msg:
            err_msg = f"HTTP {e.code}: {raw[:200] if isinstance(raw, str) else e}"
        return {
            "ok": False,
            "status": e.code,
            "data": parsed,
            "error": err_msg,
            "rate": parse_rate_headers(getattr(e, "headers", None)),
        }
    except Exception as e:  # noqa: BLE001
        return {
            "ok": False,
            "status": None,
            "data": None,
            "error": str(e),
            "rate": {},
        }


def iter_sse_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
    timeout: float = 120.0,
):
    """
    Stream an SSE HTTP response; yield parsed events.

    Yields dicts::

        {"ok": True, "data": <json dict from data: line>}
        {"ok": True, "done": True}          # upstream sent [DONE]
        {"ok": False, "error": str, "status": int|None}

    Never raises for network/HTTP errors (yields one error event).
    """
    data = None if body is None else json.dumps(body).encode("utf-8")
    hdrs = dict(headers or {})
    if body is not None:
        hdrs.setdefault("Content-Type", "application/json")
    hdrs.setdefault("Accept", "text/event-stream")
    hdrs.setdefault(
        "User-Agent",
        "Mozilla/5.0 (compatible; Tollgate/0.1; +https://github.com/landjunge/TollGate)",
    )
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method.upper())
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        try:
            raw = e.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                parsed = {"raw": raw[:400]}
        except Exception:  # noqa: BLE001
            parsed = {}
            raw = str(e)
        err_msg = None
        if isinstance(parsed, dict):
            if isinstance(parsed.get("error"), dict):
                err_msg = parsed["error"].get("message") or str(parsed["error"])
            elif parsed.get("detail"):
                err_msg = str(parsed.get("detail"))[:300]
        if not err_msg:
            err_msg = f"HTTP {e.code}: {(raw[:200] if isinstance(raw, str) else str(e))}"
        yield {
            "ok": False,
            "status": e.code,
            "error": err_msg,
            "data": parsed,
            "rate": parse_rate_headers(getattr(e, "headers", None)),
        }
        return
    except Exception as e:  # noqa: BLE001
        yield {"ok": False, "status": None, "error": str(e), "data": None, "rate": {}}
        return

    buf = ""
    try:
        while True:
            chunk = resp.read(1024)
            if not chunk:
                break
            if isinstance(chunk, bytes):
                buf += chunk.decode("utf-8", errors="replace")
            else:
                buf += str(chunk)
            while "\n" in buf:
                line, buf = buf.split("\n", 1)
                line = line.rstrip("\r")
                if not line or line.startswith(":"):
                    continue
                if not line.startswith("data:"):
                    continue
                payload = line[5:].lstrip()
                if payload == "[DONE]":
                    yield {"ok": True, "done": True}
                    return
                try:
                    obj = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict):
                    yield {"ok": True, "data": obj}
    except Exception as e:  # noqa: BLE001
        yield {"ok": False, "status": None, "error": str(e), "data": None}
    finally:
        try:
            resp.close()
        except Exception:  # noqa: BLE001
            pass
    yield {"ok": True, "done": True}
