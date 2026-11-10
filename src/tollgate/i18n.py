"""Zweisprachigkeit DE/EN.

Alle NetzwerkPunkt-Werkzeuge sind zweisprachig. Nachruesten ist teuer, also
gehoert jeder sichtbare Text von Anfang an in diesen Katalog und nie direkt
in den Code.

Regeln:
- Schluessel sind stabil, Texte nicht. Ein Schluessel fehlt lieber laut, als
  dass eine Sprache still auf die andere zurueckfaellt.
- Eigennamen und Fachbegriffe werden nicht uebersetzt: Tollgate, Protect,
  Route, Prove, Provider, Consumer, Envelope, Chaos, MCP, JSON.
- Befehle, Flags, Pfade und URLs sind sprachneutral und bleiben gleich.
- Der Test tests/test_i18n.py haelt fest, dass beide Sprachen vollstaendig
  sind und dass kein sichtbarer Text am Katalog vorbeigeht.
"""

from __future__ import annotations

import os

LANGUAGES = ("de", "en")
DEFAULT_LANGUAGE = "en"

LANGUAGE_NAMES = {"de": "Deutsch", "en": "English"}

# Zwei Sprachebenen, unabhaengig von DE/EN. Klartext ist der Normalfall,
# Fachsprache ist zuschaltbar — nie umgekehrt. Wer die Fachwoerter kennt,
# schaltet sie ein; wer sie nicht kennt, wird nicht damit ueberfahren.
# Vorbild ist 4AllPass (frontend/src/lib/copy-mode.ts).
PLAIN = "plain"
EXPERT = "expert"
REGISTERS = (PLAIN, EXPERT)
DEFAULT_REGISTER = PLAIN
# Ein Fachtext haengt als eigener Eintrag am selben Schluessel. Das
# Trennzeichen ist bewusst kein Punkt: sonst waere "ui.register.expert" die
# Fachfassung von "ui.register" statt ein eigener Schluessel.
EXPERT_SUFFIX = "#expert"

# Reihenfolge fuer die Kommandozeile: unsere eigene Variable schlaegt die
# Locale des Systems. "C" und "POSIX" heissen "keine Vorliebe" und werden
# uebersprungen, sonst wuerde jede Server-Shell stumm auf eine Sprache fallen,
# die der Betreiber nie gewaehlt hat.
ENVIRONMENT_VARIABLES = ("TOLLGATE_LANG", "LC_ALL", "LC_MESSAGES", "LANG")
NEUTRAL_LOCALES = {"c", "posix", ""}

CATALOG: dict[str, dict[str, str]] = {
    "ui.control.scope_title": {
        "de": "Was hier kontrolliert wird",
        "en": "What is controlled here",
    },
    "ui.control.scope_body": {
        "de": "Tagesverbrauch kann geschätzt sein. Freeze sperrt neue angeschlossene Aufrufe; "
              "es beendet keine fremden Prozesse. Dauerhafte Auftragsbudgets gelten nur am "
              "angeschlossenen Versandweg. Dessen Dummy-Prüfung ist keine Live-Anbieterabnahme. "
              "Eine bestätigte Sperre ist noch kein bestätigter Abbruch; unklare Kosten bleiben reserviert.",
        "en": "Daily usage may be estimated. Freeze blocks new connected calls; it does not "
              "terminate other processes. Durable workflow budgets apply only at the connected "
              "dispatch boundary. Its dummy test is not live-provider acceptance. A confirmed "
              "block is not a confirmed abort; unknown costs remain reserved.",
    },
    # --- Programm ---
    "cli.description": {
        "de": "Tollgate — Sicherheitsschicht für AI-Agenten (Protect · Route · Prove). "
              "Probier: tollgate help",
        "en": "Tollgate — safety layer for AI agents (Protect · Route · Prove). "
              "Try: tollgate help",
    },
    "cli.lang": {
        "de": "Ausgabesprache: de oder en",
        "en": "Output language: de or en",
    },
    "cli.mode": {
        "de": "Sprachebene: plain (Klartext, Standard) oder expert (Fachsprache)",
        "en": "Wording: plain (default) or expert (technical terms)",
    },
    # --- Befehle ---
    "cmd.help": {
        "de": "Hilfe — Themen und Handbuch-Verweise",
        "en": "User help — topics and handbook links",
    },
    "cmd.help.topic": {
        "de": "start|protect|route|prove|ui|api|ops|troubleshoot|commands|env|config|faq",
        "en": "start|protect|route|prove|ui|api|ops|troubleshoot|commands|env|config|faq",
    },
    "cmd.serve": {
        "de": "Tollgate starten, damit Agenten es erreichen können",
        "en": "Start Tollgate so agents can reach it",
    },
    "cmd.serve#expert": {
        "de": "HTTP-Server starten (uvicorn)",
        "en": "Run HTTP server (uvicorn)",
    },
    "cmd.mcp": {
        "de": "MCP-Server auf stdin/stdout starten",
        "en": "Run MCP stdio server",
    },
    "cmd.health": {
        "de": "Zeigt, ob Tollgate hier läuft: wo seine Dateien liegen und "
              "wie es anmeldet",
        "en": "Shows whether Tollgate runs here: where its files are and how "
              "it signs in",
    },
    "cmd.health#expert": {
        "de": "Lokalen Zustand als JSON ausgeben (Pfade + Anmeldeart)",
        "en": "Print local health JSON (paths + auth mode)",
    },
    "cmd.control": {
        "de": "Lagebild: wie es den Anbietern geht, wer wieviel verbraucht "
              "hat, und was daraus folgt",
        "en": "The situation: how the providers are doing, who used how much, "
              "and what follows from it",
    },
    "cmd.control#expert": {
        "de": "Lagebild (Provider-Zustand + Verbrauch je Consumer + Schlagzeile)",
        "en": "Control plane snapshot (provider health + consumer burn + headline)",
    },
    "cmd.resilience": {
        "de": "AI Resilience Score (0–100) + Warnungen",
        "en": "AI Resilience Score (0–100) + warnings",
    },
    "cmd.chaos": {
        "de": "Probe für den Ernstfall: einen Anbieter absichtlich ausfallen "
              "lassen und sehen, ob umgeschaltet wird",
        "en": "A drill for the real thing: make a provider fail on purpose "
              "and see whether it switches over",
    },
    "cmd.chaos#expert": {
        "de": "Chaos / Notfall: Provider-Ausfall erzeugen oder Umschalttest fahren",
        "en": "Chaos / DR: inject provider outage or run failover test",
    },
    "cmd.chaos.action": {
        "de": "status | start | stop | test",
        "en": "status | start | stop | test",
    },
    "cmd.chaos.provider": {
        "de": "Provider-Kennung (z. B. opencode_zen)",
        "en": "provider id (e.g. opencode_zen)",
    },
    "cmd.chaos.duration": {
        "de": "Dauer des Ausfalls: 30s, 5m, 1h (Vorgabe 5m)",
        "en": "inject duration: 30s, 5m, 1h (default 5m)",
    },
    "cmd.chaos.probes": {
        "de": "Stichproben für den Chaos-Test",
        "en": "probes for chaos test",
    },
    "cmd.chaos.intent": {
        "de": "Route-Intent für den Test",
        "en": "route intent for test",
    },
    "cmd.chaos.chat": {
        "de": "zusätzlich kleine Chats senden (kostet)",
        "en": "also send tiny chats (costs)",
    },
    "cmd.chaos.all": {
        "de": "alle Ausfälle beenden",
        "en": "stop all injects",
    },
    "cmd.paths": {
        "de": "Zeigt, wo Tollgate seine Dateien ablegt",
        "en": "Shows where Tollgate keeps its files",
    },
    "cmd.paths#expert": {
        "de": "Übertragbare Pfadübersicht ausgeben",
        "en": "Print portable path snapshot",
    },
    "cmd.consumer_add": {
        "de": "Einen Zugang anlegen, damit ein Werkzeug Tollgate benutzen darf",
        "en": "Create an access so a tool may use Tollgate",
    },
    "cmd.consumer_add#expert": {
        "de": "HTTP-Consumer anlegen (id:secret)",
        "en": "Add HTTP consumer (id:secret)",
    },
    "cmd.consumer_add.id": {
        "de": "Consumer-Kennung (z. B. n8n, gnom)",
        "en": "consumer id (e.g. n8n, gnom)",
    },
    "cmd.consumer_add.config": {
        "de": "/v1/config erlauben",
        "en": "allow /v1/config",
    },
    "cmd.consumer_add.secret": {
        "de": "festes Secret (optional)",
        "en": "optional fixed secret",
    },
    "cmd.consumer_add.label": {
        "de": "Anzeigename",
        "en": "display label",
    },
    "cmd.envelope": {
        "de": "Tagesgrenzen je Zugang setzen oder anzeigen — wieviel darf "
              "heute ausgegeben werden",
        "en": "Set or show the daily limit per access — how much may be "
              "spent today",
    },
    "cmd.envelope#expert": {
        "de": "Tages-Envelopes und Agentenschutz setzen oder auflisten "
              "(consumer_envelopes)",
        "en": "Set / list day envelopes + agent protection (consumer_envelopes)",
    },
    "cmd.envelope.id": {
        "de": "Consumer-Kennung (bei --list weglassen)",
        "en": "consumer id (omit with --list)",
    },
    "cmd.envelope.list": {
        "de": "alle Envelopes und ihren Verbrauch auflisten",
        "en": "list all envelopes + usage",
    },
    "cmd.envelope.allow_provider": {
        "de": "L3-Scope: Provider erlauben (mehrfach möglich); ersetzt die Liste "
              "allowed_providers",
        "en": "L3 scope: allow provider (repeatable); replaces allowed_providers list",
    },
    "cmd.envelope.block_provider": {
        "de": "L3-Scope: Provider sperren (mehrfach möglich)",
        "en": "L3 scope: block provider (repeatable)",
    },
    "cmd.envelope.allow_intent": {
        "de": "L3-Scope: Intent erlauben, z. B. free_llm,search (mehrfach möglich)",
        "en": "L3 scope: allow intent e.g. free_llm,search (repeatable)",
    },
    "cmd.envelope.block_intent": {
        "de": "L3-Scope: Intent sperren (mehrfach möglich)",
        "en": "L3 scope: block intent (repeatable)",
    },
    "cmd.envelope.allow_op": {
        "de": "L3-Scope: Operation erlauben, z. B. chat,search (mehrfach möglich)",
        "en": "L3 scope: allow op e.g. chat,search (repeatable)",
    },
    "cmd.envelope.block_op": {
        "de": "L3-Scope: Operation sperren (mehrfach möglich)",
        "en": "L3 scope: block op (repeatable)",
    },
    "cmd.envelope.clear_scopes": {
        "de": "alle allowed_*/blocked_*-Listen dieses Consumers entfernen",
        "en": "remove all allowed_*/blocked_* lists for this consumer",
    },
    "cmd.envelope.remove": {
        "de": "Envelope dieses Consumers entfernen (fällt auf _default zurück)",
        "en": "remove envelope for this consumer (fall back to _default)",
    },
    "cmd.distill": {
        "de": "Distill-JSON für einen neuen Provider anlegen",
        "en": "Scaffold distill JSON for a new provider",
    },
    "cmd.distill.provider": {
        "de": "Provider-Kennung (z. B. azure_openai)",
        "en": "provider id (e.g. azure_openai)",
    },
    "cmd.distill.title": {
        "de": "Anzeigetitel",
        "en": "display title",
    },
    "cmd.distill.env": {
        "de": "z. B. AZURE_OPENAI_API_KEY",
        "en": "e.g. AZURE_OPENAI_API_KEY",
    },
    "cmd.distill.high_risk": {
        "de": "als high_risk kennzeichnen (muss ausdrücklich freigegeben werden, "
              "mit engen $-Grenzen)",
        "en": "mark high_risk (must enable explicitly + tight $ caps)",
    },
    "cmd.high_risk": {
        "de": "high_risk_providers in keys_app.json auflisten oder setzen",
        "en": "List / set high_risk_providers in keys_app.json",
    },
    "cmd.doctor": {
        "de": "Installation und Konfiguration prüfen (erster Schritt nach der "
              "Einrichtung)",
        "en": "Self-diagnose install/config (first step after setup)",
    },
    "cmd.doctor.providers": {
        "de": "Provider zusätzlich live prüfen",
        "en": "include live provider diagnose",
    },
    "cmd.json": {
        "de": "maschinenlesbare Ausgabe",
        "en": "machine-readable output",
    },
    "cmd.advise": {
        "de": "Vorschläge für Routing und Budget aus dem Ledger (wird nie "
              "automatisch angewandt)",
        "en": "Propose routing/budget tweaks from ledger (never auto-applies)",
    },
    "cmd.desk": {
        "de": "Kurzer Lagebericht (Freeze · Resilience · Ausgaben · Auffälliges)",
        "en": "Compact desk status (freeze · resilience · spend · attention)",
    },
    "cmd.desk.json": {
        "de": "maschinenlesbares JSON (Vorgabe ist lesbarer Text)",
        "en": "machine-readable JSON (default is human text)",
    },
    "cmd.report_card": {
        "de": "AI Reliability Report — Zeugnis (PASS/FAIL für Protect · Route · Prove)",
        "en": "AI Reliability Report scorecard (PASS/FAIL for Protect·Route·Prove)",
    },
    "cmd.report_card.label": {
        "de": "Bezeichnung, z. B. Customer Support Agent",
        "en": "label e.g. Customer Support Agent",
    },
    "cmd.report_card.json": {
        "de": "JSON statt Textkarte",
        "en": "JSON instead of text card",
    },
    "cmd.demo": {
        "de": "Vorführung: Tool-Schleife eines Agenten blocken, optional mit "
              "Chaos-Nachweis",
        "en": "Killer demo: agent tool-loop block + optional chaos DR proof",
    },
    "cmd.demo.protect_only": {
        "de": "nur den Protect-Teil (kein Chaos-Test)",
        "en": "only Protect Aha (no chaos test)",
    },
    "cmd.demo.consumer": {
        "de": "Agenten-Spur (Vorgabe support-agent)",
        "en": "agent lane id (default support-agent)",
    },
    "cmd.demo.provider": {
        "de": "Provider für Chaos- und Aufrufversuch (Vorgabe opencode_zen)",
        "en": "provider for chaos / invoke attempt (default opencode_zen)",
    },
    "cmd.freeze": {
        "de": "Not-Aus — jede kostenpflichtige Zulassung verweigern",
        "en": "Emergency kill switch — deny all billable admission",
    },
    "cmd.freeze.state": {
        "de": "on (Vorgabe) | off/unfreeze | status",
        "en": "on (default) | off/unfreeze | status",
    },
    "cmd.freeze.reason": {
        "de": "Grund für den Freeze (Audit + Webhook)",
        "en": "why freeze (audit + webhook)",
    },
    "cmd.unfreeze": {
        "de": "Kurzform für: freeze off",
        "en": "Alias for: freeze off",
    },
    "cmd.circuit": {
        "de": "Schutzschalter auflisten oder zurücksetzen",
        "en": "List or reset circuit breakers",
    },
    "cmd.circuit.action": {
        "de": "list | reset | status",
        "en": "list | reset | status",
    },
    "cmd.circuit.provider": {
        "de": "Provider-Kennung zum Zurücksetzen (bei --all weglassen)",
        "en": "provider id for reset (omit with --all)",
    },
    "cmd.circuit.all": {
        "de": "jeden Schutzschalter zurücksetzen",
        "en": "reset every circuit",
    },
    "cmd.alerts": {
        "de": "Webhook-Meldungen: Zustellung testen oder Ereignisliste zeigen",
        "en": "Webhook alerts: test delivery or list event catalog",
    },
    "cmd.alerts.action": {
        "de": "test | events",
        "en": "test | events",
    },
    "cmd.alerts.message": {
        "de": "Text für die Testmeldung",
        "en": "message for alert test",
    },
    "cmd.snapshot": {
        "de": "Betriebszustand aus- und einlesen (tragbarer USB-Umzug)",
        "en": "Export/import desk ops state (portable USB migration)",
    },
    "cmd.snapshot.action": {
        "de": "export | import | info",
        "en": "export | import | info",
    },
    "cmd.snapshot.path": {
        "de": "Archivpfad (.tgz)",
        "en": "archive path (.tgz)",
    },
    "cmd.snapshot.out": {
        "de": "Ziel des Exports (Vorgabe: tollgate-snapshot-<tag>.tgz)",
        "en": "export destination (default: tollgate-snapshot-<day>.tgz)",
    },
    "cmd.snapshot.secrets": {
        "de": "Key.txt / .env mitnehmen (heikel — standardmäßig aus)",
        "en": "export Key.txt / .env (sensitive — off by default)",
    },
    "cmd.snapshot.no_audit": {
        "de": "audit.jsonl vom Export ausnehmen",
        "en": "omit audit.jsonl from export",
    },
    "cmd.snapshot.force": {
        "de": "Import: vorhandene Dateien überschreiben, auch keys_app.json",
        "en": "import: overwrite existing files, including keys_app.json",
    },
    "cmd.snapshot.merge_config": {
        "de": "Import: keys_app.json aus dem Archiv mit der lokalen Datei "
              "zusammenführen. Nur für eigene Snapshots — ein fremdes Archiv "
              "kann eine Provider-base_url umbiegen und damit die API-Keys.",
        "en": "import: deep-merge keys_app.json from the archive onto the local one. "
              "Only for snapshots you produced yourself — a foreign archive can "
              "redirect a provider base_url and with it your API keys.",
    },
    "cmd.snapshot.dry_run": {
        "de": "Import: Plan zeigen, ohne zu schreiben",
        "en": "import: show plan without writing",
    },
    "cmd.plan_status": {
        "de": "Tarif und Limits von Codex, Claude und Grok lesen (nur lesend, kein Modellaufruf)",
        "en": "Read Codex, Claude and Grok plan and limits (read-only, no model call)",
    },
    "cmd.plan_status.provider": {
        "de": "nur diesen Anbieter lesen",
        "en": "read only this provider",
    },
    "cmd.plan_status.no_live": {
        "de": "nur lokale Dateien, Codex app-server nicht fragen",
        "en": "local files only, do not ask the Codex app-server",
    },
    "cmd.plan_status.evaluate": {
        "de": "Prognose gegen echte Nutzungsbelege seit Zeitpunkt (ISO) prüfen",
        "en": "check the forecast against real usage evidence since a time (ISO)",
    },
    "cmd.plan_status.statusline": {
        "de": "Statusline-Eingabe von Claude Code lesen und protokollieren",
        "en": "read and log the Claude Code statusline input",
    },
    "cmd.plan_status.log": {
        "de": "Messprotokoll (JSONL), Vorgabe im TollGate-Datenordner",
        "en": "measurement log (JSONL), default in the TollGate data folder",
    },
    "cmd.report": {
        "de": "Täglicher Betriebsbericht — Nachweise für Protect · Route · Prove",
        "en": "Daily operator report — Protect · Route · Prove evidence",
    },
    "cmd.report.format": {
        "de": "md (Vorgabe) oder json",
        "en": "md (default) or json",
    },
    "cmd.report.out": {
        "de": "in Datei schreiben (optional)",
        "en": "write to file (optional)",
    },
    "cmd.audit": {
        "de": "Audit-Spur abfragen — wer wurde abgewiesen und warum (nur Betrieb)",
        "en": "Query audit trail — who was denied and why (ops only)",
    },
    "cmd.audit.event": {
        "de": "nach Ereignis filtern (admit_deny, usage, …)",
        "en": "filter event (admit_deny, usage, …)",
    },
    "cmd.audit.consumer": {
        "de": "nach Consumer- oder Agenten-Kennung filtern",
        "en": "filter consumer/agent id",
    },
    "cmd.audit.provider": {
        "de": "nach Provider-Kennung filtern",
        "en": "filter provider id",
    },
    "cmd.audit.limit": {
        "de": "höchste Zeilenzahl (Vorgabe 30)",
        "en": "max rows (default 30)",
    },
    "cmd.audit.summary": {
        "de": "Zusammenfassung: häufigste Ablehnungsgründe, nach Ereignis und "
              "Consumer",
        "en": "aggregates: top deny reasons + by event/consumer",
    },
    "cmd.audit.json": {
        "de": "maschinenlesbar (Vorgabe)",
        "en": "machine-readable (default)",
    },
    "cmd.search": {
        "de": "Module, Dokumente, HTTP und CLI durchsuchen (Code finden, ohne "
              "Pfade zu raten)",
        "en": "Search repo modules / docs / HTTP / CLI (find code without guessing paths)",
    },
    "cmd.search.query": {
        "de": "Suchbegriffe (z. B. circuit breaker); bei --map weglassen",
        "en": "search terms (e.g. circuit breaker); omit with --map",
    },
    "cmd.search.kind": {
        "de": "Filter: concept module doc http cli config script (mehrfach möglich)",
        "en": "filter: concept module doc http cli config script (repeatable)",
    },
    "cmd.search.limit": {
        "de": "höchste Trefferzahl (Vorgabe 15)",
        "en": "max hits (default 15)",
    },
    "cmd.search.map": {
        "de": "die ganze Repo-Karte als Markdown ausgeben (Inhalt von docs/MAP.md)",
        "en": "print full repo map markdown (docs/MAP.md body)",
    },
    # --- Ausgaben ---
    "out.search_usage": {
        "de": "Aufruf: tollgate search <suche> [--kind module] [--json]\n"
              "        tollgate search --map\n"
              "Beispiele: tollgate search circuit breaker\n"
              "           tollgate search budget --kind concept\n"
              "Karte: docs/MAP.md",
        "en": "usage: tollgate search <query> [--kind module] [--json]\n"
              "       tollgate search --map\n"
              "examples: tollgate search circuit breaker\n"
              "          tollgate search budget --kind concept\n"
              "map: docs/MAP.md",
    },
    "out.wrote": {
        "de": "geschrieben {path}",
        "en": "wrote {path}",
    },
    "out.demo_missing": {
        "de": "Vorführskript nicht gefunden — aus dem Repo-Verzeichnis starten:\n"
              "  ./scripts/demo-agent-safety.sh\n"
              "oder: docs/DEMO.md",
        "en": "demo script not found — run from repo checkout:\n"
              "  ./scripts/demo-agent-safety.sh\n"
              "or: docs/DEMO.md",
    },
    "out.use_header": {
        "de": "\nKopfzeile verwenden: X-Consumer-Key: {key}",
        "en": "\nUse header: X-Consumer-Key: {key}",
    },
    "out.config": {
        "de": "[tollgate] Konfiguration: {path}",
        "en": "[tollgate] config: {path}",
    },
    "out.error": {
        "de": "[tollgate] FEHLER: {message}",
        "en": "[tollgate] ERROR: {message}",
    },
    "out.open_mode": {
        "de": "[tollgate] offener Modus (lokaler Schreibtisch) · Dashboard "
              "http://{host}:{port}/dashboard",
        "en": "[tollgate] open mode (local desk) · dashboard "
              "http://{host}:{port}/dashboard",
    },
    # --- Dashboard (Control Room) ---
    "ui.wizard.skip": {
        "de": "Überspringen",
        "en": "Skip",
    },
    "ui.wizard.back": {
        "de": "Zurück",
        "en": "Back",
    },
    "ui.wizard.continue": {
        "de": "Weiter",
        "en": "Continue",
    },
    "ui.brand": {
        "de": "TOLLGATE",
        "en": "TOLLGATE",
    },
    "ui.setup": {
        "de": "Einrichten",
        "en": "Setup",
    },
    "ui.key": {
        "de": "Schlüssel",
        "en": "key",
    },
    "ui.tab.overview": {
        "de": "Überblick",
        "en": "Overview",
    },
    "ui.tab.agents": {
        "de": "Agenten",
        "en": "Agents",
    },
    "ui.tab.providers": {
        "de": "Anbieter",
        "en": "Providers",
    },
    "ui.tab.providers#expert": {
        "de": "Provider",
        "en": "Providers",
    },
    "ui.tab.prove": {
        "de": "Nachweis",
        "en": "Proof",
    },
    "ui.tab.prove#expert": {
        "de": "Prove",
        "en": "Prove",
    },
    "ui.tab.audit": {
        "de": "Protokoll",
        "en": "Log",
    },
    "ui.tab.audit#expert": {
        "de": "Audit",
        "en": "Audit",
    },
    "ui.control_room": {
        "de": "Leitstand",
        "en": "Control room",
    },
    "ui.control_room#expert": {
        "de": "Control Room",
        "en": "Control Room",
    },
    "ui.overview.lead": {
        "de": "Ist deine AI sicher, funktioniert sie, und was ist als Nächstes zu tun?",
        "en": "Is your AI safe, does it work, and what must you do next?",
    },
    "ui.reliability": {
        "de": "Verlässlichkeit",
        "en": "Reliability",
    },
    "ui.agents.heading": {
        "de": "Agenten · Ausgaben &amp; Grenzen",
        "en": "Agents · spend &amp; limits",
    },
    "ui.loading": {
        "de": "Wird geladen…",
        "en": "Loading…",
    },
    "ui.manage_limits": {
        "de": "Grenzen verwalten →",
        "en": "Manage limits →",
    },
    "ui.needs_attention": {
        "de": "Braucht Aufmerksamkeit",
        "en": "Needs attention",
    },
    "ui.recommendations": {
        "de": "Empfehlungen",
        "en": "Recommendations",
    },
    "ui.test_loop_block": {
        "de": "Endlosschleife testen",
        "en": "Test the endless-loop stop",
    },
    "ui.test_loop_block#expert": {
        "de": "Tool-Schleife testen",
        "en": "Test tool-loop block",
    },
    "ui.unfreeze": {
        "de": "Zulassung wieder freigeben",
        "en": "Unfreeze admission",
    },
    "ui.limits.intro_a": {
        "de": "Jede Spur (Agent / Anwendung) hat ihre eigenen harten Grenzen. Öffne",
        "en": "Each lane (agent / app) has its own hard limits. Open",
    },
    "ui.limits.edit": {
        "de": "Grenzen bearbeiten",
        "en": "Edit limits",
    },
    "ui.limits.intro_b": {
        "de": ", um Tages-, Stunden- und Request-Budget zu ändern.",
        "en": "to change day, hour, and per-request budgets.",
    },
    "ui.providers.lead": {
        "de": "Welcher Anbieter läuft gerade am besten — der Zustand von jetzt, "
              "nicht die Einstellungen.",
        "en": "Which provider works best right now — the state it is in, not "
              "the settings.",
    },
    "ui.providers.lead#expert": {
        "de": "Welcher Provider läuft gerade am besten — Zustand, keine Konfigurationsliste.",
        "en": "Which provider works best right now — health, not a config dump.",
    },
    "ui.col.provider": {
        "de": "Provider",
        "en": "Provider",
    },
    "ui.col.health": {
        "de": "Zustand",
        "en": "State",
    },
    "ui.col.health#expert": {
        "de": "Zustand",
        "en": "Health",
    },
    "ui.col.success": {
        "de": "Erfolg",
        "en": "Success",
    },
    "ui.col.latency": {
        "de": "Antwortzeit",
        "en": "Response time",
    },
    "ui.col.latency#expert": {
        "de": "Antwortzeit",
        "en": "Latency",
    },
    "ui.col.cost_day": {
        "de": "Kosten heute",
        "en": "Cost day",
    },
    "ui.col.circuit": {
        "de": "Schutzschalter",
        "en": "Safety switch",
    },
    "ui.col.circuit#expert": {
        "de": "Schutzschalter",
        "en": "Circuit",
    },
    "ui.prove.lead": {
        "de": "Schaltet es wirklich um — oder steht es nur in der Konfiguration?",
        "en": "Is failover real — or only configured?",
    },
    "ui.prove.test_title": {
        "de": "Umschalttest für Provider",
        "en": "Provider failover test",
    },
    "ui.prove.last_none": {
        "de": "Letzter Test: —",
        "en": "Last test: —",
    },
    "ui.prove.run": {
        "de": "Test starten",
        "en": "Run test",
    },
    "ui.prove.refresh_cert": {
        "de": "Zeugnis erneuern",
        "en": "Refresh the report",
    },
    "ui.prove.refresh_cert#expert": {
        "de": "Zeugnis erneuern",
        "en": "Refresh certificate",
    },
    "ui.audit.lead": {
        "de": "Was Tollgate durchgelassen, gestoppt oder auf einen anderen "
              "Anbieter umgeleitet hat. Keine Passwörter, keine Schlüssel.",
        "en": "What Tollgate let through, stopped, or sent to a different "
              "provider. No passwords, no keys.",
    },
    "ui.audit.lead#expert": {
        "de": "Was Tollgate zugelassen, geblockt oder umgeschaltet hat — nur Betrieb, keine Geheimnisse.",
        "en": "What Tollgate allowed, blocked, or failed over — ops only, no secrets.",
    },
    "ui.refresh": {
        "de": "Neu laden",
        "en": "Refresh",
    },
    "ui.denies_only": {
        "de": "Nur Ablehnungen",
        "en": "Denies only",
    },
    "ui.col.when": {
        "de": "Wann",
        "en": "When",
    },
    "ui.col.agent": {
        "de": "Agent",
        "en": "Agent",
    },
    "ui.col.event": {
        "de": "Ereignis",
        "en": "Event",
    },
    "ui.col.detail": {
        "de": "Detail",
        "en": "Detail",
    },
    "ui.footer.lead": {
        "de": "Sicherheitsschicht für AI-Agenten · kein Gateway-Katalog ·",
        "en": "Safety layer for AI agents · not a gateway catalog ·",
    },
    "ui.footer.api": {
        "de": "API",
        "en": "API",
    },
    "ui.footer.website": {
        "de": "Webseite",
        "en": "Website",
    },
    "ui.footer.github": {
        "de": "GitHub",
        "en": "GitHub",
    },
    "ui.footer.help": {
        "de": "tollgate help",
        "en": "tollgate help",
    },
    "ui.no_hard_limits": {
        "de": "Keine harten Grenzen",
        "en": "No hard limits",
    },
    "ui.agents.none_traffic": {
        "de": "Noch keine Agenten — schick Verkehr, dann setz die Grenzen unter Agenten.",
        "en": "No agents yet — send traffic, then set limits under Agents.",
    },
    "ui.nothing_urgent": {
        "de": "✓ Nichts Dringendes — Agenten unter Kontrolle",
        "en": "✓ Nothing urgent — agents under control",
    },
    "ui.open_arrow": {
        "de": "Öffnen →",
        "en": "Open →",
    },
    "ui.no_provider_traffic": {
        "de": "Noch kein Provider-Verkehr",
        "en": "No provider traffic yet",
    },
    "ui.agents.none": {
        "de": "Noch keine Agenten.",
        "en": "No agents yet.",
    },
    "ui.protect_first": {
        "de": "Ersten Agenten schützen",
        "en": "Protect first agent",
    },
    "ui.test_loop": {
        "de": "Schleife testen",
        "en": "Test loop",
    },
    "ui.budget.day": {
        "de": "Tagesbudget ($)",
        "en": "Day budget ($)",
    },
    "ui.budget.day_hint": {
        "de": "Harter Stopp für den Kalendertag",
        "en": "Hard stop for the calendar day",
    },
    "ui.budget.hour": {
        "de": "Stundenbudget ($)",
        "en": "Hour budget ($)",
    },
    "ui.budget.hour_hint": {
        "de": "Oft der Vorgabewert „$2“ — unabhängig vom Tag",
        "en": "Often the “$2” default — separate from day",
    },
    "ui.budget.request": {
        "de": "Max $ / Request",
        "en": "Max $ / request",
    },
    "ui.budget.request_hint": {
        "de": "Blockt einzelne Aufrufe, die zu groß sind",
        "en": "Blocks oversized single calls",
    },
    "ui.budget.tool_calls": {
        "de": "Max Tool-Aufrufe",
        "en": "Max tool-calls",
    },
    "ui.budget.tool_calls_hint": {
        "de": "Stoppt Agenten-Schleifen, die davonlaufen",
        "en": "Stops runaway agent loops",
    },
    "ui.budget.rpm": {
        "de": "Max Req / Minute",
        "en": "Max req / minute",
    },
    "ui.budget.rpm_hint": {
        "de": "Ratenbegrenzung je Spur",
        "en": "Rate limit per lane",
    },
    "ui.save_limits": {
        "de": "Grenzen speichern",
        "en": "Save limits",
    },
    "ui.cancel": {
        "de": "Abbrechen",
        "en": "Cancel",
    },
    "ui.no_provider_data": {
        "de": "Noch keine Provider-Daten",
        "en": "No provider data yet",
    },
    "ui.off": {
        "de": "(aus)",
        "en": "(off)",
    },
    "ui.health_score": {
        "de": "Zustandswert",
        "en": "Health score",
    },
    "ui.status": {
        "de": "Status",
        "en": "Status",
    },
    "ui.requests_today": {
        "de": "Requests heute",
        "en": "Requests today",
    },
    "ui.errors": {
        "de": "Fehler",
        "en": "Errors",
    },
    "ui.avg_latency": {
        "de": "Mittlere Antwortzeit",
        "en": "Average response time",
    },
    "ui.avg_latency#expert": {
        "de": "Mittlere Antwortzeit",
        "en": "Avg latency",
    },
    "ui.usd_today": {
        "de": "USD heute",
        "en": "USD today",
    },
    "ui.resilience": {
        "de": "Widerstandsfähigkeit",
        "en": "Resilience",
    },
    "ui.policy": {
        "de": "Regelwerk",
        "en": "Policy",
    },
    "ui.dr_history": {
        "de": "Notfall-Verlauf",
        "en": "DR history",
    },
    "ui.last_test": {
        "de": "Letzter Test:",
        "en": "Last test:",
    },
    "ui.never_run": {
        "de": "Nie gelaufen",
        "en": "Never run",
    },
    "ui.prove.needs_two": {
        "de": "Braucht ≥2 Provider in free_llm plus Schlüssel, dann den Test unten starten.",
        "en": "Needs ≥2 providers in free_llm + keys, then run the test below.",
    },
    "ui.report_title": {
        "de": "AI Reliability Report",
        "en": "AI Reliability Report",
    },
    "ui.no_audit_rows": {
        "de": "Noch keine Audit-Zeilen",
        "en": "No audit rows yet",
    },
    "ui.wizard.welcome": {
        "de": "Willkommen bei Tollgate",
        "en": "Welcome to Tollgate",
    },
    "ui.wizard.lead": {
        "de": "Schütze deinen ersten AI-Agenten — statt 50 Gateways einzurichten.",
        "en": "Protect your first AI agent — not configure 50 gateways.",
    },
    "ui.wizard.claim": {
        "de": "✓ Sicherheitsschicht zwischen Agenten und Providern",
        "en": "✓ Safety layer between agents and providers",
    },
    "ui.wizard.step1": {
        "de": "1 · Den Agenten benennen",
        "en": "1 · Name the agent",
    },
    "ui.wizard.step2": {
        "de": "2 · Schutz setzen (Budget + Tool-Schleifen)",
        "en": "2 · Set protection (budget + tool loops)",
    },
    "ui.wizard.step3": {
        "de": "3 · Nachweisen, dass es wirkt",
        "en": "3 · Prove it works",
    },
    "ui.wizard.who": {
        "de": "Wen schützen wir?",
        "en": "Who are we protecting?",
    },
    "ui.wizard.who_hint": {
        "de": "Name der Anwendung oder Agenten-Spur (consumer id).",
        "en": "Application / agent lane name (consumer id).",
    },
    "ui.wizard.app_name": {
        "de": "Name der Anwendung",
        "en": "Application name",
    },
    "ui.wizard.set_protection": {
        "de": "Schutz setzen",
        "en": "Set protection",
    },
    "ui.wizard.set_hint": {
        "de": "Harte Stopps vor der Rechnung. Nachschärfen kannst du später unter Agenten.",
        "en": "Hard stops before the invoice. You can tighten later under Agents.",
    },
    "ui.wizard.daily_budget": {
        "de": "Tagesbudget ($)",
        "en": "Daily budget ($)",
    },
    "ui.wizard.per_task": {
        "de": "Max $ / Aufgabe",
        "en": "Max $ / task",
    },
    "ui.wizard.tool_calls": {
        "de": "Max Tool-Aufrufe",
        "en": "Max tool calls",
    },
    "ui.wizard.rpm": {
        "de": "Max Requests / Min",
        "en": "Max requests / min",
    },
    "ui.wizard.protected": {
        "de": "Du bist geschützt",
        "en": "You’re protected",
    },
    "ui.wizard.lane": {
        "de": "Spur",
        "en": "Lane",
    },
    "ui.wizard.will_get": {
        "de": "bekommt harte Grenzen.",
        "en": "will get hard limits.",
    },
    "ui.wizard.ok_budget": {
        "de": "✓ Budget eingerichtet",
        "en": "✓ Budget configured",
    },
    "ui.wizard.ok_loop": {
        "de": "✓ Tool-Schleifen-Grenze aktiv",
        "en": "✓ Tool-loop limit enabled",
    },
    "ui.wizard.ok_rate": {
        "de": "✓ Ratenbegrenzung aktiv",
        "en": "✓ Rate limit enabled",
    },
    "ui.pill.day": {
        "de": "Tagesbudget",
        "en": "Day budget",
    },
    "ui.pill.hour": {
        "de": "Stundenbudget — oft der „$2“-Wert",
        "en": "Hour budget — often the “$2” value",
    },
    "ui.pill.request": {
        "de": "Pro Request",
        "en": "Per request",
    },
    "ui.pill.tool_stop": {
        "de": "Tool-Loop-Stop",
        "en": "Tool-loop stop",
    },
    "ui.key_hint": {
        "de": "Offener Modus: beliebige Bezeichnung · Anmeldemodus: id:secret",
        "en": "Open mode: any label · Auth mode: id:secret",
    },
    "ui.eg.5": {
        "de": "z. B. 5",
        "en": "e.g. 5",
    },
    "ui.eg.2": {
        "de": "z. B. 2",
        "en": "e.g. 2",
    },
    "ui.eg.050": {
        "de": "z. B. 0,50",
        "en": "e.g. 0.50",
    },
    "ui.eg.20": {
        "de": "z. B. 20",
        "en": "e.g. 20",
    },
    "ui.eg.40": {
        "de": "z. B. 40",
        "en": "e.g. 40",
    },
    "ui.lang_label_text": {
        "de": "Sprache",
        "en": "Language",
    },
    "ui.register_label_text": {
        "de": "Sprachebene",
        "en": "Wording",
    },
    "ui.register.plain": {
        "de": "Klartext",
        "en": "Plain",
    },
    "ui.register.expert": {
        "de": "Fachsprache",
        "en": "Expert",
    },
    "ui.register.plain_hint": {
        "de": "Kurze Sätze, keine Fachwörter. So startet Tollgate.",
        "en": "Short sentences, no jargon. This is how Tollgate starts.",
    },
    "ui.register.expert_hint": {
        "de": "Die Fachbegriffe, wenn du sie kennst.",
        "en": "The technical terms, if you know them.",
    },
    "ui.grade.good": {
        "de": "GUT",
        "en": "GOOD",
    },
    "ui.grade.fair": {
        "de": "MITTEL",
        "en": "FAIR",
    },
    "ui.grade.weak": {
        "de": "SCHWACH",
        "en": "WEAK",
    },
    "ui.stat.spent_today": {
        "de": "Heute ausgegeben",
        "en": "Spent today",
    },
    "ui.stat.requests": {
        "de": "Requests",
        "en": "Requests",
    },
    "ui.stat.success": {
        "de": "Erfolg",
        "en": "Success",
    },
    "ui.stat.agent_stops": {
        "de": "Agenten gestoppt",
        "en": "Agent stops",
    },
    "ui.stat.circuits_open": {
        "de": "Schalter offen",
        "en": "Circuits open",
    },
    "ui.stat.agents_protected": {
        "de": "Agenten geschützt",
        "en": "Agents protected",
    },
    "ui.no_day_cap": {
        "de": "keine Tagesgrenze",
        "en": "no day cap",
    },
    "ui.pill.day_short": {
        "de": "Tag",
        "en": "Day",
    },
    "ui.pill.hour_short": {
        "de": "Stunde",
        "en": "Hour",
    },
    "ui.pill.req_short": {
        "de": "Req",
        "en": "Req",
    },
    "ui.pill.tools_short": {
        "de": "Tools",
        "en": "Tools",
    },
    "ui.per_min": {
        "de": "/Min",
        "en": "/min",
    },
    "ui.suffix.req": {
        "de": "· Req",
        "en": "· req",
    },
    "ui.frozen_note": {
        "de": "Die Zulassung ist eingefroren — kein kostenpflichtiger Verkehr.",
        "en": "Admission is frozen — no billable traffic.",
    },
    "ui.prove_pending": {
        "de": "Prove steht aus: noch kein Umschalttest. Braucht ≥2 Provider plus Schlüssel.",
        "en": "Prove pending: no failover test yet. Needs ≥2 providers + keys.",
    },
    "ui.desk_protected": {
        "de": "Der Schreibtisch wirkt geschützt. Weiter mit echtem Verkehr.",
        "en": "Desk looks protected. Keep using real traffic.",
    },
    "ui.default_policy": {
        "de": "· Vorgabe-Regelwerk",
        "en": "· default policy",
    },
    "ui.spent_today_lower": {
        "de": "heute ausgegeben",
        "en": "spent today",
    },
    "ui.of_open": {
        "de": "von ",
        "en": "of ",
    },
    "ui.per_day": {
        "de": " / Tag",
        "en": " / day",
    },
    "ui.left_suffix": {
        "de": " übrig",
        "en": " left",
    },
    "ui.passed": {
        "de": "✓ BESTANDEN",
        "en": "✓ PASSED",
    },
    "ui.failed": {
        "de": "✗ DURCHGEFALLEN",
        "en": "✗ FAILED",
    },
    "ui.test_passed": {
        "de": "✓ TEST BESTANDEN",
        "en": "✓ TEST PASSED",
    },
    "ui.test_failed": {
        "de": "✗ TEST DURCHGEFALLEN",
        "en": "✗ TEST FAILED",
    },
    "ui.err.control_plane": {
        "de": "Lagebild konnte nicht geladen werden:",
        "en": "Failed to load control plane:",
    },
    "ui.cert_refreshed": {
        "de": "Zeugnis erneuert.",
        "en": "Certificate refreshed.",
    },
    "ui.running_test": {
        "de": "Umschalttest läuft…",
        "en": "Running failover test…",
    },
    "ui.err.test_start": {
        "de": "Test konnte nicht starten:",
        "en": "Test failed to start:",
    },
    "ui.testing_loop": {
        "de": "Prüfe den Schutz gegen Tool-Schleifen für",
        "en": "Testing tool-loop protection for",
    },
    "ui.err.test": {
        "de": "Test fehlgeschlagen:",
        "en": "Test failed:",
    },
    "ui.numbers_hint": {
        "de": "Zahlen ≥ 0 verwenden (leer = unbegrenzt)",
        "en": "Use numbers ≥ 0 (empty = unlimited)",
    },
    "ui.saving": {
        "de": "Wird gespeichert…",
        "en": "Saving…",
    },
    "ui.err.unfreeze": {
        "de": "Freigeben fehlgeschlagen:",
        "en": "Unfreeze failed:",
    },
    "ui.get_started": {
        "de": "Los geht’s",
        "en": "Get started",
    },
    "ui.err.name_required": {
        "de": "Bitte einen Anwendungsnamen eingeben",
        "en": "Enter an application name",
    },
    "ui.err.limit_required": {
        "de": "Mindestens ein Tagesbudget oder eine Obergrenze für Tool-Aufrufe setzen",
        "en": "Set at least a daily budget or max tool calls",
    },
    "ui.err.save_protection": {
        "de": "Schutz konnte nicht gespeichert werden:",
        "en": "Could not save protection:",
    },
    "ui.suffix.overall": {
        "de": "· gesamt",
        "en": "· overall",
    },
    "ui.limits_for_open": {
        "de": "Grenzen für «",
        "en": "Limits for «",
    },
    "ui.limits_for_close": {
        "de": "»",
        "en": "»",
    },
    "ui.eod_line": {
        "de": "Requests · Tokens · Tagesende ~",
        "en": "requests · tokens · EOD ~",
    },
    "out.auth_mode": {
        "de": "[tollgate] Anmeldemodus · http://{host}:{port}/dashboard",
        "en": "[tollgate] auth mode · http://{host}:{port}/dashboard",
    },
}


def normalise(language: str | None) -> str:
    """Gibt immer eine unterstuetzte Sprache zurueck."""
    if not language:
        return DEFAULT_LANGUAGE
    code = language.strip().lower().replace("_", "-").split("-", 1)[0]
    return code if code in LANGUAGES else DEFAULT_LANGUAGE


# Eigene Variable fuer die Sprachebene. Es gibt keine Locale dafuer, also
# gibt es auch nichts vom System zu erben.
REGISTER_VARIABLE = "TOLLGATE_MODE"


def register_from_environment(env: dict[str, str] | None = None) -> str:
    """Liest die Sprachebene aus der Umgebung. Ohne Angabe: Klartext."""
    source = os.environ if env is None else env
    return normalise_register(source.get(REGISTER_VARIABLE))


def from_environment(env: dict[str, str] | None = None) -> str:
    """Liest die Sprache aus den ueblichen Locale-Variablen."""
    source = os.environ if env is None else env
    for name in ENVIRONMENT_VARIABLES:
        raw = (source.get(name) or "").strip()
        code = raw.split(".", 1)[0].split("@", 1)[0]
        if code.lower() in NEUTRAL_LOCALES:
            continue
        return normalise(code)
    return DEFAULT_LANGUAGE


def from_accept_header(header: str | None) -> str:
    """Liest die erste unterstuetzte Sprache aus einem Accept-Language-Kopf."""
    if not header:
        return DEFAULT_LANGUAGE
    for chunk in header.split(","):
        code = chunk.split(";", 1)[0].strip().lower().replace("_", "-")
        base = code.split("-", 1)[0]
        if base in LANGUAGES:
            return base
    return DEFAULT_LANGUAGE


def normalise_register(register: str | None) -> str:
    """Gibt immer eine unterstuetzte Sprachebene zurueck."""
    if not register:
        return DEFAULT_REGISTER
    value = register.strip().lower()
    return value if value in REGISTERS else DEFAULT_REGISTER


def _entry(key: str, register: str) -> dict[str, str] | None:
    """Der Eintrag fuer diesen Schluessel auf dieser Ebene.

    Auf der Fachebene zaehlt die Variante `<schluessel>#expert`, wenn es sie
    gibt. Gibt es sie nicht, bleibt der Klartext stehen — die meisten Texte
    brauchen keine zweite Fassung, und einen Fachbegriff zu erfinden waere
    schlechter als der klare Satz.
    """
    if normalise_register(register) == EXPERT:
        variant = CATALOG.get(key + EXPERT_SUFFIX)
        if variant is not None:
            return variant
    return CATALOG.get(key)


def translate(key: str, language: str = DEFAULT_LANGUAGE,
              register: str = DEFAULT_REGISTER, **values: object) -> str:
    """Uebersetzt einen Schluessel.

    Ein unbekannter Schluessel gibt den Schluessel selbst zurueck, damit die
    Oberflaeche nicht zerbricht — der Test faengt ihn vorher ab.
    """
    entry = _entry(key, register)
    if entry is None:
        return key
    text = entry.get(normalise(language)) or entry[DEFAULT_LANGUAGE]
    return text.format(**values) if values else text


def catalog_for(language: str, register: str = DEFAULT_REGISTER) -> dict[str, str]:
    """Der ganze Katalog in einer Sprache.

    Die `#expert`-Varianten tauchen nicht als eigene Schluessel auf; sie sind
    bereits eingesetzt, wo die Fachebene gewaehlt ist.
    """
    code = normalise(language)
    keys = (key for key in CATALOG if not key.endswith(EXPERT_SUFFIX))
    return {key: (_entry(key, register) or CATALOG[key]).get(code)
                 or CATALOG[key][DEFAULT_LANGUAGE]
            for key in keys}
