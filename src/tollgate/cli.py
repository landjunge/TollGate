"""tollgate CLI entry."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable

from tollgate import help_text, i18n

Translator = Callable[..., str]


def _translator(language: str,
                register: str = i18n.DEFAULT_REGISTER) -> Translator:
    """Bindet Sprache und Sprachebene einmal, damit kein Aufruf sie vergisst."""

    def translate(key: str, **values: object) -> str:
        return i18n.translate(key, language, register, **values)

    return translate


def _flag_value(argv: list[str], flag: str) -> str | None:
    """Liest `--flag wert` oder `--flag=wert` aus argv."""
    for index, item in enumerate(argv):
        if item == flag and index + 1 < len(argv):
            return argv[index + 1]
        if item.startswith(flag + "="):
            return item.split("=", 1)[1]
    return None


def resolve_language(argv: list[str]) -> str:
    """Sprache schon vor dem Parsen bestimmen.

    argparse baut die Hilfetexte beim Anlegen des Parsers, nicht erst beim
    Parsen. Deshalb muss --lang vorher aus argv gelesen werden, sonst waere
    `tollgate --lang de --help` weiter englisch.
    """
    chosen = _flag_value(argv, "--lang")
    return i18n.normalise(chosen) if chosen else i18n.from_environment()


def resolve_register(argv: list[str]) -> str:
    """Sprachebene schon vor dem Parsen bestimmen — aus demselben Grund."""
    chosen = _flag_value(argv, "--mode")
    return (i18n.normalise_register(chosen) if chosen
            else i18n.register_from_environment())


def _format_help(topic: str = "", language: str = i18n.DEFAULT_LANGUAGE,
                 register: str = i18n.DEFAULT_REGISTER) -> str:
    """Hilfetext fuer Menschen (spiegelt docs/HILFE.md + USER_GUIDE.md).

    Ein Thema kann eine Fachfassung unter `<thema>#expert` haben. Bisher hat
    keines eine — dann bleibt der Klartext stehen, wie ueberall sonst auch.
    """
    code = i18n.normalise(language)
    level = i18n.normalise_register(register)
    name = (topic or "").strip().lower()
    entry = None
    if level == i18n.EXPERT:
        entry = help_text.TOPICS.get(name + i18n.EXPERT_SUFFIX)
    if entry is None:
        entry = help_text.TOPICS.get(name)
    if entry is not None:
        return entry[code].strip() + "\n"
    if name:
        head = help_text.UNKNOWN_TOPIC[code].format(topic=name)
        return head + "\n\n" + _format_help("", code, level)
    return help_text.OVERVIEW[code].strip() + "\n"

def main(argv: list[str] | None = None) -> None:
    items = sys.argv[1:] if argv is None else argv
    language = resolve_language(items)
    register = resolve_register(items)
    t = _translator(language, register)
    p = argparse.ArgumentParser(prog="tollgate", description=t("cli.description"))
    p.add_argument(
        "--lang",
        default=language,
        choices=list(i18n.LANGUAGES),
        help=t("cli.lang"),
    )
    p.add_argument(
        "--mode",
        default=register,
        choices=list(i18n.REGISTERS),
        help=t("cli.mode"),
    )
    sub = p.add_subparsers(dest="cmd")
    help_p = sub.add_parser("help", help=t("cmd.help"))
    help_p.add_argument(
        "topic",
        nargs="?",
        default="",
        help=t("cmd.help.topic"),
    )

    sub.add_parser("serve", help=t("cmd.serve"))
    sub.add_parser("mcp", help=t("cmd.mcp"))
    sub.add_parser("health", help=t("cmd.health"))
    sub.add_parser(
        "control",
        help=t("cmd.control"),
    )
    sub.add_parser(
        "resilience",
        help=t("cmd.resilience"),
    )
    ch = sub.add_parser(
        "chaos",
        help=t("cmd.chaos"),
    )
    ch.add_argument(
        "action",
        choices=["status", "start", "stop", "test"],
        help=t("cmd.chaos.action"),
    )
    ch.add_argument("provider", nargs="?", default="", help=t("cmd.chaos.provider"))
    ch.add_argument(
        "--duration",
        default="5m",
        help=t("cmd.chaos.duration"),
    )
    ch.add_argument("--requests", type=int, default=5, help=t("cmd.chaos.probes"))
    ch.add_argument("--intent", default="free_llm", help=t("cmd.chaos.intent"))
    ch.add_argument("--live-chat", action="store_true", help=t("cmd.chaos.chat"))
    ch.add_argument("--all", action="store_true", help=t("cmd.chaos.all"))
    sub.add_parser("paths", help=t("cmd.paths"))

    cadd = sub.add_parser("consumer-add", help=t("cmd.consumer_add"))
    cadd.add_argument("id", help=t("cmd.consumer_add.id"))
    cadd.add_argument("--admin", action="store_true", help=t("cmd.consumer_add.config"))
    cadd.add_argument("--secret", default="", help=t("cmd.consumer_add.secret"))
    cadd.add_argument("--label", default="", help=t("cmd.consumer_add.label"))

    cbud = sub.add_parser(
        "consumer-budget",
        help=t("cmd.envelope"),
    )
    cbud.add_argument(
        "id",
        nargs="?",
        default="",
        help=t("cmd.envelope.id"),
    )
    cbud.add_argument("--list", action="store_true", help=t("cmd.envelope.list"))
    cbud.add_argument("--max-calls-day", type=int, default=None, dest="max_calls_day")
    cbud.add_argument("--max-tokens-day", type=int, default=None, dest="max_tokens_day")
    cbud.add_argument("--max-usd-day", type=float, default=None, dest="max_usd_day")
    cbud.add_argument("--max-usd-request", type=float, default=None, dest="max_usd_request")
    cbud.add_argument("--max-usd-hour", type=float, default=None, dest="max_usd_hour")
    cbud.add_argument(
        "--max-requests-minute", type=int, default=None, dest="max_requests_minute"
    )
    cbud.add_argument(
        "--max-tokens-request", type=int, default=None, dest="max_tokens_request"
    )
    cbud.add_argument("--max-tool-calls", type=int, default=None, dest="max_tool_calls")
    cbud.add_argument(
        "--allow-provider",
        action="append",
        default=None,
        dest="allow_providers",
        help=t("cmd.envelope.allow_provider"),
    )
    cbud.add_argument(
        "--block-provider",
        action="append",
        default=None,
        dest="block_providers",
        help=t("cmd.envelope.block_provider"),
    )
    cbud.add_argument(
        "--allow-intent",
        action="append",
        default=None,
        dest="allow_intents",
        help=t("cmd.envelope.allow_intent"),
    )
    cbud.add_argument(
        "--block-intent",
        action="append",
        default=None,
        dest="block_intents",
        help=t("cmd.envelope.block_intent"),
    )
    cbud.add_argument(
        "--allow-op",
        action="append",
        default=None,
        dest="allow_ops",
        help=t("cmd.envelope.allow_op"),
    )
    cbud.add_argument(
        "--block-op",
        action="append",
        default=None,
        dest="block_ops",
        help=t("cmd.envelope.block_op"),
    )
    cbud.add_argument(
        "--clear-scopes",
        action="store_true",
        help=t("cmd.envelope.clear_scopes"),
    )
    cbud.add_argument(
        "--clear",
        action="store_true",
        help=t("cmd.envelope.remove"),
    )

    padd = sub.add_parser("provider-add", help=t("cmd.distill"))
    padd.add_argument("id", help=t("cmd.distill.provider"))
    padd.add_argument("--title", default="", help=t("cmd.distill.title"))
    padd.add_argument("--base-url", default="", dest="base_url")
    padd.add_argument(
        "--auth",
        default="bearer",
        choices=["bearer", "header_token", "xi_api_key"],
    )
    padd.add_argument("--env-key", default="", dest="env_key", help=t("cmd.distill.env"))
    padd.add_argument(
        "--high-risk",
        action="store_true",
        help=t("cmd.distill.high_risk"),
    )

    risk = sub.add_parser("high-risk", help=t("cmd.high_risk"))
    risk.add_argument("action", choices=["list", "add", "remove"])
    risk.add_argument("provider", nargs="?", default="")

    doc = sub.add_parser("doctor", help=t("cmd.doctor"))
    doc.add_argument("--live", action="store_true", help=t("cmd.doctor.providers"))
    doc.add_argument("--json", action="store_true", help=t("cmd.json"))

    sub.add_parser(
        "suggest",
        help=t("cmd.advise"),
    )

    st = sub.add_parser(
        "status",
        help=t("cmd.desk"),
    )
    st.add_argument(
        "--json",
        action="store_true",
        help=t("cmd.desk.json"),
    )

    plan = sub.add_parser("plan-status", help=t("cmd.plan_status"))
    plan.add_argument("--provider", choices=["all", "codex", "claude", "grok"], default="all",
                      help=t("cmd.plan_status.provider"))
    plan.add_argument("--no-live", action="store_true", help=t("cmd.plan_status.no_live"))
    plan.add_argument("--evaluate", default="", metavar="SINCE",
                      help=t("cmd.plan_status.evaluate"))
    plan.add_argument("--claude-statusline", action="store_true",
                      help=t("cmd.plan_status.statusline"))
    plan.add_argument("--log", default="", help=t("cmd.plan_status.log"))

    cert = sub.add_parser(
        "certificate",
        help=t("cmd.report_card"),
    )
    cert.add_argument(
        "--application",
        default="",
        help=t("cmd.report_card.label"),
    )
    cert.add_argument("--json", action="store_true", help=t("cmd.report_card.json"))

    dem = sub.add_parser(
        "demo",
        help=t("cmd.demo"),
    )
    dem.add_argument(
        "--skip-chaos",
        action="store_true",
        help=t("cmd.demo.protect_only"),
    )
    dem.add_argument(
        "--consumer",
        default="support-agent",
        help=t("cmd.demo.consumer"),
    )
    dem.add_argument(
        "--provider",
        default="opencode_zen",
        help=t("cmd.demo.provider"),
    )

    frz = sub.add_parser(
        "freeze",
        help=t("cmd.freeze"),
    )
    frz.add_argument(
        "action",
        nargs="?",
        default="on",
        choices=["on", "off", "status", "unfreeze"],
        help=t("cmd.freeze.state"),
    )
    frz.add_argument(
        "--reason",
        default="",
        help=t("cmd.freeze.reason"),
    )
    sub.add_parser("unfreeze", help=t("cmd.unfreeze"))

    circ = sub.add_parser(
        "circuits",
        help=t("cmd.circuit"),
    )
    circ.add_argument(
        "action",
        choices=["list", "reset", "status"],
        help=t("cmd.circuit.action"),
    )
    circ.add_argument(
        "provider",
        nargs="?",
        default="",
        help=t("cmd.circuit.provider"),
    )
    circ.add_argument(
        "--all",
        action="store_true",
        dest="all_circuits",
        help=t("cmd.circuit.all"),
    )

    alrt = sub.add_parser(
        "alert",
        help=t("cmd.alerts"),
    )
    alrt.add_argument(
        "action",
        choices=["test", "events"],
        help=t("cmd.alerts.action"),
    )
    alrt.add_argument(
        "--message",
        default="tollgate alert test",
        help=t("cmd.alerts.message"),
    )

    snap = sub.add_parser(
        "snapshot",
        help=t("cmd.snapshot"),
    )
    snap.add_argument(
        "action",
        choices=["export", "import", "info"],
        help=t("cmd.snapshot.action"),
    )
    snap.add_argument(
        "path",
        nargs="?",
        default="",
        help=t("cmd.snapshot.path"),
    )
    snap.add_argument(
        "-o",
        "--output",
        default="",
        help=t("cmd.snapshot.out"),
    )
    snap.add_argument(
        "--include-secrets",
        action="store_true",
        help=t("cmd.snapshot.secrets"),
    )
    snap.add_argument(
        "--no-audit",
        action="store_true",
        help=t("cmd.snapshot.no_audit"),
    )
    snap.add_argument(
        "--replace",
        action="store_true",
        help=t("cmd.snapshot.force"),
    )
    snap.add_argument(
        "--merge-config",
        action="store_true",
        help=t("cmd.snapshot.merge_config"),
    )
    snap.add_argument(
        "--dry-run",
        action="store_true",
        help=t("cmd.snapshot.dry_run"),
    )

    rep = sub.add_parser(
        "report",
        help=t("cmd.report"),
    )
    rep.add_argument(
        "--format",
        choices=["json", "md", "markdown"],
        default="md",
        dest="report_format",
        help=t("cmd.report.format"),
    )
    rep.add_argument(
        "-o",
        "--output",
        default="",
        help=t("cmd.report.out"),
    )

    aud = sub.add_parser(
        "audit",
        help=t("cmd.audit"),
    )
    aud.add_argument(
        "--event",
        default="",
        help=t("cmd.audit.event"),
    )
    aud.add_argument("--consumer", default="", help=t("cmd.audit.consumer"))
    aud.add_argument("--provider", default="", help=t("cmd.audit.provider"))
    aud.add_argument("--limit", type=int, default=30, help=t("cmd.audit.limit"))
    aud.add_argument(
        "--summary",
        action="store_true",
        help=t("cmd.audit.summary"),
    )
    aud.add_argument("--json", action="store_true", help=t("cmd.audit.json"))

    srch = sub.add_parser(
        "search",
        help=t("cmd.search"),
    )
    srch.add_argument(
        "query",
        nargs="*",
        default=[],
        help=t("cmd.search.query"),
    )
    srch.add_argument(
        "--kind",
        action="append",
        dest="kinds",
        default=None,
        help=t("cmd.search.kind"),
    )
    srch.add_argument("--limit", type=int, default=15, help=t("cmd.search.limit"))
    srch.add_argument("--json", action="store_true", help=t("cmd.json"))
    srch.add_argument(
        "--map",
        action="store_true",
        help=t("cmd.search.map"),
    )

    args = p.parse_args(items)

    if args.cmd == "help":
        print(_format_help(getattr(args, "topic", "") or "", language, register))
        return

    if args.cmd == "mcp" or (args.cmd is None and len(sys.argv) == 1):
        from tollgate.mcp import main as mcp_main

        mcp_main()
        return

    if args.cmd == "serve":
        import os

        import uvicorn

        from tollgate.app_config import load_config
        from tollgate.config_validate import assert_config_or_raise
        from tollgate.paths import pin_data_home_env

        pin_data_home_env()
        cfg = load_config(force=True)
        strict = (os.environ.get("TOLLGATE_STRICT_CONFIG") or "").strip().lower() in (
            "1",
            "true",
            "yes",
        )
        try:
            warns = assert_config_or_raise(cfg, strict=strict)
            for w in warns:
                print(t("out.config", path=w), file=sys.stderr)
        except ValueError as e:
            print(str(e), file=sys.stderr)
            raise SystemExit(2) from e
        host = (os.environ.get("HOST") or "127.0.0.1").strip() or "127.0.0.1"
        port = int(os.environ.get("PORT", "8787"))
        try:
            from tollgate.consumers import auth_required, open_public_bind_error

            blocked = open_public_bind_error(host=host)
            if blocked:
                print(t("out.error", message=blocked), file=sys.stderr)
                raise SystemExit(2)
            if not auth_required():
                print(t("out.open_mode", host=host, port=port), file=sys.stderr)
            else:
                print(t("out.auth_mode", host=host, port=port), file=sys.stderr)
        except Exception as e:  # noqa: BLE001
            from tollgate.soft_fail import soft_fail

            soft_fail("serve_banner", e, op="serve")
        uvicorn.run("tollgate.server_v1:app", host=host, port=port, reload=False)
        return

    if args.cmd == "doctor":
        from tollgate.doctor import format_doctor_text, run_doctor

        report = run_doctor(live=bool(args.live))
        if args.json:
            print(json.dumps(report, indent=2, default=str))
        else:
            print(format_doctor_text(report))
        raise SystemExit(0 if report.get("ok") else 1)

    if args.cmd == "suggest":
        from tollgate.paths import pin_data_home_env
        from tollgate.suggest import routing_suggestions

        pin_data_home_env()
        print(json.dumps(routing_suggestions(), indent=2, default=str))
        return

    if args.cmd == "search":
        from tollgate.repo_search import format_search_text, map_markdown, search

        if args.map:
            print(map_markdown())
            return
        q = " ".join(args.query or []).strip()
        if not q:
            print(
                t("out.search_usage"),
                file=sys.stderr,
            )
            raise SystemExit(2)
        result = search(q, limit=int(args.limit), kinds=args.kinds)
        if args.json:
            print(json.dumps(result, indent=2, default=str))
        else:
            print(format_search_text(result))
        raise SystemExit(0 if result.get("hits") else 1)

    if args.cmd == "audit":
        from tollgate.audit_log import audit_summary, query_audit
        from tollgate.paths import pin_data_home_env

        pin_data_home_env()
        if args.summary:
            out = audit_summary()
            print(json.dumps(out, indent=2, default=str))
            return
        out = query_audit(
            limit=int(args.limit),
            event=args.event,
            consumer=args.consumer,
            provider=args.provider,
        )
        # always JSON for machine + human-friendly structure
        print(json.dumps(out, indent=2, default=str))
        return

    if args.cmd == "report":
        from pathlib import Path

        from tollgate.paths import pin_data_home_env
        from tollgate.report import build_report, format_report_markdown

        pin_data_home_env()
        fmt = (args.report_format or "md").lower()
        if fmt in ("md", "markdown"):
            text = format_report_markdown()
        else:
            text = json.dumps(build_report(), indent=2, default=str)
        out_path = (args.output or "").strip()
        if out_path:
            Path(out_path).expanduser().write_text(text + ("" if text.endswith("\n") else "\n"), encoding="utf-8")
            print(t("out.wrote", path=out_path), file=sys.stderr)
        print(text)
        return

    if args.cmd == "alert":
        from tollgate.alerts import event_catalog, test_webhook
        from tollgate.paths import pin_data_home_env

        pin_data_home_env()
        if args.action == "events":
            print(json.dumps(event_catalog(), indent=2, default=str))
            return
        out = test_webhook(message=args.message)
        print(json.dumps(out, indent=2, default=str))
        raise SystemExit(0 if out.get("ok") else 1)

    if args.cmd == "status":
        from tollgate.paths import pin_data_home_env
        from tollgate.status import desk_status, format_status_text

        pin_data_home_env()
        if args.json:
            print(json.dumps(desk_status(), indent=2, default=str))
        else:
            print(format_status_text())
        return

    if args.cmd == "plan-status":
        from datetime import datetime, timezone
        from pathlib import Path

        from tollgate.paths import pin_data_home_env
        from tollgate.provider_ops import plan_status as ps

        pin_data_home_env()
        log = Path(args.log).expanduser() if args.log else None
        if args.claude_statusline:
            snap = ps.claude_statusline(json.loads(sys.stdin.read() or "{}"))
            if snap["windows"]:
                ps.append_log([snap], log)
            print(" ".join(f"{w['window']}:{w['used_percent']:.0f}%" for w in snap["windows"]))
            return
        chosen = ps.PROVIDERS if args.provider == "all" else (args.provider,)
        if args.evaluate:
            since = datetime.fromisoformat(args.evaluate.replace("Z", "+00:00"))
            since = since if since.tzinfo else since.replace(tzinfo=timezone.utc)
            print(json.dumps(ps.evaluate_logs(chosen, since=since), indent=2, default=str))
            return
        rows = ps.collect(chosen, live=not args.no_live)
        path = ps.append_log(rows, log)
        print(json.dumps({"log": str(path), "snapshots": rows}, indent=2, default=str))
        return

    if args.cmd == "certificate":
        from tollgate.certificate import build_certificate, format_certificate_text
        from tollgate.paths import pin_data_home_env

        pin_data_home_env()
        cert_data = build_certificate(application=args.application or "")
        if args.json:
            print(json.dumps(cert_data, indent=2, default=str))
        else:
            print(format_certificate_text(cert_data))
        # non-zero if protect hard-fails
        overall = cert_data.get("overall")
        raise SystemExit(1 if overall in ("NEEDS_PROTECT", "FROZEN") else 0)

    if args.cmd == "demo":
        import os
        import subprocess
        from pathlib import Path

        root = Path(__file__).resolve().parents[2]
        script = root / "scripts" / "demo-agent-safety.sh"
        if not script.is_file():
            # installed wheel: fall back to in-process mini demo
            from tollgate.paths import pin_data_home_env

            pin_data_home_env()
            print(t("out.demo_missing"), file=sys.stderr)
            raise SystemExit(2)
        env = os.environ.copy()
        env["DEMO_CONSUMER"] = str(args.consumer or "support-agent")
        env["DEMO_CHAOS_PROVIDER"] = str(args.provider or "opencode_zen")
        if args.skip_chaos:
            env["SKIP_CHAOS"] = "1"
        raise SystemExit(subprocess.call(["bash", str(script)], env=env))

    if args.cmd in ("freeze", "unfreeze"):
        from tollgate.freeze import freeze_status, set_frozen
        from tollgate.paths import pin_data_home_env

        pin_data_home_env()
        if args.cmd == "unfreeze":
            out = set_frozen(False, reason="", by="cli")
            print(json.dumps(out, indent=2, default=str))
            raise SystemExit(0)
        act = (getattr(args, "action", None) or "on").lower()
        if act == "status":
            print(json.dumps(freeze_status(), indent=2, default=str))
            return
        if act in ("off", "unfreeze"):
            out = set_frozen(False, reason=args.reason or "", by="cli")
            print(json.dumps(out, indent=2, default=str))
            raise SystemExit(0)
        out = set_frozen(
            True,
            reason=args.reason or "manual freeze via CLI",
            by="cli",
        )
        print(json.dumps(out, indent=2, default=str))
        raise SystemExit(0)

    if args.cmd == "circuits":
        from tollgate.gateway.circuit import get_circuits, reset_circuits
        from tollgate.paths import pin_data_home_env

        pin_data_home_env()
        if args.action in ("list", "status"):
            rows = get_circuits().snapshot()
            print(
                json.dumps(
                    {"ok": True, "count": len(rows), "circuits": rows},
                    indent=2,
                    default=str,
                )
            )
            return
        # reset
        if not args.provider and not args.all_circuits:
            print(
                json.dumps(
                    {
                        "ok": False,
                        "error": "provider id required, or pass --all",
                    }
                )
            )
            raise SystemExit(2)
        out = reset_circuits(
            args.provider or "",
            all_circuits=bool(args.all_circuits),
        )
        print(json.dumps(out, indent=2, default=str))
        return

    if args.cmd == "snapshot":
        from datetime import date
        from pathlib import Path

        from tollgate.paths import pin_data_home_env
        from tollgate.snapshot import export_snapshot, import_snapshot, snapshot_info

        pin_data_home_env()
        action = args.action
        if action == "export":
            out = (args.output or args.path or "").strip()
            if not out:
                out = f"tollgate-snapshot-{date.today().isoformat()}.tgz"
            result = export_snapshot(
                out,
                include_secrets=bool(args.include_secrets),
                include_audit=not bool(args.no_audit),
            )
            print(json.dumps(result, indent=2, default=str))
            raise SystemExit(0 if result.get("ok") else 1)
        path = (args.path or args.output or "").strip()
        if not path:
            print(
                json.dumps(
                    {
                        "ok": False,
                        "error": "path required: tollgate snapshot import <file.tgz>",
                    }
                )
            )
            raise SystemExit(2)
        if action == "info":
            print(json.dumps(snapshot_info(path), indent=2, default=str))
            return
        result = import_snapshot(
            path,
            dry_run=bool(args.dry_run),
            replace=bool(args.replace),
            merge_config=bool(getattr(args, "merge_config", False)),
        )
        print(json.dumps(result, indent=2, default=str))
        raise SystemExit(0 if result.get("ok") else 1)

    if args.cmd == "health":
        from tollgate import get_keys_service
        from tollgate.consumers import auth_status
        from tollgate.cost import high_risk_ids
        from tollgate.paths import path_snapshot, pin_data_home_env

        pin_data_home_env()
        print(
            json.dumps(
                {
                    "ok": True,
                    "portable": path_snapshot(),
                    "auth": auth_status(),
                    "high_risk_providers": sorted(high_risk_ids()),
                    "app": get_keys_service().app_status(),
                },
                indent=2,
                default=str,
            )
        )
        return

    if args.cmd == "control":
        from tollgate.control_plane import control_snapshot
        from tollgate.paths import pin_data_home_env

        pin_data_home_env()
        print(json.dumps(control_snapshot(), indent=2, default=str))
        return

    if args.cmd == "resilience":
        from tollgate.paths import pin_data_home_env
        from tollgate.resilience import resilience_score

        pin_data_home_env()
        print(json.dumps(resilience_score(), indent=2, default=str))
        return

    if args.cmd == "chaos":
        from tollgate.chaos import run_failover_test, start_chaos, status, stop_chaos
        from tollgate.paths import pin_data_home_env

        pin_data_home_env()

        def _parse_dur(s: str) -> float:
            s = (s or "5m").strip().lower()
            if s.endswith("ms"):
                return max(0.001, float(s[:-2]) / 1000.0)
            if s.endswith("s"):
                return max(1.0, float(s[:-1]))
            if s.endswith("m"):
                return max(1.0, float(s[:-1]) * 60.0)
            if s.endswith("h"):
                return max(1.0, float(s[:-1]) * 3600.0)
            return max(1.0, float(s))

        if args.action == "status":
            print(json.dumps(status(), indent=2, default=str))
            return
        if args.action == "stop":
            print(
                json.dumps(
                    stop_chaos(args.provider, all_injects=bool(args.all)),
                    indent=2,
                    default=str,
                )
            )
            return
        if args.action == "start":
            if not args.provider:
                print(json.dumps({"ok": False, "error": "provider required"}))
                raise SystemExit(1)
            print(
                json.dumps(
                    start_chaos(
                        args.provider,
                        duration_s=_parse_dur(args.duration),
                        reason="cli",
                    ),
                    indent=2,
                    default=str,
                )
            )
            return
        if args.action == "test":
            if not args.provider:
                print(json.dumps({"ok": False, "error": "provider required"}))
                raise SystemExit(1)
            rep = run_failover_test(
                args.provider,
                intent=args.intent,
                requests=int(args.requests),
                duration_s=_parse_dur(args.duration),
                live_chat=bool(args.live_chat),
            )
            print(json.dumps(rep, indent=2, default=str))
            raise SystemExit(0 if rep.get("survived") or rep.get("ok") else 1)
        return

    if args.cmd == "paths":
        from tollgate.paths import path_snapshot, pin_data_home_env

        pin_data_home_env()
        print(json.dumps(path_snapshot(), indent=2))
        return

    if args.cmd == "consumer-add":
        from tollgate.consumers import add_consumer
        from tollgate.paths import pin_data_home_env

        pin_data_home_env()
        out = add_consumer(
            args.id,
            secret=args.secret or None,
            admin=bool(args.admin),
            label=args.label or args.id,
        )
        print(json.dumps(out, indent=2))
        if out.get("ok"):
            print(
                t("out.use_header", key=f"{out['id']}:{out['secret']}"),
                file=sys.stderr,
            )
        return

    if args.cmd == "consumer-budget":
        from tollgate.app_config import load_config, save_config
        from tollgate.limits import check_consumer_limits, consumer_envelope
        from tollgate.paths import pin_data_home_env
        from tollgate.usage_ledger import consumer_usage, load_usage

        pin_data_home_env()
        if args.list or not args.id:
            cfg = load_config(force=True)
            envs = dict(cfg.get("consumer_envelopes") or {})
            day = load_usage()
            used = day.get("consumers") or {}
            rows = []
            ids = set(envs.keys()) | set(used.keys())
            for cid in sorted(ids):
                if cid.startswith("_") and cid != "_default":
                    continue
                rows.append(
                    {
                        "id": cid,
                        "envelope": envs.get(cid) or {},
                        "usage": used.get(cid) or {},
                        "limits": check_consumer_limits(cid) if cid != "_default" else None,
                    }
                )
            print(json.dumps({"ok": True, "envelopes": rows, "raw": envs}, indent=2, default=str))
            return
        from tollgate.consumers import ANONYMOUS, consumer_id_is_valid

        cid = (args.id or "").strip()
        if not cid or cid == ANONYMOUS or not consumer_id_is_valid(cid):
            print(json.dumps({"ok": False, "error": "invalid consumer id"}))
            raise SystemExit(1)
        cfg = load_config(force=True)
        envs = dict(cfg.get("consumer_envelopes") or {})
        if args.clear:
            envs.pop(cid, None)
            cfg["consumer_envelopes"] = envs
            save_config(cfg)
            print(json.dumps({"ok": True, "id": cid, "cleared": True}, indent=2))
            return
        block = dict(envs.get(cid) or {})
        if args.max_calls_day is not None:
            block["max_calls_day"] = int(args.max_calls_day)
        if args.max_tokens_day is not None:
            block["max_tokens_day"] = int(args.max_tokens_day)
        if args.max_usd_day is not None:
            block["max_usd_day"] = float(args.max_usd_day)
        if args.max_usd_request is not None:
            block["max_usd_request"] = float(args.max_usd_request)
        if args.max_usd_hour is not None:
            block["max_usd_hour"] = float(args.max_usd_hour)
        if args.max_requests_minute is not None:
            block["max_requests_minute"] = int(args.max_requests_minute)
        if args.max_tokens_request is not None:
            block["max_tokens_request"] = int(args.max_tokens_request)
        if args.max_tool_calls is not None:
            block["max_tool_calls"] = int(args.max_tool_calls)
        # L3 scopes
        if getattr(args, "clear_scopes", False):
            for k in (
                "allowed_providers",
                "blocked_providers",
                "allowed_ops",
                "blocked_ops",
                "allowed_intents",
                "blocked_intents",
            ):
                block.pop(k, None)
        if args.allow_providers is not None:
            block["allowed_providers"] = [
                str(x).strip().lower() for x in args.allow_providers if str(x).strip()
            ]
        if args.block_providers is not None:
            block["blocked_providers"] = [
                str(x).strip().lower() for x in args.block_providers if str(x).strip()
            ]
        if args.allow_intents is not None:
            block["allowed_intents"] = [
                str(x).strip().lower() for x in args.allow_intents if str(x).strip()
            ]
        if args.block_intents is not None:
            block["blocked_intents"] = [
                str(x).strip().lower() for x in args.block_intents if str(x).strip()
            ]
        if args.allow_ops is not None:
            block["allowed_ops"] = [
                str(x).strip().lower() for x in args.allow_ops if str(x).strip()
            ]
        if args.block_ops is not None:
            block["blocked_ops"] = [
                str(x).strip().lower() for x in args.block_ops if str(x).strip()
            ]
        if not block:
            print(
                json.dumps(
                    {
                        "ok": False,
                        "error": (
                            "pass --max-usd-day / --allow-provider / "
                            "--max-requests-minute / … or --clear"
                        ),
                    }
                )
            )
            raise SystemExit(1)
        envs[cid] = block
        cfg["consumer_envelopes"] = envs
        save_config(cfg)
        print(
            json.dumps(
                {
                    "ok": True,
                    "id": cid,
                    "envelope": consumer_envelope(cid),
                    "usage": consumer_usage(cid),
                    "limits": check_consumer_limits(cid),
                },
                indent=2,
                default=str,
            )
        )
        return

    if args.cmd == "provider-add":
        from tollgate.paths import pin_data_home_env
        from tollgate.provider_scaffold import scaffold_provider

        pin_data_home_env()
        out = scaffold_provider(
            args.id,
            title=args.title,
            base_url=args.base_url,
            auth=args.auth,
            env_key=args.env_key,
            high_risk=bool(args.high_risk),
        )
        print(json.dumps(out, indent=2, default=str))
        return

    if args.cmd == "high-risk":
        from tollgate.app_config import load_config, save_config
        from tollgate.cost import high_risk_ids
        from tollgate.paths import pin_data_home_env

        pin_data_home_env()
        if args.action == "list":
            print(json.dumps({"high_risk_providers": sorted(high_risk_ids())}, indent=2))
            return
        pid = (args.provider or "").strip().lower()
        if not pid:
            print(json.dumps({"ok": False, "error": "provider id required"}))
            return
        cfg = load_config(force=True)
        guard = dict(cfg.get("cost_guard") or {})
        lst = [str(x).lower() for x in (guard.get("high_risk_providers") or [])]
        if args.action == "add" and pid not in lst:
            lst.append(pid)
        if args.action == "remove":
            lst = [x for x in lst if x != pid]
        guard["high_risk_providers"] = lst
        cfg["cost_guard"] = guard
        save_config(cfg)
        # ensure provider block exists disabled if high-risk add
        if args.action == "add":
            provs = dict(cfg.get("providers") or {})
            block = dict(provs.get(pid) or {})
            block.setdefault("enabled", False)
            block.setdefault("high_risk", True)
            block.setdefault("max_usd_day", 1.0)
            block.setdefault("max_calls_day", 20)
            provs[pid] = block
            cfg["providers"] = provs
            save_config(cfg)
        print(json.dumps({"ok": True, "high_risk_providers": lst, "action": args.action, "provider": pid}, indent=2))
        return

    p.print_help()


if __name__ == "__main__":
    main()
