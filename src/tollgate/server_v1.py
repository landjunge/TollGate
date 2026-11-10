"""
Standalone multi-consumer HTTP surface.

  tollgate serve
  → http://127.0.0.1:8787/docs

Native:
  GET  /v1/health | /v1/auth | /v1/providers | /v1/budget | /v1/usage
  POST /v1/route | /v1/invoke
  GET|POST /v1/config

OpenAI-compatible drop-in:
  GET  /v1/models
  POST /v1/chat/completions
  Authorization: Bearer <consumer_id>:<secret>  (or X-Consumer-Key)

Anthropic-compatible drop-in:
  POST /v1/messages
  x-api-key: <consumer_id>:<secret>  (or Authorization Bearer / X-Consumer-Key)
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field

from tollgate import __version__, get_keys_service, i18n, routed_chat
from tollgate.consumers import auth_status, verify_consumer
from tollgate.gateway.context import RequestClass, RequestContext
from tollgate.gateway.entry import gateway_call
from tollgate.metrics import render_prometheus
from tollgate.openai_compat import (
    list_models_openai,
    map_tollgate_error,
    normalize_messages,
    openai_error,
    parse_bearer,
    resolve_intent,
    response_headers,
    to_openai_completion,
)


def _bootstrap_env() -> None:
    try:
        from tollgate.app_config import load_config
        from tollgate.config_validate import assert_config_or_raise
        from tollgate.paths import data_home, pin_data_home_env, user_dir
        from tollgate.secrets import ensure_env_from_key_txt, load_keys, parse_key_file

        pin_data_home_env()
        ensure_env_from_key_txt()
        load_keys()
        kp = user_dir() / "Key.txt"
        if not kp.is_file():
            kp = data_home() / "User" / "Key.txt"
        if kp.is_file():
            for k, v in parse_key_file(kp.read_text(encoding="utf-8")).items():
                os.environ.setdefault(k, v)
        # Config validation at process start (strict via env)
        cfg = load_config(force=True)
        strict = (os.environ.get("TOLLGATE_STRICT_CONFIG") or "").strip().lower() in (
            "1",
            "true",
            "yes",
        )
        assert_config_or_raise(cfg, strict=strict)
    except ValueError:
        raise
    except Exception as e:  # noqa: BLE001
        from tollgate.soft_fail import soft_fail

        soft_fail("bootstrap", e, op="serve", audit=False)


_bootstrap_env()


LANGUAGE_COOKIE = "tollgate_lang"
REGISTER_COOKIE = "tollgate_register"

@asynccontextmanager
async def _lifespan(_app: FastAPI):
    from tollgate.consumers import refuse_open_public_bind

    refuse_open_public_bind()
    yield


app = FastAPI(
    title="Tollgate",
    version=__version__,
    lifespan=_lifespan,
    description=(
        "Tollgate — AI reliability & control plane. "
        "Protect · Route · Prove (chaos failover tests). "
        "https://github.com/landjunge/tollgate"
    ),
)


def _require(
    x_consumer_key: str | None,
    x_consumer_id: str | None = None,
    *,
    need_admin: bool = False,
    authorization: str | None = None,
    x_api_key: str | None = None,
) -> dict[str, Any]:
    # Prefer X-Consumer-Key, then Anthropic x-api-key, then Bearer (OpenAI SDK)
    key = x_consumer_key
    if not (key or "").strip():
        key = (x_api_key or "").strip() or None
    if not (key or "").strip():
        key = parse_bearer(authorization)
    auth = verify_consumer(key, x_consumer_id, need_admin=need_admin)
    if not auth.get("ok"):
        raise HTTPException(status_code=401, detail=auth.get("error") or "unauthorized")
    return auth


class RouteBody(BaseModel):
    intent: str = "llm"
    tokens_est: int = Field(0, ge=0)
    chars_est: int = Field(0, ge=0)
    prefer_free: bool | None = None
    live: bool = False


class InvokeBody(BaseModel):
    provider: str
    op: str = "status"
    arguments: dict[str, Any] = Field(default_factory=dict)
    tokens_est: int = Field(0, ge=0)
    chars_est: int = Field(0, ge=0)
    tool_calls_est: int = Field(
        0,
        ge=0,
        description="Agent loop depth this turn — enforced via max_tool_calls envelope",
    )
    model: str = ""
    agent_id: str = ""
    job_id: str = ""
    session_id: str = ""
    request_class: str = "interactive"
    allow_paid_fallback: bool = False


def _security_surface() -> dict[str, Any]:
    """Bind + open-mode hints for dashboard / doctor (no secrets)."""
    import os

    from tollgate.consumers import auth_required

    host = (os.environ.get("HOST") or "127.0.0.1").strip() or "127.0.0.1"
    port = int(os.environ.get("PORT") or "8787")
    open_mode = not auth_required()
    bind_public = host in ("0.0.0.0", "::", "[::]", "*")
    warning = None
    if open_mode and bind_public:
        warning = (
            "OPEN MODE on a public bind — any client can admit traffic and "
            "mutate config. Use HOST=127.0.0.1 or enable consumers auth."
        )
    elif open_mode:
        warning = (
            "Open auth mode (local desk) — fine on localhost only. "
            "Do not expose this port to the internet."
        )
    return {
        "open_mode": open_mode,
        "bind_host": host,
        "bind_port": port,
        "bind_is_public": bind_public,
        "dashboard_url": f"http://{host if host not in ('0.0.0.0', '::', '[::]') else '127.0.0.1'}:{port}/dashboard",
        "warning": warning,
    }


@app.get("/v1/health")
def health() -> dict[str, Any]:
    from tollgate.freeze import freeze_status
    from tollgate.gateway.circuit import get_circuits
    from tollgate.paths import path_snapshot

    ks = get_keys_service()
    fr = freeze_status()
    return {
        "ok": not fr.get("frozen"),
        "service": "tollgate",
        "product": "Tollgate",
        "version": __version__,
        "extractable": True,
        "multi_consumer": True,
        "portable": path_snapshot(),
        "auth": auth_status(),
        "security": _security_surface(),
        "app": ks.app_status(),
        "freeze": fr,
        "circuits": get_circuits().snapshot()[:30],
        "metrics": "/metrics",
        "control": "/v1/control",
        "status": "/v1/status",
        "audit": "/v1/audit",
        "report": "/v1/report",
        "alerts": "/v1/alerts",
        "freeze_path": "/v1/freeze",
        "dashboard": "/dashboard",
    }


def _metrics_authorized(
    authorization: str | None,
    x_consumer_key: str | None,
    x_api_key: str | None,
    x_metrics_token: str | None,
) -> bool:
    """
    Metrics access policy (v0.3):

    - TOLLGATE_METRICS_PUBLIC=1 → always open (explicit opt-out of protection)
    - TOLLGATE_METRICS_TOKEN set → Bearer / X-Metrics-Token must match
    - else if consumers auth required → any valid consumer key
    - else open mode (local desk) → open
    """
    if (os.environ.get("TOLLGATE_METRICS_PUBLIC") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    ):
        return True

    token = (os.environ.get("TOLLGATE_METRICS_TOKEN") or "").strip()
    if token:
        presented = (x_metrics_token or "").strip()
        if not presented:
            # Authorization: Bearer <token> or Bearer id:secret handled below
            presented = parse_bearer(authorization) or ""
        if presented and hmac_compare(presented, token):
            return True
        # also allow full consumer key when token mode is on? no — token only
        return False

    from tollgate.consumers import auth_required

    if not auth_required():
        return True

    # Auth mode: any valid consumer (scrape with desk key)
    try:
        _require(x_consumer_key, need_admin=False, authorization=authorization, x_api_key=x_api_key)
        return True
    except HTTPException:
        return False


def hmac_compare(a: str, b: str) -> bool:
    import hmac as _hmac

    ba, bb = (a or "").encode("utf-8"), (b or "").encode("utf-8")
    if len(ba) != len(bb):
        return False
    return _hmac.compare_digest(ba, bb)


@app.get("/metrics")
def metrics(
    authorization: str | None = Header(None),
    x_consumer_key: str | None = Header(None, alias="X-Consumer-Key"),
    x_api_key: str | None = Header(None, alias="x-api-key"),
    x_metrics_token: str | None = Header(None, alias="X-Metrics-Token"),
) -> PlainTextResponse:
    """
    Prometheus text exposition (ledger, circuits, cache, portable).

    Protected when auth mode is on or TOLLGATE_METRICS_TOKEN is set.
    Opt out: TOLLGATE_METRICS_PUBLIC=1.
    """
    if not _metrics_authorized(
        authorization, x_consumer_key, x_api_key, x_metrics_token
    ):
        raise HTTPException(
            status_code=401,
            detail=(
                "metrics unauthorized — pass consumer key, "
                "X-Metrics-Token / Bearer TOLLGATE_METRICS_TOKEN, "
                "or set TOLLGATE_METRICS_PUBLIC=1"
            ),
        )
    return PlainTextResponse(
        render_prometheus(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@app.get("/v1/auth")
def auth_info(
    x_consumer_key: str | None = Header(default=None, alias="X-Consumer-Key"),
    x_consumer_id: str | None = Header(default=None, alias="X-Consumer-Id"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    """
    Public: only whether auth is required (no consumer enumeration).

    Authenticated (or open mode) callers get consumer list / counts for desk UX.
    """
    st = auth_status()
    public = {
        "ok": True,
        "required": st["required"],
        "header": "X-Consumer-Key: <id>:<secret>",
    }
    if not st["required"]:
        # Open desk mode — full status is fine (local trust boundary)
        public["consumers_n"] = st["consumers_n"]
        public["consumers"] = st["consumers"]
        public["mode"] = "open"
        return public
    # Auth mode: details only when credentials valid
    try:
        auth = _require(
            x_consumer_key, x_consumer_id, need_admin=False, authorization=authorization
        )
    except HTTPException:
        return public
    public["consumers_n"] = st["consumers_n"]
    public["consumers"] = st["consumers"]
    public["mode"] = "auth"
    public["viewer"] = auth.get("consumer")
    public["admin"] = bool(auth.get("admin"))
    return public


@app.get("/v1/control")
def control_plane_view(
    x_consumer_key: str | None = Header(default=None, alias="X-Consumer-Key"),
    x_consumer_id: str | None = Header(default=None, alias="X-Consumer-Id"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    """
    Product control pane: provider health, consumer burn, headline.

    Protect · Route · Prove — not a secret dump.
    """
    auth = _require(x_consumer_key, x_consumer_id, authorization=authorization)
    from tollgate.control_plane import control_snapshot

    out = control_snapshot()
    out["consumer"] = auth["consumer"]
    return out


@app.get("/v1/status")
def status_view(
    format: str = Query("json", description="json | text"),
    x_consumer_key: str | None = Header(default=None, alias="X-Consumer-Key"),
    x_consumer_id: str | None = Header(default=None, alias="X-Consumer-Id"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> Any:
    """Compact desk status (freeze · resilience · spend · attention)."""
    auth = _require(x_consumer_key, x_consumer_id, authorization=authorization)
    from tollgate.status import desk_status, format_status_text

    fmt = (format or "json").strip().lower()
    if fmt in ("text", "txt", "md"):
        return PlainTextResponse(format_status_text(), media_type="text/plain; charset=utf-8")
    out = desk_status()
    out["viewer"] = auth["consumer"]
    return out


@app.get("/v1/resilience")
def resilience_view(
    x_consumer_key: str | None = Header(default=None, alias="X-Consumer-Key"),
    x_consumer_id: str | None = Header(default=None, alias="X-Consumer-Id"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    """AI Resilience Score 0–100 + warnings (Prove pillar)."""
    auth = _require(x_consumer_key, x_consumer_id, authorization=authorization)
    from tollgate.resilience import resilience_score

    out = resilience_score()
    out["consumer"] = auth["consumer"]
    return out


@app.get("/v1/chaos")
def chaos_status_http(
    x_consumer_key: str | None = Header(default=None, alias="X-Consumer-Key"),
    x_consumer_id: str | None = Header(default=None, alias="X-Consumer-Id"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    """Active chaos injects + last failover test report."""
    auth = _require(x_consumer_key, x_consumer_id, authorization=authorization)
    from tollgate.chaos import status as chaos_status

    out = chaos_status()
    out["consumer"] = auth["consumer"]
    return out


class ChaosTestBody(BaseModel):
    provider: str = "opencode_zen"
    requests: int = Field(8, ge=1, le=50)
    intent: str = "free_llm"
    live_chat: bool = False


@app.post("/v1/chaos/test")
def chaos_test_http(
    body: ChaosTestBody,
    x_consumer_key: str | None = Header(default=None, alias="X-Consumer-Key"),
    x_consumer_id: str | None = Header(default=None, alias="X-Consumer-Id"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    """Run failover chaos test (Prove) — admin when auth mode."""
    auth = _require(
        x_consumer_key, x_consumer_id, need_admin=True, authorization=authorization
    )
    from tollgate.chaos import run_failover_test

    rep = run_failover_test(
        body.provider,
        intent=body.intent or "free_llm",
        requests=int(body.requests or 8),
        live_chat=bool(body.live_chat),
    )
    rep["viewer"] = auth["consumer"]
    return rep


@app.get("/v1/certificate")
def certificate_http(
    application: str = Query(""),
    x_consumer_key: str | None = Header(default=None, alias="X-Consumer-Key"),
    x_consumer_id: str | None = Header(default=None, alias="X-Consumer-Id"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    """AI Reliability Report scorecard for the Control Room UI."""
    auth = _require(x_consumer_key, x_consumer_id, authorization=authorization)
    from tollgate.certificate import build_certificate

    out = build_certificate(application=application or "")
    out["viewer"] = auth["consumer"]
    return out


@app.get("/v1/audit")
def audit_view(
    limit: int = Query(40, ge=1, le=500),
    event: str = Query("", description="Filter: admit_deny | usage | …"),
    consumer: str = Query("", description="Consumer / agent lane id"),
    provider: str = Query(""),
    summary: bool = Query(False, description="Return aggregates instead of event list"),
    x_consumer_key: str | None = Header(default=None, alias="X-Consumer-Key"),
    x_consumer_id: str | None = Header(default=None, alias="X-Consumer-Id"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    """
    Query append-only audit trail (denies, usage) — ops only, no secrets.

    Explains *who* was stopped and *why* (Protect pillar evidence).
    """
    auth = _require(x_consumer_key, x_consumer_id, authorization=authorization)
    from tollgate.audit_log import audit_summary, query_audit

    if summary:
        out = audit_summary()
    else:
        out = query_audit(
            limit=limit,
            event=event,
            consumer=consumer,
            provider=provider,
        )
    out["viewer"] = auth["consumer"]
    return out


@app.get("/v1/report")
def report_view(
    format: str = Query("json", description="json | md"),
    x_consumer_key: str | None = Header(default=None, alias="X-Consumer-Key"),
    x_consumer_id: str | None = Header(default=None, alias="X-Consumer-Id"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> Any:
    """
    Daily operator report — Protect · Route · Prove evidence in one response.

    ``format=md`` returns text/markdown for Slack/status notes.
    """
    auth = _require(x_consumer_key, x_consumer_id, authorization=authorization)
    from tollgate.report import build_report, format_report_markdown

    fmt = (format or "json").strip().lower()
    if fmt in ("md", "markdown", "text"):
        return PlainTextResponse(
            format_report_markdown(),
            media_type="text/markdown; charset=utf-8",
        )
    out = build_report()
    out["viewer"] = auth["consumer"]
    return out


@app.get("/v1/alerts")
def alerts_catalog(
    x_consumer_key: str | None = Header(default=None, alias="X-Consumer-Key"),
    x_consumer_id: str | None = Header(default=None, alias="X-Consumer-Id"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    """List webhook event types + config pointers (no secrets)."""
    auth = _require(x_consumer_key, x_consumer_id, authorization=authorization)
    from tollgate.alerts import event_catalog

    out = event_catalog()
    out["viewer"] = auth["consumer"]
    return out


@app.post("/v1/alerts/test")
def alerts_test(
    x_consumer_key: str | None = Header(default=None, alias="X-Consumer-Key"),
    x_consumer_id: str | None = Header(default=None, alias="X-Consumer-Id"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    """Force-send a webhook_test event (admin when auth mode)."""
    auth = _require(
        x_consumer_key, x_consumer_id, need_admin=True, authorization=authorization
    )
    from tollgate.alerts import test_webhook

    out = test_webhook(message=f"probe from consumer {auth.get('consumer')}")
    out["viewer"] = auth["consumer"]
    return out


class FreezeBody(BaseModel):
    frozen: bool = True
    reason: str = ""


@app.get("/v1/freeze")
def freeze_get(
    x_consumer_key: str | None = Header(default=None, alias="X-Consumer-Key"),
    x_consumer_id: str | None = Header(default=None, alias="X-Consumer-Id"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    """Admission kill-switch status."""
    auth = _require(x_consumer_key, x_consumer_id, authorization=authorization)
    from tollgate.freeze import freeze_status

    out = freeze_status()
    out["viewer"] = auth["consumer"]
    return out


@app.post("/v1/freeze")
def freeze_set(
    body: FreezeBody,
    x_consumer_key: str | None = Header(default=None, alias="X-Consumer-Key"),
    x_consumer_id: str | None = Header(default=None, alias="X-Consumer-Id"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    """Set global admission freeze (admin when auth mode)."""
    auth = _require(
        x_consumer_key, x_consumer_id, need_admin=True, authorization=authorization
    )
    from tollgate.freeze import set_frozen

    out = set_frozen(
        bool(body.frozen),
        reason=body.reason or ("api freeze" if body.frozen else ""),
        by=str(auth.get("consumer") or "api"),
    )
    out["viewer"] = auth["consumer"]
    return out


class CircuitsResetBody(BaseModel):
    provider: str = ""
    all: bool = False


@app.get("/v1/circuits")
def circuits_list(
    x_consumer_key: str | None = Header(default=None, alias="X-Consumer-Key"),
    x_consumer_id: str | None = Header(default=None, alias="X-Consumer-Id"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    """List circuit breaker rows."""
    auth = _require(x_consumer_key, x_consumer_id, authorization=authorization)
    from tollgate.gateway.circuit import get_circuits

    rows = get_circuits().snapshot()
    return {"ok": True, "count": len(rows), "circuits": rows, "viewer": auth["consumer"]}


@app.post("/v1/circuits/reset")
def circuits_reset(
    body: CircuitsResetBody,
    x_consumer_key: str | None = Header(default=None, alias="X-Consumer-Key"),
    x_consumer_id: str | None = Header(default=None, alias="X-Consumer-Id"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    """Reset circuit breakers for a provider or all (admin)."""
    auth = _require(
        x_consumer_key, x_consumer_id, need_admin=True, authorization=authorization
    )
    from tollgate.gateway.circuit import reset_circuits

    if not body.provider and not body.all:
        raise HTTPException(
            status_code=400, detail="provider required or all=true"
        )
    out = reset_circuits(body.provider or "", all_circuits=bool(body.all))
    out["viewer"] = auth["consumer"]
    return out


@app.get("/static/np/{name}")
def dashboard_static(name: str):
    """Read-only shared header assets (fixed whitelist, no path traversal)."""
    import re
    from importlib.resources import files
    from fastapi.responses import Response

    if not re.fullmatch(r"(networkpunkt-appbar[a-z-]*\.(js|css)|networkpunkt-product-header\.js|np-appbar-[a-z0-9-]+-256\.png)", name):
        raise HTTPException(status_code=404, detail="not found")
    path = files("tollgate").joinpath("static/np", name)
    types = {"js": "text/javascript", "css": "text/css", "png": "image/png"}
    return Response(path.read_bytes(), media_type=types[name.rsplit(".", 1)[1]])


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(request: Request) -> HTMLResponse:
    """Human-readable control plane (no SPA build).

    Sprache: ?lang= schlaegt das Cookie, das Cookie schlaegt den Browser.
    Sprachebene: ?mode= schlaegt das Cookie, sonst Klartext. Anders als bei
    der Sprache fragen wir den Browser nicht — Klartext ist der Normalfall
    fuer alle, und wer Fachwoerter will, sagt es einmal.
    Beide Wahlen werden ein Jahr lang gemerkt.
    """
    from tollgate.dashboard_html import dashboard_html

    chosen = request.query_params.get("lang")
    if chosen:
        language = i18n.normalise(chosen)
    else:
        cookie = request.cookies.get(LANGUAGE_COOKIE)
        language = (
            i18n.normalise(cookie)
            if cookie
            else i18n.from_accept_header(request.headers.get("accept-language"))
        )

    chosen_mode = request.query_params.get("mode")
    register = i18n.normalise_register(
        chosen_mode if chosen_mode else request.cookies.get(REGISTER_COOKIE)
    )

    response = HTMLResponse(dashboard_html(language, register))
    if chosen:
        response.set_cookie(
            LANGUAGE_COOKIE,
            language,
            max_age=31536000,
            samesite="lax",
            httponly=False,
        )
    if chosen_mode:
        response.set_cookie(
            REGISTER_COOKIE,
            register,
            max_age=31536000,
            samesite="lax",
            httponly=False,
        )
    return response


@app.get("/v1/providers")
def providers(
    live: bool = Query(False),
    x_consumer_key: str | None = Header(default=None, alias="X-Consumer-Key"),
    x_consumer_id: str | None = Header(default=None, alias="X-Consumer-Id"),
) -> dict[str, Any]:
    auth = _require(x_consumer_key, x_consumer_id)
    out = get_keys_service().inventory(live=live)
    out["consumer"] = auth["consumer"]
    try:
        from tollgate.control_plane import provider_health

        out["health"] = provider_health()
    except Exception as e:  # noqa: BLE001
        from tollgate.soft_fail import soft_fail

        soft_fail("provider_health", e, op="providers")
    return out


@app.get("/v1/budget")
def budget(
    provider: str = Query(""),
    tokens_est: int = Query(0, ge=0),
    chars_est: int = Query(0, ge=0),
    x_consumer_key: str | None = Header(default=None, alias="X-Consumer-Key"),
    x_consumer_id: str | None = Header(default=None, alias="X-Consumer-Id"),
) -> dict[str, Any]:
    auth = _require(x_consumer_key, x_consumer_id)
    ks = get_keys_service()
    from tollgate.limits import check_consumer_limits, consumer_envelope
    from tollgate.usage_ledger import consumer_usage

    cid = auth["consumer"]
    c_lim = check_consumer_limits(cid, tokens_est=tokens_est)
    c_used = consumer_usage(cid)
    if provider.strip():
        return {
            "ok": True,
            "consumer": cid,
            "provider": provider,
            "limits": ks.check_provider_limits(
                provider, tokens_est=tokens_est, chars_est=chars_est
            ),
            "consumer_envelope": consumer_envelope(cid),
            "consumer_limits": c_lim,
            "consumer_usage": c_used,
            "usage": ks.usage(),
        }
    return {
        "ok": True,
        "consumer": cid,
        "consumer_envelope": consumer_envelope(cid),
        "consumer_limits": c_lim,
        "consumer_usage": c_used,
        "usage": ks.usage(),
        "config": ks.get_config().get("config", {}).get("cost_guard"),
    }


@app.post("/v1/route")
def route(
    body: RouteBody,
    explain: bool = Query(True, description="Include why-this-provider explainability"),
    x_consumer_key: str | None = Header(default=None, alias="X-Consumer-Key"),
    x_consumer_id: str | None = Header(default=None, alias="X-Consumer-Id"),
) -> dict[str, Any]:
    auth = _require(x_consumer_key, x_consumer_id)
    from tollgate.limits import check_consumer_scope

    sc = check_consumer_scope(auth["consumer"], intent=body.intent)
    if not sc.get("allowed"):
        return {
            "ok": False,
            "error": sc.get("reason") or "scope denied",
            "error_class": "POLICY_DENY",
            "protection": "scope",
            "consumer": auth["consumer"],
            "intent": body.intent,
        }
    out = get_keys_service().route(
        body.intent,
        tokens_est=body.tokens_est,
        chars_est=body.chars_est,
        live=body.live,
        prefer_free=body.prefer_free,
    )
    out["consumer"] = auth["consumer"]
    if explain:
        try:
            from tollgate.control_plane import explain_route

            out["explain"] = explain_route(out)
        except Exception as e:  # noqa: BLE001
            out["explain"] = {"ok": False, "error": str(e)}
    return out


@app.post("/v1/invoke")
def invoke(
    body: InvokeBody,
    x_consumer_key: str | None = Header(default=None, alias="X-Consumer-Key"),
    x_consumer_id: str | None = Header(default=None, alias="X-Consumer-Id"),
) -> dict[str, Any]:
    """Multi-consumer admit + call + meter."""
    auth = _require(x_consumer_key, x_consumer_id)
    consumer = auth["consumer"]
    try:
        rclass = RequestClass(body.request_class or "interactive")
    except ValueError:
        rclass = RequestClass.INTERACTIVE
    args = dict(body.arguments or {})
    if body.model and "model" not in args:
        args["model"] = body.model
    # tool_calls_est: explicit body field, or count tools/tool_calls in arguments
    tools_est = int(body.tool_calls_est or 0)
    if tools_est <= 0:
        for key in ("tool_calls", "tools", "tool_calls_est"):
            raw = args.get(key)
            if isinstance(raw, list):
                tools_est = len(raw)
                break
            if isinstance(raw, (int, float)) and key == "tool_calls_est":
                tools_est = int(raw)
                break
    ctx = RequestContext(
        agent_id=body.agent_id or consumer,
        consumer=consumer,
        job_id=body.job_id,
        session_id=body.session_id,
        request_class=rclass,
        allow_paid_fallback=body.allow_paid_fallback,
        tool_calls_est=max(0, tools_est),
    )
    out = gateway_call(
        body.provider,
        body.op,
        ctx=ctx,
        tokens_est=body.tokens_est,
        chars_est=body.chars_est,
        model=body.model or str(args.get("model") or ""),
        **args,
    )
    out["consumer"] = consumer
    if tools_est:
        out["tool_calls_est"] = tools_est
    return out


@app.get("/v1/usage")
def usage(
    x_consumer_key: str | None = Header(default=None, alias="X-Consumer-Key"),
    x_consumer_id: str | None = Header(default=None, alias="X-Consumer-Id"),
) -> dict[str, Any]:
    auth = _require(x_consumer_key, x_consumer_id)
    out = get_keys_service().usage()
    if isinstance(out, dict):
        out = dict(out)
        out["consumer"] = auth["consumer"]
    return out


@app.get("/v1/config")
def config_get(
    x_consumer_key: str | None = Header(default=None, alias="X-Consumer-Key"),
    x_consumer_id: str | None = Header(default=None, alias="X-Consumer-Id"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    """Read keys_app.json policy (admin when auth mode)."""
    auth = _require(x_consumer_key, x_consumer_id, need_admin=True, authorization=authorization)
    out = get_keys_service().get_config()
    out["consumer"] = auth["consumer"]
    out["warning"] = (
        "policy config only (no Key.txt secrets); admin scope when auth enabled"
    )
    return out


@app.post("/v1/config")
def config_patch(
    body: dict[str, Any],
    x_consumer_key: str | None = Header(default=None, alias="X-Consumer-Key"),
    x_consumer_id: str | None = Header(default=None, alias="X-Consumer-Id"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    """Deep-merge patch into keys_app.json (admin when auth mode)."""
    auth = _require(x_consumer_key, x_consumer_id, need_admin=True, authorization=authorization)
    if not isinstance(body, dict) or not body:
        raise HTTPException(status_code=400, detail="JSON object patch required")
    patch = (
        body.get("config")
        if isinstance(body.get("config"), dict) and len(body) == 1
        else body
    )
    if not isinstance(patch, dict):
        raise HTTPException(status_code=400, detail="invalid patch")
    out = get_keys_service().set_config(patch)
    if not out.get("ok"):
        raise HTTPException(
            status_code=400,
            detail=out.get("error") or "config validation failed",
        )
    out["consumer"] = auth["consumer"]
    return out


# ── OpenAI-compatible drop-in ─────────────────────────────────────────


class ChatCompletionsBody(BaseModel):
    model: str = "tollgate/auto"
    messages: list[dict[str, Any]] = Field(default_factory=list)
    temperature: float | None = 0.7
    max_tokens: int | None = 1024
    stream: bool = False
    # OpenAI tools schema (optional) — also used as weak tool_calls_est fallback
    tools: list[Any] | None = None
    # Tollgate extras (optional; ignored by OpenAI SDKs)
    intent: str | None = None
    provider: str | None = None
    request_class: str | None = None
    prefer_free: bool | None = None
    user: str | None = None  # OpenAI user field → agent_id hint
    tokens_est: int = Field(0, ge=0, description="Prompt size hint for admit")
    tool_calls_est: int = Field(
        0,
        ge=0,
        description="Agent loop depth this turn — max_tool_calls protection",
    )


@app.get("/v1/models")
def openai_models(
    x_consumer_key: str | None = Header(default=None, alias="X-Consumer-Key"),
    x_consumer_id: str | None = Header(default=None, alias="X-Consumer-Id"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    """OpenAI-compatible model list."""
    _require(x_consumer_key, x_consumer_id, authorization=authorization)
    return list_models_openai()


@app.post("/v1/chat/completions")
def openai_chat_completions(
    body: ChatCompletionsBody,
    x_consumer_key: str | None = Header(default=None, alias="X-Consumer-Key"),
    x_consumer_id: str | None = Header(default=None, alias="X-Consumer-Id"),
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_tool_calls_est: str | None = Header(
        default=None, alias="X-Tollgate-Tool-Calls-Est"
    ),
) -> Any:
    """
    OpenAI-compatible chat completions (admission + route + meter).

    Drop-in::

        export OPENAI_BASE_URL=http://127.0.0.1:8787/v1
        export OPENAI_API_KEY=n8n:secret   # or any label in open mode

    Loop protection: send ``tool_calls_est`` (body) or header
    ``X-Tollgate-Tool-Calls-Est``, or let Tollgate infer depth from tool
    messages in ``messages`` history.

    ``stream: true`` returns SSE — real upstream token stream when the provider
    supports it (deepseek / worker / opencode_zen / openrouter); otherwise
    synthetic chunks from a full completion.
    """
    from tollgate.openai_compat import estimate_tool_calls_est

    auth = _require(x_consumer_key, x_consumer_id, authorization=authorization)
    consumer = auth["consumer"]
    msgs = normalize_messages(body.messages)
    if not msgs:
        err, code = openai_error("messages is required", status=400)
        return JSONResponse(err, status_code=code)

    intent = (body.intent or "").strip()
    prefer_free = body.prefer_free
    if not intent:
        intent, auto_free = resolve_intent(body.model, prefer_free=prefer_free)
        if prefer_free is None:
            prefer_free = auto_free
    else:
        prefer_free = bool(prefer_free) if prefer_free is not None else intent == "free_llm"

    # model may be provider-specific id; empty provider → router picks
    mid = (body.model or "").strip()
    provider = (body.provider or "").strip()
    if mid.startswith("tollgate/"):
        mid = ""  # let router choose
    rclass = (body.request_class or "interactive").strip() or "interactive"
    agent = (body.user or f"openai:{consumer}")[:64]
    max_tok = int(body.max_tokens or 1024)
    temp = float(body.temperature if body.temperature is not None else 0.7)

    # Prefer raw messages for tool_calls inference (normalize strips tool_calls)
    tools_est = estimate_tool_calls_est(
        explicit=int(body.tool_calls_est or 0),
        messages=body.messages,
        tools=body.tools,
        header_val=x_tool_calls_est,
    )
    tok_est = int(body.tokens_est or 0)

    if body.stream:
        from tollgate.chat_stream import start_chat_stream

        started = start_chat_stream(
            msgs,
            intent=intent or "llm",
            model=mid,
            provider=provider,
            max_tokens=max_tok,
            temperature=temp,
            tokens_est=tok_est,
            tool_calls_est=tools_est,
            agent_id=agent,
            consumer=consumer,
            request_class=rclass,
            prefer_free=prefer_free,
            requested_model=body.model or "tollgate",
        )
        if not started.get("ok"):
            err, code, hdrs = map_tollgate_error(started)
            return JSONResponse(err, status_code=code, headers=hdrs or None)
        headers = {
            "Cache-Control": "no-cache",
            "X-Tollgate-Consumer": consumer,
            "X-Tollgate-Stream": str(started.get("mode") or "upstream"),
            "X-Tollgate-Provider": str(started.get("provider") or ""),
        }
        return StreamingResponse(
            started["stream"],
            media_type="text/event-stream",
            headers=headers,
        )

    result = routed_chat(
        msgs,
        intent=intent or "llm",
        model=mid,
        provider=provider,
        max_tokens=max_tok,
        temperature=temp,
        tokens_est=tok_est,
        tool_calls_est=tools_est,
        agent_id=agent,
        consumer=consumer,
        request_class=rclass,
        prefer_free=prefer_free,
    )

    if not result.get("ok"):
        err, code, hdrs = map_tollgate_error(result)
        return JSONResponse(err, status_code=code, headers=hdrs or None)

    body_out = to_openai_completion(
        result,
        model=str(result.get("model") or body.model or "tollgate"),
        consumer=consumer,
        requested_model=body.model or "tollgate",
    )
    hdrs = response_headers(
        result, consumer=consumer, requested_model=body.model or "tollgate"
    )
    return JSONResponse(body_out, headers=hdrs or None)


# ── Anthropic-compatible drop-in ──────────────────────────────────────


class AnthropicMessagesBody(BaseModel):
    model: str = "tollgate/auto"
    messages: list[dict[str, Any]] = Field(default_factory=list)
    max_tokens: int = 1024
    system: str | list[Any] | None = None
    temperature: float | None = 1.0
    stream: bool = False
    metadata: dict[str, Any] | None = None
    # Tollgate extras
    intent: str | None = None
    provider: str | None = None
    request_class: str | None = None
    prefer_free: bool | None = None


@app.post("/v1/messages")
def anthropic_messages(
    body: AnthropicMessagesBody,
    x_consumer_key: str | None = Header(default=None, alias="X-Consumer-Key"),
    x_consumer_id: str | None = Header(default=None, alias="X-Consumer-Id"),
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_api_key: str | None = Header(default=None, alias="x-api-key"),
    anthropic_version: str | None = Header(default=None, alias="anthropic-version"),
) -> Any:
    """
    Anthropic-compatible Messages API (admission + route + meter).

    Drop-in::

        export ANTHROPIC_BASE_URL=http://127.0.0.1:8787
        export ANTHROPIC_API_KEY=n8n:secret   # open mode: any label

        # or curl with x-api-key
        curl -s http://127.0.0.1:8787/v1/messages \\
          -H 'x-api-key: desk' -H 'anthropic-version: 2023-06-01' \\
          -H 'content-type: application/json' \\
          -d '{"model":"tollgate/free","max_tokens":64,"messages":[{"role":"user","content":"hi"}]}'

    Does **not** require an Anthropic provider key — routes through Tollgate LLMs.
    ``anthropic-version`` is accepted and ignored (compat).
    """
    _ = anthropic_version  # accepted for SDK compat
    auth = _require(
        x_consumer_key,
        x_consumer_id,
        authorization=authorization,
        x_api_key=x_api_key,
    )
    consumer = auth["consumer"]

    from tollgate.anthropic_compat import (
        anthropic_error,
        map_anthropic_error,
        normalize_anthropic_messages,
        stream_anthropic_from_openai_sse,
        to_anthropic_message,
    )

    msgs = normalize_anthropic_messages(body.messages, system=body.system)
    # strip system-only → need at least one user/assistant turn for most providers
    userish = [m for m in msgs if m.get("role") != "system"]
    if not userish:
        err, code = anthropic_error("messages is required", status=400)
        return JSONResponse(err, status_code=code)

    intent = (body.intent or "").strip()
    prefer_free = body.prefer_free
    if not intent:
        intent, auto_free = resolve_intent(body.model, prefer_free=prefer_free)
        if prefer_free is None:
            prefer_free = auto_free
    else:
        prefer_free = bool(prefer_free) if prefer_free is not None else intent == "free_llm"

    mid = (body.model or "").strip()
    provider = (body.provider or "").strip()
    # claude-* / tollgate/* → let router pick provider/model
    if mid.startswith("tollgate/") or mid.lower().startswith("claude"):
        route_model = ""
    else:
        route_model = mid
    rclass = (body.request_class or "interactive").strip() or "interactive"
    meta_user = ""
    if isinstance(body.metadata, dict):
        meta_user = str(body.metadata.get("user_id") or body.metadata.get("user") or "")[:64]
    agent = (meta_user or f"anthropic:{consumer}")[:64]
    max_tok = max(1, int(body.max_tokens or 1024))
    temp = float(body.temperature if body.temperature is not None else 0.7)

    if body.stream:
        from tollgate.chat_stream import start_chat_stream

        started = start_chat_stream(
            msgs,
            intent=intent or "llm",
            model=route_model,
            provider=provider,
            max_tokens=max_tok,
            temperature=temp,
            agent_id=agent,
            consumer=consumer,
            request_class=rclass,
            prefer_free=prefer_free,
            requested_model=body.model or "tollgate",
        )
        if not started.get("ok"):
            err, code, hdrs = map_anthropic_error(started)
            return JSONResponse(err, status_code=code, headers=hdrs or None)
        headers = {
            "Cache-Control": "no-cache",
            "X-Tollgate-Consumer": consumer,
            "X-Tollgate-Stream": str(started.get("mode") or "upstream"),
            "X-Tollgate-Provider": str(started.get("provider") or ""),
            "X-Tollgate-Compat": "anthropic",
        }
        if mid.lower().startswith("claude") or mid.startswith("tollgate/"):
            headers["X-Tollgate-Routed-From"] = mid
        # chat_stream yields OpenAI SSE → convert to Anthropic event stream
        anthro_stream = stream_anthropic_from_openai_sse(
            started["stream"],
            model=body.model or str(started.get("model") or "tollgate"),
            provider=str(started.get("provider") or ""),
            consumer=consumer,
        )
        return StreamingResponse(
            anthro_stream,
            media_type="text/event-stream",
            headers=headers,
        )

    result = routed_chat(
        msgs,
        intent=intent or "llm",
        model=route_model,
        provider=provider,
        max_tokens=max_tok,
        temperature=temp,
        agent_id=agent,
        consumer=consumer,
        request_class=rclass,
        prefer_free=prefer_free,
    )
    if not result.get("ok"):
        err, code, hdrs = map_anthropic_error(result)
        return JSONResponse(err, status_code=code, headers=hdrs or None)
    body_out = to_anthropic_message(
        result,
        model=str(result.get("model") or body.model or "tollgate"),
        consumer=consumer,
        requested_model=body.model or "tollgate",
    )
    hdrs = response_headers(
        result, consumer=consumer, requested_model=body.model or "tollgate"
    )
    return JSONResponse(body_out, headers=hdrs or None)


@app.get("/")
def root() -> dict[str, Any]:
    return {
        "service": "tollgate",
        "product": "Tollgate",
        "docs": "/docs",
        "repo": "https://github.com/landjunge/tollgate",
        "openai_base_url": "/v1",
        "openai": ["/v1/chat/completions", "/v1/models"],
        "anthropic_base_url": "/",
        "anthropic": ["/v1/messages"],
        "control": "/v1/control",
        "resilience": "/v1/resilience",
        "chaos": "/v1/chaos",
        "dashboard": "/dashboard",
        "vision": "docs/VISION.md",
        "product_doc": "docs/PRODUCT.md",
        "architecture": "docs/ARCHITECTURE.md",
        "mcp": "docs/MCP.md",
        "portable": "docs/PORTABLE.md",
        "cost_limits": "docs/COST_LIMITS.md",
        "metrics": "/metrics",
        "v1": [
            "/v1/health",
            "/v1/auth",
            "/v1/control",
            "/v1/resilience",
            "/v1/chaos",
            "/v1/models",
            "/v1/chat/completions",
            "/v1/messages",
            "/v1/route",
            "/v1/invoke",
            "/v1/budget",
            "/v1/providers",
            "/v1/usage",
            "/v1/config",
        ],
    }
