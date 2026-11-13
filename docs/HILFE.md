# Tollgate — Hilfe & Handbuch

**Version:** 1.0.7 · **Repo:** https://github.com/landjunge/TollGate  

> **Tollgate ist die Sicherheits-Schicht zwischen deinen AI-Agents und dem Internet.**  
> Nicht „API-Gateway“, nicht „Multi-LLM-Katalog“.

**Killer-Use-Case:** *„Mein AI-Agent darf niemals außer Kontrolle geraten.“*

| Schnell | |
|---------|--|
| 10 Minuten (kalt) | [TEN_MINUTE.md](TEN_MINUTE.md) · `./scripts/ten-minute.sh` |
| Demo (Protect + Prove) | [DEMO.md](DEMO.md) · `tollgate demo` |
| Control Room | http://127.0.0.1:8787/dashboard |
| CLI-Hilfe | `tollgate help` · `tollgate help protect` · `tollgate help env` |
| FAQ | [FAQ.md](FAQ.md) |
| English guide | [USER_GUIDE.md](USER_GUIDE.md) |

---

## Inhaltsverzeichnis

1. [Was ist Tollgate?](#1-was-ist-tollgate)
2. [Installation](#2-installation)
3. [Daten & Secrets](#3-daten--secrets)
4. [Consumer (Agent-Lane)](#4-kernkonzept-consumer-agent-lane)
5. [Protect](#5-protect--agent-schützen)
6. [Route](#6-route--failover--health)
7. [Prove](#7-prove--resilienz-beweisen)
8. [Control Room (WebUI)](#8-control-room-webui)
9. [Clients anbinden](#9-clients-anbinden)
10. [CLI-Referenz](#10-cli-referenz)
11. [HTTP-API](#11-http-api-überblick)
12. [Webhooks & Metrics](#12-webhooks--metrics)
13. [Portable / Snapshot](#13-portable--snapshot)
14. [Troubleshooting](#14-troubleshooting)
15. [Sicherheit](#15-sicherheit-kurz)
16. [Dokumenten-Karte](#16-dokumenten-karte)
17. [Support](#17-support--mitmachen)
18. [Umgebungsvariablen (vollständig)](#18-umgebungsvariablen-vollständig)
19. [Config-Rezepte (`keys_app.json`)](#19-config-rezepte-keys_appjson)
20. [Admit-Entscheidungspfad](#20-admit-entscheidungspfad)
21. [Tagesablauf / Praxisrezepte](#21-tagesablauf--praxisrezepte)
22. [Glossar](#22-glossar)
23. [FAQ (Kurz)](#23-faq-kurz)

---

## 1. Was ist Tollgate?

Tollgate sitzt **vor** LLM-Providern und Tools:

```text
Agent / n8n / MCP-Client / OpenAI-SDK
              │
              ▼
           TOLLGATE
     Protect · Route · Prove
              │
     ┌────────┼────────┐
     ▼        ▼        ▼
  OpenAI  Anthropic  Zen/DeepSeek/…
```

### Drei Säulen

| Säule | Bedeutung | Typische Frage |
|-------|-----------|----------------|
| **Protect** | Budgets, Tool-Loop-Stops, Scopes, Freeze, Audit | Wird mein Agent teuer oder endlos? |
| **Route** | Health-aware Routing, Failover, Circuits | Was passiert, wenn OpenAI down ist? |
| **Prove** | Chaos-Test, Resilience-Score, Certificate | Kann ich das **beweisen**? |

### Was Tollgate **nicht** ist

- Kein Agent-Framework (kein LangGraph-Ersatz)
- Kein Speicher für Chat-Verläufe (nur Ops: Ledger, Audit, Circuits)
- Kein SaaS-Multi-Tenant-Katalog mit 100 Providern

### Abgrenzung (Wedge)

| | **Tollgate** | LiteLLM | Helicone |
|--|--------------|---------|----------|
| Kernjob | **Agent-Safety + DR-Proof** | Multi-Provider-Proxy | Observability |
| Pre-Admission Hard Deny | ✅ | optional | meist post-hoc |
| Chaos / Prove | ✅ first-class | DIY | — |

---

## 2. Installation

### Voraussetzungen

- **Python ≥ 3.11**
- Optional: Docker
- Optional: API-Keys (für echte LLM-Calls; **Protect-Demo braucht keine Keys**)

### Lokal

```bash
git clone https://github.com/landjunge/TollGate.git tollgate
cd tollgate
python3 -m venv .venv
.venv/bin/pip install -e .

export TOLLGATE_HOME=$HOME/.tollgate   # oder fester Datenordner
mkdir -p "$TOLLGATE_HOME/User"

# Server starten
tollgate serve
# → http://127.0.0.1:8787
```

Oder Desk-Bootstrap:

```bash
./scripts/desk-ready.sh
```

### Docker

```bash
docker compose up -d --build
docker compose exec tollgate tollgate certificate
# Dashboard: http://127.0.0.1:8787/dashboard
```

### Erster Erfolg (ohne Feature-Tour)

```bash
./scripts/ten-minute.sh
# oder
tollgate demo
tollgate certificate
```

| Schritt | Erwartung |
|---------|-----------|
| **Protect** | `🛑 REQUEST BLOCKED` bei Tool-Loop (ohne $) |
| **Prove** | Chaos/Failover läuft oder klarer Next-Step |
| **Result** | Certificate-Scorecard + Control Room |

Wenn dieser Pfad unklar ist: **keine neuen Features** — den Pfad reparieren.

---

## 3. Daten & Secrets

### Datenverzeichnis

| Variable | Bedeutung |
|----------|-----------|
| `TOLLGATE_HOME` | Datenwurzel (enthält `User/`) |
| `GNOM_WS` | Fallback (Gnom-Kompatibilität) |
| Default | oft `~/.tollgate` |

Unter `$TOLLGATE_HOME/User/`:

| Datei | Inhalt |
|-------|--------|
| `Key.txt` | API-Keys (nie committen) |
| `keys_app.json` | Limits, Routing, Envelopes, Freeze |
| `keys_usage.json` | Tages-Ledger (Calls, Tokens, $) |
| `consumers.json` | gehashte Consumer-Secrets (Auth-Modus) |
| `circuits.json` | Circuit-Breaker-Zustand |
| `audit.jsonl` | Append-only Audit |
| `chaos.json` | Chaos/DR-Status |

Vorlage Keys: `Key.txt.example` → nach `User/Key.txt` kopieren.

```bash
# Beispiel Key.txt
OPENCODE_API_KEY=…
DEEPSEEK_API_KEY=…
BRAVE_API_KEY=…
```

```bash
tollgate doctor          # prüft Pfade, Keys, Caps
tollgate paths           # zeigt data_home
```

**Regel:** Secrets nur in Tollgate — nie in Agent-Prompts oder n8n-Env mit echten Provider-Keys.

---

## 4. Kernkonzept: Consumer (Agent-Lane)

Ein **Consumer** ist eine logische Lane, z. B.:

- `support-agent`
- `coding-agent`
- `n8n`

Jeder Request trägt eine Identität:

```http
X-Consumer-Key: support-agent
# oder Auth-Modus:
X-Consumer-Key: support-agent:geheimes-token
Authorization: Bearer support-agent:geheimes-token
```

### Open Mode vs Auth Mode

| | Open Mode | Auth Mode |
|--|-----------|-----------|
| Wann | keine `consumers.json` / leer | Einträge vorhanden oder `TOLLGATE_REQUIRE_AUTH=1` |
| Key | beliebiges Label (z. B. `desk`) | `id:secret` |
| Desk | lokal ok | Pflicht bei Multi-Host / n8n remote |

```bash
tollgate consumer-add n8n
tollgate consumer-add desk --admin
# Secret wird EINMAL angezeigt — speichern!
```

Admin-Scope (`--admin`) darf Policy patchen (`POST /v1/config`, Circuits-Reset, Chaos-Test, …).

---

## 5. Protect — Agent schützen

### Budget & Loop-Limits setzen

```bash
tollgate consumer-budget support-agent \
  --max-usd-day 2 \
  --max-usd-request 0.5 \
  --max-usd-hour 1 \
  --max-requests-minute 50 \
  --max-tool-calls 20 \
  --max-tokens-request 50000 \
  --max-calls-day 500 \
  --max-tokens-day 500000

tollgate consumer-budget --list
```

| Feld | Wirkung |
|------|---------|
| `max_usd_day` | Tagesbudget $ |
| `max_usd_request` | Hartes Limit pro Request (Schätzung) |
| `max_usd_hour` | Stundenfenster |
| `max_requests_minute` | RPM |
| `max_tool_calls` | **Tool-Loop-Tiefe** pro Turn |
| `max_tokens_request` | Token-Schätzung pro Request |
| `max_calls_day` / `max_tokens_day` | Tages-Counts |

`0` / weglassen = unbeschränkt **auf dieser Dimension** (andere Dimensionen können greifen).

### Defaults (Protect-on-by-default)

Neue Installs bekommen `_default` mit sicheren Caps (u. a. ~$5/Tag global, 60 RPM, 25 Tool-Calls, $0.50/Request). Siehe [COST_LIMITS.md](COST_LIMITS.md).

```bash
# Unbekannte Lanes enger
tollgate consumer-budget _default --max-usd-day 1 --max-requests-minute 30
# Eine Dimension freigeben (Escape Hatch)
tollgate consumer-budget desk --max-usd-day 0
# Envelope löschen → fällt auf _default zurück
tollgate consumer-budget support-agent --clear
```

### Scopes (wer darf was)

```bash
tollgate consumer-budget support-agent \
  --allow-provider opencode_zen --allow-provider deepseek \
  --block-provider google \
  --allow-intent free_llm --allow-intent llm \
  --allow-op chat --allow-op search

tollgate consumer-budget support-agent --clear-scopes
```

| Scope-Liste | Semantik |
|-------------|----------|
| `allowed_*` leer | auf dieser Achse unrestricted |
| `blocked_*` | **gewinnt immer** (Deny) |
| Deny-Reason | enthält `scope:` / `protection: scope` |

### Tool-Loop demonstrieren (Aha #1)

Clients senden die **geschätzte Loop-Tiefe**:

```bash
curl -s http://127.0.0.1:8787/v1/invoke \
  -H 'Content-Type: application/json' \
  -H 'X-Consumer-Key: support-agent' \
  -d '{
    "provider": "opencode_zen",
    "op": "chat",
    "tool_calls_est": 99,
    "arguments": {"message": "hi"},
    "agent_id": "support-agent"
  }'
```

Antwort enthält u. a.:

```json
"blocked": {
  "headline": "REQUEST BLOCKED",
  "reason": "max_tool_calls",
  "tool_calls": { "est": 99, "max": 20 },
  "message": "🛑 REQUEST BLOCKED\n…"
}
```

Im **Dashboard**: Overview → „Test tool-loop block“ oder Agents → „Test loop“.

> **Wichtig:** Clients müssen `tool_calls_est` (oder Äquivalent) mitschicken. Ohne Schätzung kann Tollgate die Loop-Tiefe nicht hard-denyen.

### Globaler Kill-Switch (Freeze)

```bash
tollgate freeze --reason "runaway agents"
tollgate freeze status
tollgate unfreeze
# Env: TOLLGATE_FROZEN=1  (oder TOLLGATE_ADMISSION_FROZEN=1)
```

Billable Traffic wird verweigert. System-Probes können weiterlaufen (`allow_system_when_frozen`).

### Globale Cost Guard

Zusätzlich zu Lane-Envelopes:

- `cost_guard.max_usd_day_global` (Default 5.0)
- High-Risk-Provider (Google etc.) default **off** bis explizit enabled + caps
- Soft-Warn bei ~80 % Budget (`soft_warn_ratio`) → optional Webhook

```bash
tollgate high-risk list
tollgate high-risk add azure_openai
```

---

## 6. Route — Failover & Health

Routing wählt Provider nach Intent (`free_llm`, `llm`, `search`, …), Limits und Health.

```bash
curl -s http://127.0.0.1:8787/v1/route \
  -H 'Content-Type: application/json' \
  -H 'X-Consumer-Key: support-agent' \
  -d '{"intent":"free_llm","tokens_est":1000}'
```

Antwort kann `explain` enthalten: **warum** dieser Provider.

Circuits (Breaker pro Provider/Model/Key):

```bash
tollgate circuits list
tollgate circuits reset deepseek
tollgate circuits reset --all
```

Defaults in Config (`circuits.*`): `failure_threshold`, `cooldown_s`, `hard_cooldown_s`, Jitter gegen Thundering Herd.

---

## 7. Prove — Resilienz beweisen

```bash
# Provider-Ausfall simulieren + Failover messen
tollgate chaos test opencode_zen --requests 10
tollgate resilience
tollgate certificate --application "Customer Support Agent"
tollgate demo                     # Protect + Prove live
tollgate demo --skip-chaos        # nur Protect
```

Dashboard → **Prove** → „Run test“.

Certificate-Scorecard:

```text
Budget Protection       PASS
Agent Loop Protection   PASS
Provider Failover       PASS / NOT_RUN
…
Resilience Score        nn/100
```

Chaos braucht typischerweise **≥2 Provider** in der Intent-Chain und gültige Keys für den echten Pfad.

---

## 8. Control Room (WebUI)

**URL:** http://127.0.0.1:8787/dashboard  

| Bereich | Frage |
|---------|--------|
| **Overview** | Sicher? Kaputt? Zu teuer? Was tun? |
| **Agents** | Protection, Budgets, Loop-Test, Edit |
| **Providers** | Health, Latency, Kosten |
| **Prove** | Chaos-Test, Certificate |
| **Audit** | Wer wurde geblockt / warum |

Status-Badge oben: **PROTECTED** · **ATTENTION** · **FROZEN**

**Setup-Wizard** (erster Start / Button „Setup“):

1. Welcome  
2. Agent-Name  
3. Protection ($/Tag, $/Task, Tool-Calls, RPM)  
4. Speichern → optional sofort Loop-Test  

Feld **key** (oben rechts): im Open Mode beliebiges Label; im Auth Mode `id:secret`.  
Label wird in `localStorage` gehalten.

OpenAPI: http://127.0.0.1:8787/docs  

---

## 9. Clients anbinden

### OpenAI-kompatibel (größter Hebel)

```bash
export OPENAI_BASE_URL=http://127.0.0.1:8787/v1
export OPENAI_API_KEY=support-agent   # oder id:secret
# model: tollgate/free | tollgate/auto | provider-modell
```

```bash
curl -s $OPENAI_BASE_URL/chat/completions \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "tollgate/free",
    "messages": [{"role":"user","content":"hi"}],
    "max_tokens": 64,
    "tool_calls_est": 3
  }'
```

Extras: `tool_calls_est`, `tokens_est`, `prefer_free`, `request_class`.  
Header bei Erfolg: `X-Tollgate-Provider`, `X-Tollgate-Model`, …  
Bei Deny: `error.tollgate` + `Retry-After` / `X-Tollgate-Protection`.

Details: [OPENAI.md](OPENAI.md)

### Anthropic Messages

`POST /v1/messages` · [ANTHROPIC.md](ANTHROPIC.md)

### n8n

- Community-Node: `n8n-nodes-tollgate/`
- Oder OpenAI-Node mit `base_url` → Tollgate  
- [N8N.md](N8N.md)

### MCP (Cursor / Claude Desktop)

```bash
python -m tollgate
# oder: tollgate mcp
```

Beispiel-Config: `configs/mcp-tollgate.example.json` · [MCP.md](MCP.md)

### Python Client (intern)

```python
from tollgate.client import TollgateClient  # falls genutzt
# TOLLGATE_URL, TOLLGATE_CONSUMER
```

---

## 10. CLI-Referenz

```bash
tollgate help                 # Themen-Übersicht
tollgate help protect
tollgate help prove
tollgate help env
tollgate help faq
tollgate help config
tollgate help ui
```

| Befehl | Zweck |
|--------|--------|
| `serve` | HTTP-Server (Default `HOST=127.0.0.1` `PORT=8787`) |
| `mcp` | MCP stdio |
| `doctor` | Diagnose (nach Install zuerst) |
| `health` / `paths` / `status` | Zustand |
| `control` | Control-Plane JSON (UI-Daten) |
| `certificate` | AI Reliability Report |
| `demo` | Live Protect+Prove Demo |
| `consumer-add` | Auth-Consumer anlegen |
| `consumer-budget` | Envelopes + Scopes |
| `chaos` | status / start / stop / test |
| `resilience` | Score 0–100 |
| `freeze` / `unfreeze` | Kill-Switch |
| `circuits` | list / reset |
| `audit` | Audit-Trail abfragen |
| `report` | Tagesbrief (md/json) |
| `alert` | Webhook test / events |
| `snapshot` | export / import Desk-State |
| `search` | Repo-Doku/Module suchen |
| `high-risk` / `provider-add` | Provider-Risiko / Scaffold |
| `suggest` | Vorschläge aus Ledger (nie auto-apply) |

### Häufige Beispiele

```bash
tollgate doctor
tollgate status
tollgate consumer-budget support-agent --max-usd-day 2 --max-tool-calls 20
tollgate chaos test opencode_zen --requests 8
tollgate certificate --application "Support Agent"
tollgate audit --event admit_deny --limit 20
tollgate freeze --reason "incident"
tollgate snapshot export -o desk.tgz
tollgate report --format md
tollgate search circuit breaker
tollgate search --map
```

### `consumer-budget` Flags (komplett)

```text
--list
--max-calls-day --max-tokens-day --max-usd-day
--max-usd-request --max-usd-hour --max-requests-minute
--max-tokens-request --max-tool-calls
--allow-provider / --block-provider   (wiederholbar)
--allow-intent / --block-intent
--allow-op / --block-op
--clear-scopes   # nur Scope-Listen
--clear          # ganzes Envelope → _default
```

---

## 11. HTTP-API (Überblick)

Basis: `http://127.0.0.1:8787`

| Methode | Pfad | Zweck |
|---------|------|--------|
| GET | `/dashboard` | Control Room UI |
| GET | `/docs` | OpenAPI |
| GET | `/v1/health` | Liveness + Freeze + Circuits |
| GET | `/v1/control` | Control-Plane (UI-Daten) |
| GET | `/v1/status` | Kompakter Status |
| GET | `/v1/certificate` | Scorecard |
| GET | `/v1/resilience` | Resilience JSON |
| GET | `/v1/chaos` | Chaos-Status |
| POST | `/v1/chaos/test` | Failover-Test (admin) |
| GET | `/v1/audit` | Audit-Query |
| GET | `/v1/budget` | Budget der Lane |
| GET/POST | `/v1/config` | Policy lesen/patchen (admin) |
| POST | `/v1/route` | Intent → Provider |
| POST | `/v1/invoke` | Admit + Call |
| POST | `/v1/chat/completions` | OpenAI Drop-in |
| POST | `/v1/messages` | Anthropic Drop-in |
| GET | `/v1/models` | Modell-Liste (Drop-in) |
| GET/POST | `/v1/freeze` | Kill-Switch |
| GET | `/v1/circuits` | Circuits |
| POST | `/v1/circuits/reset` | Reset (admin) |
| GET | `/metrics` | Prometheus (ggf. Auth) |

Vollständige Signaturen: laufender Server → `/docs`.

### Config patchen (HTTP)

```bash
curl -s http://127.0.0.1:8787/v1/config | jq .

curl -s -X POST http://127.0.0.1:8787/v1/config \
  -H 'Content-Type: application/json' \
  -H 'X-Consumer-Key: desk' \
  -d '{"cost_guard":{"max_usd_day_global":3.0}}'
```

Invalid patches → **HTTP 400**, Datei wird nicht geschrieben (Schema-Validierung).

---

## 12. Webhooks & Metrics

### Alerts

```bash
export TOLLGATE_ALERT_WEBHOOK=https://…
# oder keys_app.json → cost_guard.alert_webhook_url
tollgate alert events
tollgate alert test
```

Events u. a.: `agent_protection`, `hard_deny`, `soft_budget`, `chaos_*`, `admission_frozen`.

### Metrics

```bash
curl -s http://127.0.0.1:8787/metrics
# Auth-Mode: Consumer-Key oder TOLLGATE_METRICS_TOKEN
# Öffentlich erzwingen: TOLLGATE_METRICS_PUBLIC=1
```

---

## 13. Portable / Snapshot

```bash
tollgate snapshot export -o desk.tgz      # ohne Key.txt
tollgate snapshot import desk.tgz
tollgate snapshot export -o full.tgz --include-secrets   # vorsichtig!
```

USB: [PORTABLE.md](PORTABLE.md)

---

## 14. Troubleshooting

| Symptom | Prüfung |
|---------|---------|
| Server startet nicht | `tollgate doctor` · Port 8787 frei? · Python ≥ 3.11 |
| 401 Unauthorized | Auth-Mode: `id:secret`? · `tollgate consumer-add` |
| Immer blocked | Envelope zu eng? · `freeze status`? · Scope? |
| Chaos „failed“ | ≥2 Provider in Intent-Chain? · Keys gesetzt? |
| Dashboard leer / alt | Hard-Refresh · `X-Consumer-Key` oben · Server-Version `/v1/health` |
| Metrics 401 | Token/Consumer oder `TOLLGATE_METRICS_PUBLIC=1` |
| Ledger / Budgets „kaputt“ | fail-closed by design · `keys_usage.json` prüfen |
| Falsche Daten-Home | `tollgate paths` · `echo $TOLLGATE_HOME` |
| Config-Patch 400 | Schema invalid · `TOLLGATE_STRICT_CONFIG=1` + doctor |
| Multi-Worker Drift | alle Worker gleiche `TOLLGATE_HOME` |

Logs bei Desk-Start oft: `/tmp/tollgate-desk.log`

Mehr: [FAQ.md](FAQ.md) · `tollgate help troubleshoot`

---

## 15. Sicherheit (Kurz)

- Keys nur in `Key.txt` / Env, nie im Agent  
- Auth-Mode für alles außer reinem Localhost  
- Metrics & Config nicht ungeschützt im Internet  
- Audit/Redaction: keine Chat-Transcripts im Ledger  
- Freeze bei Incident  
- High-Risk-Provider (Google) default **off**  
- Snapshot ohne Secrets exportieren, außer bewusst  

---

## 16. Dokumenten-Karte

| Doc | Inhalt |
|-----|--------|
| [TEN_MINUTE.md](TEN_MINUTE.md) | Kalter 10-Minuten-Test |
| [DEMO.md](DEMO.md) | Killer-Demo Protect + Prove |
| [FAQ.md](FAQ.md) | Häufige Fragen |
| [GETTING_STARTED.md](GETTING_STARTED.md) | Setup-Schritte |
| [PRODUCT.md](PRODUCT.md) | Positionierung |
| [COST_LIMITS.md](COST_LIMITS.md) | Envelopes im Detail |
| [OPENAI.md](OPENAI.md) / [ANTHROPIC.md](ANTHROPIC.md) | Drop-ins |
| [N8N.md](N8N.md) / [MCP.md](MCP.md) | Integrationen |
| [OPERATIONS.md](OPERATIONS.md) | Betrieb |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Schichten |
| [MAP.md](MAP.md) | Code-Index |
| [USER_GUIDE.md](USER_GUIDE.md) | English handbook |
| [STABILITY.md](STABILITY.md) | Multi-Worker, Schema |
| [PORTABLE.md](PORTABLE.md) | USB / Migration |

CLI: `tollgate search <begriff>` · `tollgate search --map`

---

## 17. Support / Mitmachen

- Issues & Code: https://github.com/landjunge/TollGate  
- Feedback zur **10-Minuten-Reibung** ist wertvoller als Feature-Wünsche.  
- Lizenz: MIT  

**Pay the toll — or don't call.**

---

## 18. Umgebungsvariablen (vollständig)

| Variable | Zweck | Default / Hinweis |
|----------|--------|-------------------|
| `TOLLGATE_HOME` | Datenwurzel (`User/`) | `~/.tollgate` o. ä. |
| `GNOM_WS` | Fallback-Datenwurzel | Gnom-Kompat |
| `TOLLGATE_CONFIG` | Absolute Config-Override | sonst `User/keys_app.json` |
| `GNOM_KEYS_CONFIG` | Alias für Config-Override | — |
| `TOLLGATE_PORTABLE` | Portable Path-Auflösung | `0` / `1` |
| `TOLLGATE_REQUIRE_AUTH` | Auth-Mode erzwingen | off wenn consumers leer |
| `TOLLGATE_CONSUMERS` | Consumers-Pfad Override | — |
| `TOLLGATE_FROZEN` | Kill-Switch via Env | `1` = frozen |
| `TOLLGATE_ADMISSION_FROZEN` | Alias Freeze | — |
| `TOLLGATE_ALERT_WEBHOOK` | Alert-URL | oder Config |
| `TOLLGATE_METRICS_TOKEN` | Metrics Bearer | — |
| `TOLLGATE_METRICS_PUBLIC` | Metrics ohne Auth | `1` = public |
| `TOLLGATE_STRICT_CONFIG` | Config-Validierung hard-fail | soft by default |
| `TOLLGATE_URL` | Client Base-URL | `http://127.0.0.1:8787` |
| `TOLLGATE_CONSUMER` | Client Default-Lane | `gnom` |
| `TOLLGATE_STREAM_SYNTHETIC` | Stream-Dev-Hilfe | selten |
| `HOST` / `PORT` | `tollgate serve` Bind | `127.0.0.1` / `8787` |

Provider-Keys liegen in `User/Key.txt` **oder** als Prozess-Env (z. B. `OPENCODE_API_KEY`, `DEEPSEEK_API_KEY`, …) — siehe `Key.txt.example` und `tollgate doctor`.

```bash
tollgate help env
```

---

## 19. Config-Rezepte (`keys_app.json`)

Ort: `$TOLLGATE_HOME/User/keys_app.json` (wird beim ersten Start aus Defaults geschrieben).

### Minimal: Lane enger

```json
{
  "consumer_envelopes": {
    "support-agent": {
      "max_usd_day": 2.0,
      "max_usd_request": 0.5,
      "max_tool_calls": 15,
      "max_requests_minute": 30,
      "allowed_providers": ["opencode_zen", "deepseek"],
      "blocked_providers": ["google"],
      "allowed_intents": ["free_llm", "llm"],
      "allowed_ops": ["chat"]
    }
  }
}
```

### Globaler Cost Cap + High Risk

```json
{
  "cost_guard": {
    "enabled": true,
    "max_usd_day_global": 3.0,
    "soft_warn_ratio": 0.8,
    "alert_webhook_url": "https://hooks.example/tollgate",
    "high_risk_providers": ["google", "gemini", "vertex"]
  },
  "providers": {
    "google": {
      "enabled": false,
      "max_usd_day": 0.5,
      "max_calls_day": 10
    }
  }
}
```

### Reliability-Ziele (Prove)

```json
{
  "reliability": {
    "availability_target": 99.9,
    "max_failover_time_s": 5.0,
    "required_fallbacks": 2,
    "gradual_recovery_s": 60.0
  }
}
```

### Freeze in Config

```json
{
  "admission": {
    "frozen": false,
    "frozen_reason": "",
    "allow_system_when_frozen": true
  }
}
```

Besser über CLI: `tollgate freeze` / `unfreeze`.

Vollständige Defaults: `src/tollgate/app_config.py` → `DEFAULT_CONFIG`.  
Feld-Detail: [COST_LIMITS.md](COST_LIMITS.md).

---

## 20. Admit-Entscheidungspfad

Jeder billable Call läuft grob so (fail-closed wo sinnvoll):

```text
Request
  → Auth (Open vs id:secret)
  → Freeze?  → DENY (admission_frozen)
  → Consumer envelope / scopes
  → Agent guard (tool_calls, rpm, $/request, …)
  → Cost guard global / provider caps
  → Circuit open? → try failover / DENY
  → Route (intent, prefer_free, health)
  → Invoke provider
  → Ledger + Audit + Metrics
```

| Deny-Typ | Beispiel-Reason |
|----------|-----------------|
| Loop | `max_tool_calls` |
| Budget | `max_usd_day`, `max_usd_request` |
| Scope | `scope:provider`, `scope:intent` |
| Freeze | `admission_frozen` |
| Circuit | provider OPEN / AUTH_DEAD |
| High-risk | provider disabled / not explicitly enabled |

Block-UX: `blocked.message` mit `🛑 REQUEST BLOCKED` (auch im Dashboard-Modal).

Code-SSoT: `src/tollgate/gateway/admit.py`, `agent_guard.py`, `limits.py`.

---

## 21. Tagesablauf / Praxisrezepte

### Morgens (Operator)

```bash
tollgate status
tollgate report --format md
tollgate audit --event admit_deny --limit 50
# Dashboard Overview: ATTENTION? Spend? Recommendations?
```

### Neuen Agent absichern (5 Minuten)

```bash
tollgate consumer-budget coding-agent \
  --max-usd-day 10 --max-usd-request 0.75 \
  --max-tool-calls 15 --max-requests-minute 40 \
  --allow-provider opencode_zen --allow-provider deepseek \
  --allow-intent free_llm --allow-op chat

# OpenAI-SDK auf Lane zeigen
export OPENAI_BASE_URL=http://127.0.0.1:8787/v1
export OPENAI_API_KEY=coding-agent
```

Oder: Dashboard → **Setup** / Agents → Edit protection.

### Incident (Runaway)

```bash
tollgate freeze --reason "runaway coding-agent"
# Agent stoppen / Policy fixen
tollgate audit --event admit_deny --limit 100
tollgate consumer-budget coding-agent --max-tool-calls 5 --max-usd-hour 0.5
tollgate unfreeze
```

### Wöchentlicher Prove

```bash
tollgate chaos test opencode_zen --requests 12
tollgate certificate --application "Prod Agents"
tollgate snapshot export -o "desk-$(date +%F).tgz"
```

### n8n absichern

```bash
tollgate consumer-add n8n          # Auth
tollgate consumer-budget n8n \
  --max-usd-day 0.5 --max-tool-calls 10 \
  --allow-intent free_llm --allow-op chat
# n8n OpenAI node: base URL → Tollgate, API key = id:secret
```

### USB / neuer Rechner

```bash
tollgate snapshot export -o desk.tgz
# auf Ziel: TOLLGATE_HOME setzen, import, Key.txt manuell
tollgate snapshot import desk.tgz
tollgate doctor
```

---

## 22. Glossar

| Begriff | Bedeutung |
|---------|-----------|
| **Consumer / Lane** | Logische Agent-Identität + Budget-Envelope |
| **Envelope** | Caps pro Consumer (`consumer_envelopes`) |
| **Admit** | Pre-Call-Entscheidung: allow/deny |
| **Fail-closed** | Bei Ledger/Config-Fehler lieber deny als freigeben |
| **Circuit** | Breaker-State pro Provider (OPEN/HALF/CLOSED) |
| **Freeze** | Globaler Kill-Switch für billable Traffic |
| **Chaos** | Simulierter Provider-Ausfall + Failover-Messung |
| **Certificate** | Scorecard Protect·Route·Prove |
| **Distill** | Provider-Wahrheit als JSON (`src/tollgate/distill/`) |
| **Control Room** | Dashboard unter `/dashboard` |
| **Open Mode** | Keine hashed Secrets — nur Labels |
| **Auth Mode** | `id:secret` Pflicht |
| **Scope** | allow/block Provider, Intent, Op |
| **tool_calls_est** | Client-seitige Schätzung der Tool-Loop-Tiefe |
| **Ledger** | `keys_usage.json` Tageszähler |
| **Audit** | Append-only Ops-Events (`audit.jsonl`) |

---

## 23. FAQ (Kurz)

**Brauche ich API-Keys für die Demo?**  
Nein. Protect (Tool-Loop-Block) braucht keine Keys. Echte Chats und voller Chaos-Pfad schon.

**Was ist der Unterschied zu LiteLLM?**  
LiteLLM verbindet Modelle. Tollgate **stoppt** Agents vor dem Schaden und **beweist** Failover.

**Warum wird mein Call geblockt?**  
`tollgate audit --event admit_deny`, Dashboard Audit, oder Response-Feld `blocked` / `error.tollgate`. Häufig: Envelope, Freeze, Scope, fehlende `tool_calls_est`-Logik auf Client-Seite falsch konfiguriert.

**Kann ich unbegrenzte Budgets?**  
Pro Dimension `0` setzen — andere Caps greifen weiter. Globaler Cost Guard kann trotzdem greifen.

**Multi-Worker?**  
Ja, wenn alle Worker dieselbe `TOLLGATE_HOME` teilen. Response-Cache ist process-lokal. Details: [STABILITY.md](STABILITY.md).

**Wo ist die „Wahrheit“ der Provider-APIs?**  
`src/tollgate/distill/*.json` — nicht in random Python-Strings erfinden.

Vollständige FAQ: **[FAQ.md](FAQ.md)** · CLI: `tollgate help faq`
