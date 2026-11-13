"""Hilfetexte der Kommandozeile, zweisprachig.

Warum ein eigenes Modul: die Themen sind lange Bloecke und wuerden den
Katalog in i18n.py unlesbar machen. Die Regel bleibt dieselbe — kein
sichtbarer Text steht im Code, jeder Block gibt es in beiden Sprachen.

Befehle, Flags, Pfade, URLs und Umgebungsvariablen sind sprachneutral und
stehen in beiden Fassungen wortgleich. Uebersetzt wird nur die Prosa. Der
Test tests/test_i18n.py haelt fest, dass die Befehlszeilen nicht
auseinanderlaufen.
"""

from __future__ import annotations

TOPIC_NAMES = (
    "start", "protect", "route", "prove", "ui", "api",
    "ops", "troubleshoot", "commands", "env", "config", "faq",
)

TOPICS: dict[str, dict[str, str]] = {
    "start": {
        "en": """
# Start / install

  python3 -m venv .venv && .venv/bin/pip install -e .
  export TOLLGATE_HOME=$HOME/.tollgate
  tollgate serve                    # http://127.0.0.1:8787
  ./scripts/ten-minute.sh           # cold 10-minute path
  ./scripts/desk-ready.sh           # doctor + server + smoke

  Docker:  docker compose up -d --build
  UI:      http://127.0.0.1:8787/dashboard
  API:     http://127.0.0.1:8787/docs

  Keys (optional for Protect demo): $TOLLGATE_HOME/User/Key.txt
  Handbook: docs/HILFE.md · docs/USER_GUIDE.md · docs/TEN_MINUTE.md
""",
        "de": """
# Start / Installation

  python3 -m venv .venv && .venv/bin/pip install -e .
  export TOLLGATE_HOME=$HOME/.tollgate
  tollgate serve                    # http://127.0.0.1:8787
  ./scripts/ten-minute.sh           # kalter Weg in zehn Minuten
  ./scripts/desk-ready.sh           # doctor + Server + Rauchprobe

  Docker:  docker compose up -d --build
  UI:      http://127.0.0.1:8787/dashboard
  API:     http://127.0.0.1:8787/docs

  Schlüssel (für die Protect-Vorführung optional): $TOLLGATE_HOME/User/Key.txt
  Handbuch: docs/HILFE.md · docs/USER_GUIDE.md · docs/TEN_MINUTE.md
""",
    },
    "protect": {
        "en": """
# Protect — agent must never go out of control

  tollgate consumer-budget support-agent \\
    --max-usd-day 2 --max-usd-request 0.5 \\
    --max-tool-calls 20 --max-requests-minute 50

  tollgate consumer-budget support-agent \\
    --allow-provider opencode_zen --allow-intent free_llm --allow-op chat

  # Tool-loop Aha (no spend required)
  curl -s http://127.0.0.1:8787/v1/invoke \\
    -H 'Content-Type: application/json' \\
    -H 'X-Consumer-Key: support-agent' \\
    -d '{"provider":"opencode_zen","op":"chat","tool_calls_est":99,"arguments":{"message":"x"}}'

  # OpenAI drop-in: send tool_calls_est or tool history
  #   body:  "tool_calls_est": 12
  #   header: X-Tollgate-Tool-Calls-Est: 12
  #   auto:  count role=tool + assistant.tool_calls in messages
  # See docs/OPENAI.md

  tollgate freeze --reason "incident"   # kill switch
  tollgate unfreeze
  Dashboard: Overview → "Test tool-loop block"
""",
        "de": """
# Protect — ein Agent darf nie außer Kontrolle geraten

  tollgate consumer-budget support-agent \\
    --max-usd-day 2 --max-usd-request 0.5 \\
    --max-tool-calls 20 --max-requests-minute 50

  tollgate consumer-budget support-agent \\
    --allow-provider opencode_zen --allow-intent free_llm --allow-op chat

  # Der Aha-Moment mit der Tool-Schleife (kostet nichts)
  curl -s http://127.0.0.1:8787/v1/invoke \\
    -H 'Content-Type: application/json' \\
    -H 'X-Consumer-Key: support-agent' \\
    -d '{"provider":"opencode_zen","op":"chat","tool_calls_est":99,"arguments":{"message":"x"}}'

  # OpenAI-Ersatz: tool_calls_est oder die Tool-Historie mitschicken
  #   Body:    "tool_calls_est": 12
  #   Kopf:    X-Tollgate-Tool-Calls-Est: 12
  #   automatisch: role=tool + assistant.tool_calls in messages zählen
  # Siehe docs/OPENAI.md

  tollgate freeze --reason "incident"   # Not-Aus
  tollgate unfreeze
  Dashboard: Overview → "Test tool-loop block"
""",
    },
    "route": {
        "en": """
# Route — health-aware failover

  curl -s http://127.0.0.1:8787/v1/route \\
    -H 'Content-Type: application/json' -H 'X-Consumer-Key: desk' \\
    -d '{"intent":"free_llm","tokens_est":1000}'

  tollgate circuits list
  tollgate circuits reset deepseek
  tollgate circuits reset --all
""",
        "de": """
# Route — Umschalten nach Provider-Zustand

  curl -s http://127.0.0.1:8787/v1/route \\
    -H 'Content-Type: application/json' -H 'X-Consumer-Key: desk' \\
    -d '{"intent":"free_llm","tokens_est":1000}'

  tollgate circuits list
  tollgate circuits reset deepseek
  tollgate circuits reset --all
""",
    },
    "prove": {
        "en": """
# Prove — chaos / resilience / certificate

  tollgate chaos test opencode_zen --requests 10
  tollgate resilience
  tollgate certificate --application "Support Agent"
  tollgate demo                     # Protect + Prove live script

  Dashboard → Prove → Run test

  NOT_RUN / failed chaos is normal when:
    · only one provider in free_llm chain
    · missing keys (tollgate doctor)
  Protect (budgets / max_tool_calls) can PASS without chaos.
  Next: enable 2nd provider → Key.txt → chaos test → certificate
""",
        "de": """
# Prove — Chaos / Widerstandsfähigkeit / Zeugnis

  tollgate chaos test opencode_zen --requests 10
  tollgate resilience
  tollgate certificate --application "Support Agent"
  tollgate demo                     # Protect + Prove als Live-Ablauf

  Dashboard → Prove → Run test

  NOT_RUN oder ein fehlgeschlagener Chaos-Test ist normal, wenn:
    · nur ein Provider in der free_llm-Kette steht
    · Schlüssel fehlen (tollgate doctor)
  Protect (Budgets / max_tool_calls) kann auch ohne Chaos bestehen.
  Weiter: zweiten Provider aktivieren → Key.txt → Chaos-Test → Zeugnis
""",
    },
    "ui": {
        "en": """
# Control Room WebUI

  http://127.0.0.1:8787/dashboard

  Overview  — safe? broken? expensive? what to do?
  Agents    — budgets, edit protection, loop test
  Providers — health / latency / cost
  Prove     — chaos test + certificate
  Audit     — who was blocked

  Badge: PROTECTED | ATTENTION | FROZEN
  Setup wizard: first protected lane without CLI
""",
        "de": """
# Control Room — die Weboberfläche

  http://127.0.0.1:8787/dashboard

  Overview  — sicher? kaputt? teuer? was ist zu tun?
  Agents    — Budgets, Schutz bearbeiten, Schleifentest
  Providers — Zustand / Antwortzeit / Kosten
  Prove     — Chaos-Test + Zeugnis
  Audit     — wer wurde geblockt

  Abzeichen: PROTECTED | ATTENTION | FROZEN
  Einrichtungsassistent: erste geschützte Spur ganz ohne Kommandozeile
""",
    },
    "api": {
        "en": """
# HTTP surfaces (base http://127.0.0.1:8787)

  GET  /dashboard /docs /metrics
  GET  /v1/health /v1/control /v1/status /v1/certificate
  GET  /v1/audit /v1/budget /v1/resilience /v1/chaos
  POST /v1/route /v1/invoke /v1/chat/completions /v1/messages
  POST /v1/config /v1/chaos/test /v1/freeze /v1/circuits/reset

  OpenAI drop-in:
    export OPENAI_BASE_URL=http://127.0.0.1:8787/v1
    export OPENAI_API_KEY=support-agent

  Full OpenAPI: /docs  ·  Handbooks: docs/HILFE.md docs/USER_GUIDE.md
""",
        "de": """
# HTTP-Schnittstellen (Basis http://127.0.0.1:8787)

  GET  /dashboard /docs /metrics
  GET  /v1/health /v1/control /v1/status /v1/certificate
  GET  /v1/audit /v1/budget /v1/resilience /v1/chaos
  POST /v1/route /v1/invoke /v1/chat/completions /v1/messages
  POST /v1/config /v1/chaos/test /v1/freeze /v1/circuits/reset

  Als OpenAI-Ersatz:
    export OPENAI_BASE_URL=http://127.0.0.1:8787/v1
    export OPENAI_API_KEY=support-agent

  Vollständiges OpenAPI: /docs  ·  Handbücher: docs/HILFE.md docs/USER_GUIDE.md
""",
    },
    "ops": {
        "en": """
# Operations

  tollgate doctor
  tollgate status
  tollgate report --format md
  tollgate audit --event admit_deny --limit 20
  tollgate alert test
  tollgate snapshot export -o desk.tgz
  tollgate search circuit breaker

  Webhook: TOLLGATE_ALERT_WEBHOOK or cost_guard.alert_webhook_url
  Metrics auth: consumer key | TOLLGATE_METRICS_TOKEN | PUBLIC=1
  Portable: docs/PORTABLE.md · docs/OPERATIONS.md
""",
        "de": """
# Betrieb

  tollgate doctor
  tollgate status
  tollgate report --format md
  tollgate audit --event admit_deny --limit 20
  tollgate alert test
  tollgate snapshot export -o desk.tgz
  tollgate search circuit breaker

  Webhook: TOLLGATE_ALERT_WEBHOOK oder cost_guard.alert_webhook_url
  Anmeldung für Metrics: Consumer-Key | TOLLGATE_METRICS_TOKEN | PUBLIC=1
  Tragbar: docs/PORTABLE.md · docs/OPERATIONS.md
""",
    },
    "troubleshoot": {
        "en": """
# Troubleshooting

  Server won't start     → tollgate doctor · free port 8787 · Python ≥ 3.11
  401 Unauthorized       → auth mode needs id:secret · consumer-add
  Always blocked         → envelope / freeze status / scopes
  Chaos failed / NOT_RUN → ≥2 providers in free_llm · keys · doctor
  Loop never blocks      → send tool_calls_est (body/header) or tool history
  Stale dashboard        → hard refresh · check /v1/health version
  Wrong data home        → tollgate paths · echo $TOLLGATE_HOME
  Metrics 401            → token / consumer / TOLLGATE_METRICS_PUBLIC=1

  Log (desk): /tmp/tollgate-desk.log
  Docs: docs/OPENAI.md (tool_calls_est) · docs/FAQ.md
""",
        "de": """
# Fehlersuche

  Server startet nicht     → tollgate doctor · Port 8787 frei · Python ≥ 3.11
  401 Unauthorized         → Anmeldemodus braucht id:secret · consumer-add
  Immer geblockt           → Envelope / Freeze-Status / Scopes
  Chaos scheitert / NOT_RUN → ≥2 Provider in free_llm · Schlüssel · doctor
  Schleife blockt nie      → tool_calls_est senden (Body/Kopf) oder Tool-Historie
  Dashboard veraltet       → hart neu laden · /v1/health Version prüfen
  Falsches Datenverzeichnis → tollgate paths · echo $TOLLGATE_HOME
  Metrics 401              → Token / Consumer / TOLLGATE_METRICS_PUBLIC=1

  Protokoll (Schreibtisch): /tmp/tollgate-desk.log
  Doku: docs/OPENAI.md (tool_calls_est) · docs/FAQ.md
""",
    },
    "commands": {
        "en": """
# All CLI commands

  serve mcp health control resilience chaos paths
  consumer-add consumer-budget provider-add high-risk
  doctor suggest status certificate demo
  freeze unfreeze circuits alert snapshot
  report audit search help

  Examples:
    tollgate consumer-budget support-agent --max-usd-day 2 --max-tool-calls 20
    tollgate chaos test opencode_zen --requests 8
    tollgate certificate
    tollgate demo --skip-chaos
""",
        "de": """
# Alle Befehle der Kommandozeile

  serve mcp health control resilience chaos paths
  consumer-add consumer-budget provider-add high-risk
  doctor suggest status certificate demo
  freeze unfreeze circuits alert snapshot
  report audit search help

  Beispiele:
    tollgate consumer-budget support-agent --max-usd-day 2 --max-tool-calls 20
    tollgate chaos test opencode_zen --requests 8
    tollgate certificate
    tollgate demo --skip-chaos
""",
    },
    "env": {
        "en": """
# Environment variables

  TOLLGATE_HOME              data root (contains User/)
  GNOM_WS                    fallback data root
  TOLLGATE_CONFIG            absolute keys_app.json override
  GNOM_KEYS_CONFIG           alias for config override
  TOLLGATE_PORTABLE=1        portable path resolution
  TOLLGATE_REQUIRE_AUTH=1    force auth mode (id:secret)
  TOLLGATE_CONSUMERS         consumers.json path override
  TOLLGATE_FROZEN=1          kill switch (also TOLLGATE_ADMISSION_FROZEN)
  TOLLGATE_ALERT_WEBHOOK     alert URL (or cost_guard.alert_webhook_url)
  TOLLGATE_METRICS_TOKEN     Bearer for /metrics
  TOLLGATE_METRICS_PUBLIC=1  open /metrics (lab only)
  TOLLGATE_STRICT_CONFIG=1   hard-fail invalid config
  TOLLGATE_URL               client base (default http://127.0.0.1:8787)
  TOLLGATE_CONSUMER          client default lane
  TOLLGATE_LANG              output language: de or en
  HOST / PORT                tollgate serve bind (127.0.0.1 / 8787)

  Provider keys: $TOLLGATE_HOME/User/Key.txt or process env
  Handbook: docs/HILFE.md §18 · docs/USER_GUIDE.md §16
""",
        "de": """
# Umgebungsvariablen

  TOLLGATE_HOME              Datenwurzel (enthält User/)
  GNOM_WS                    Ausweich-Datenwurzel
  TOLLGATE_CONFIG            absoluter Pfad statt keys_app.json
  GNOM_KEYS_CONFIG           anderer Name für dieselbe Überschreibung
  TOLLGATE_PORTABLE=1        tragbare Pfadauflösung
  TOLLGATE_REQUIRE_AUTH=1    Anmeldemodus erzwingen (id:secret)
  TOLLGATE_CONSUMERS         anderer Pfad für consumers.json
  TOLLGATE_FROZEN=1          Not-Aus (auch TOLLGATE_ADMISSION_FROZEN)
  TOLLGATE_ALERT_WEBHOOK     Melde-URL (oder cost_guard.alert_webhook_url)
  TOLLGATE_METRICS_TOKEN     Bearer für /metrics
  TOLLGATE_METRICS_PUBLIC=1  /metrics offen (nur im Labor)
  TOLLGATE_STRICT_CONFIG=1   bei ungültiger Konfiguration hart abbrechen
  TOLLGATE_URL               Basis für den Client (Vorgabe http://127.0.0.1:8787)
  TOLLGATE_CONSUMER          Vorgabespur des Clients
  TOLLGATE_LANG              Ausgabesprache: de oder en
  HOST / PORT                Bindung von tollgate serve (127.0.0.1 / 8787)

  Provider-Schlüssel: $TOLLGATE_HOME/User/Key.txt oder Prozessumgebung
  Handbuch: docs/HILFE.md §18 · docs/USER_GUIDE.md §16
""",
    },
    "config": {
        "en": """
# Config (keys_app.json)

  Path: $TOLLGATE_HOME/User/keys_app.json
  Defaults: src/tollgate/app_config.py DEFAULT_CONFIG

  Main blocks:
    cost_guard          global $ cap, high_risk, soft_warn, webhook
    consumer_envelopes  per-lane budgets + scopes + tool_calls
    providers.<id>      enabled, max_usd_day, …
    circuits            breaker thresholds / cooldown
    reliability         Prove targets
    admission           freeze flags

  CLI:
    tollgate consumer-budget …     # envelopes
    tollgate high-risk list|add
    tollgate freeze / unfreeze

  HTTP:
    GET  /v1/config
    POST /v1/config   # deep-merge; invalid → 400 not written

  Detail: docs/COST_LIMITS.md · docs/HILFE.md §19
""",
        "de": """
# Konfiguration (keys_app.json)

  Pfad: $TOLLGATE_HOME/User/keys_app.json
  Vorgaben: src/tollgate/app_config.py DEFAULT_CONFIG

  Hauptblöcke:
    cost_guard          globale $-Grenze, high_risk, soft_warn, Webhook
    consumer_envelopes  Budgets je Spur + Scopes + tool_calls
    providers.<id>      enabled, max_usd_day, …
    circuits            Schwellen und Abkühlzeit der Schutzschalter
    reliability         Zielwerte für Prove
    admission           Freeze-Schalter

  Kommandozeile:
    tollgate consumer-budget …     # Envelopes
    tollgate high-risk list|add
    tollgate freeze / unfreeze

  HTTP:
    GET  /v1/config
    POST /v1/config   # tief zusammengeführt; ungültig → 400, nichts geschrieben

  Einzelheiten: docs/COST_LIMITS.md · docs/HILFE.md §19
""",
    },
    "faq": {
        "en": """
# FAQ (short)

  Keys for demo?     No for Protect tool-loop; yes for real chat/chaos
  vs LiteLLM?        LiteLLM routes models; Tollgate stops agents + proves DR
  Always blocked?    freeze · envelope · scope · audit --event admit_deny
  tool_calls_est?    Client must send loop depth for max_tool_calls
  Unlimited budget?  Set dimension to 0 (other dims still apply)
  Multi-worker?      Share TOLLGATE_HOME (see docs/STABILITY.md)
  Find code?         tollgate search <q> · tollgate search --map
  Full FAQ:          docs/FAQ.md · DE handbook docs/HILFE.md
""",
        "de": """
# Häufige Fragen (kurz)

  Schlüssel nötig?    Für die Protect-Schleife nein; für echten Chat/Chaos ja
  Gegenüber LiteLLM?  LiteLLM verteilt Modelle; Tollgate stoppt Agenten und
                      weist den Notfallbetrieb nach
  Immer geblockt?     freeze · Envelope · Scope · audit --event admit_deny
  tool_calls_est?     Der Client muss die Schleifentiefe für max_tool_calls senden
  Budget unbegrenzt?  Dimension auf 0 setzen (andere Dimensionen gelten weiter)
  Mehrere Prozesse?   TOLLGATE_HOME teilen (siehe docs/STABILITY.md)
  Code finden?        tollgate search <suche> · tollgate search --map
  Alle Fragen:        docs/FAQ.md · deutsches Handbuch docs/HILFE.md
""",
    },
}

OVERVIEW: dict[str, str] = {
    "en": """
Tollgate — safety layer for AI agents (Protect · Route · Prove)

  “My AI agent must never go out of control.”

Quick start
  ./scripts/ten-minute.sh
  tollgate serve
  open http://127.0.0.1:8787/dashboard

Help topics
  tollgate help start          install & cold path
  tollgate help protect        budgets, loops, freeze, scopes
  tollgate help route          failover & circuits
  tollgate help prove          chaos, resilience, certificate
  tollgate help ui             Control Room WebUI
  tollgate help api            HTTP / OpenAI drop-in
  tollgate help ops            doctor, audit, snapshot, alerts
  tollgate help troubleshoot   common failures
  tollgate help commands       full command list
  tollgate help env            environment variables
  tollgate help config         keys_app.json recipes
  tollgate help faq            short FAQ

Handbooks
  docs/HILFE.md        German detailed help
  docs/USER_GUIDE.md   English user guide
  docs/FAQ.md          FAQ
  docs/TEN_MINUTE.md   10-minute stranger test
  docs/DEMO.md         killer demo script
  docs/PRODUCT.md      positioning
  Website              https://landjunge.github.io/TollGate/

Repo search
  tollgate search <query>
  tollgate search --map
""",
    "de": """
Tollgate — Sicherheitsschicht für AI-Agenten (Protect · Route · Prove)

  „Mein AI-Agent darf nie außer Kontrolle geraten.“

Schnellstart
  ./scripts/ten-minute.sh
  tollgate serve
  http://127.0.0.1:8787/dashboard öffnen

Hilfe-Themen
  tollgate help start          Installation und kalter Weg
  tollgate help protect        Budgets, Schleifen, Freeze, Scopes
  tollgate help route          Umschalten und Schutzschalter
  tollgate help prove          Chaos, Widerstandsfähigkeit, Zeugnis
  tollgate help ui             Control Room, die Weboberfläche
  tollgate help api            HTTP / OpenAI-Ersatz
  tollgate help ops            doctor, Audit, Snapshot, Meldungen
  tollgate help troubleshoot   häufige Fehler
  tollgate help commands       vollständige Befehlsliste
  tollgate help env            Umgebungsvariablen
  tollgate help config         Rezepte für keys_app.json
  tollgate help faq            kurze Fragenliste

Handbücher
  docs/HILFE.md        ausführliche deutsche Hilfe
  docs/USER_GUIDE.md   englisches Benutzerhandbuch
  docs/FAQ.md          häufige Fragen
  docs/TEN_MINUTE.md   Zehn-Minuten-Test mit Fremden
  docs/DEMO.md         Ablauf der Vorführung
  docs/PRODUCT.md      Einordnung
  Webseite             https://landjunge.github.io/TollGate/

Im Repo suchen
  tollgate search <suche>
  tollgate search --map
""",
}

UNKNOWN_TOPIC: dict[str, str] = {
    "en": "Unknown topic: {topic!r}",
    "de": "Unbekanntes Thema: {topic!r}",
}
