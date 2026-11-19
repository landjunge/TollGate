# Tollgate — User Guide

**Version:** 1.0.7 · **Repo:** https://github.com/landjunge/TollGate  

> **Tollgate is the safety layer between your AI agents and the internet.**  
> Not an API gateway. Not a multi-LLM catalog.

**Killer use case:** *“My AI agent must never go out of control.”*

| Quick links | |
|-------------|--|
| 10-minute cold start | [TEN_MINUTE.md](TEN_MINUTE.md) · `./scripts/ten-minute.sh` |
| Demo | [DEMO.md](DEMO.md) · `tollgate demo` |
| Control Room | http://127.0.0.1:8787/dashboard |
| CLI help | `tollgate help` · `tollgate help protect` · `tollgate help env` |
| FAQ | [FAQ.md](FAQ.md) |
| German handbook | [HILFE.md](HILFE.md) |

---

## Table of contents

1. What Tollgate is  
2. Install  
3. Data layout  
4. Consumers (agent lanes)  
5. Protect  
6. Route  
7. Prove  
8. Control Room WebUI  
9. Connect clients  
10. CLI reference  
11. HTTP API  
12. Ops extras  
13. Troubleshooting  
14. Security checklist  
15. Doc map  
16. Environment variables  
17. Config recipes  
18. Admission path  
19. Day-to-day recipes  
20. Glossary  

---

## 1. What Tollgate is

```text
Agent / n8n / MCP / OpenAI SDK
            │
            ▼
         TOLLGATE
   Protect · Route · Prove
            │
   ┌────────┼────────┐
   ▼        ▼        ▼
 OpenAI  Anthropic  Zen / DeepSeek / …
```

| Pillar | Job | User question |
|--------|-----|----------------|
| **Protect** | Budgets, tool-loop stops, scopes, freeze, audit | Will this agent run away? |
| **Route** | Health routing, failover, circuits | What if the primary provider dies? |
| **Prove** | Chaos tests, resilience score, certificate | Can I **show** it works? |

**Not:** agent framework · chat memory store · 100-provider SaaS catalog.

| | **Tollgate** | LiteLLM | Helicone |
|--|--------------|---------|----------|
| Core job | **Agent safety + DR proof** | Multi-provider proxy | Observability |
| Pre-admission hard deny | ✅ | optional | mostly post-hoc |
| Chaos / prove | ✅ first-class | DIY | — |

---

## 2. Install

**Requires Python ≥ 3.11.**

```bash
git clone https://github.com/landjunge/TollGate.git tollgate
cd tollgate
python3 -m venv .venv && .venv/bin/pip install -e .

export TOLLGATE_HOME=$HOME/.tollgate
mkdir -p "$TOLLGATE_HOME/User"
tollgate serve
# → http://127.0.0.1:8787
```

```bash
./scripts/desk-ready.sh      # doctor + server + smoke
./scripts/ten-minute.sh      # Protect → Prove → certificate
```

**Docker:**

```bash
docker compose up -d --build
docker compose exec tollgate tollgate certificate
```

**Protect demo needs no API keys.** Real chat needs keys in `User/Key.txt` (see `Key.txt.example`).

| Step | Expectation |
|------|-------------|
| **Protect** | `🛑 REQUEST BLOCKED` on tool-loop (no $) |
| **Prove** | Chaos/failover or clear next step |
| **Result** | Certificate + Control Room |

If the cold path is confusing: **stop shipping features** — fix the path.

---

## 3. Data layout

| Path under `$TOLLGATE_HOME/User/` | Role |
|----------------------------------|------|
| `Key.txt` | Secrets (never commit) |
| `keys_app.json` | Policy, envelopes, routing, freeze |
| `keys_usage.json` | Daily usage ledger |
| `consumers.json` | Hashed consumer secrets |
| `circuits.json` | Circuit breakers |
| `audit.jsonl` | Append-only audit |
| `chaos.json` | DR / chaos state |

```bash
tollgate doctor
tollgate paths
```

**Rule:** secrets live in Tollgate only — never in agent prompts or n8n env as raw provider keys.

---

## 4. Consumers (agent lanes)

Identity on every request:

```http
X-Consumer-Key: support-agent
# auth mode:
X-Consumer-Key: support-agent:secret
Authorization: Bearer support-agent:secret
```

| Mode | When | Key format |
|------|------|------------|
| **Open** | no consumers / local desk | any label |
| **Auth** | `consumers.json` or `TOLLGATE_REQUIRE_AUTH=1` | `id:secret` |

```bash
tollgate consumer-add n8n
tollgate consumer-add desk --admin   # may patch policy
# secret shown once
```

---

## 5. Protect

### Envelopes

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

| Field | Meaning |
|-------|---------|
| `max_usd_day` / `_request` / `_hour` | Money caps |
| `max_requests_minute` | RPM |
| `max_tool_calls` | Tool-loop depth this turn |
| `max_tokens_request` | Token estimate cap |
| `max_calls_day` / `max_tokens_day` | Daily counts |

`0` / omit = unlimited on that dimension.

**Protect-on-by-default:** new installs ship `_default` with safe caps (~$5 global day, 60 rpm, 25 tool calls, $0.50/request). Details: [COST_LIMITS.md](COST_LIMITS.md).

```bash
tollgate consumer-budget _default --max-usd-day 1
tollgate consumer-budget desk --max-usd-day 0     # escape hatch on one dim
tollgate consumer-budget support-agent --clear    # fall back to _default
```

### Scopes

```bash
tollgate consumer-budget support-agent \
  --allow-provider opencode_zen \
  --block-provider google \
  --allow-intent free_llm --allow-op chat

tollgate consumer-budget support-agent --clear-scopes
```

Empty allow-list = unrestricted on that axis. **Block lists always win.**

### Tool-loop Aha

```bash
curl -s http://127.0.0.1:8787/v1/invoke \
  -H 'Content-Type: application/json' \
  -H 'X-Consumer-Key: support-agent' \
  -d '{"provider":"opencode_zen","op":"chat","tool_calls_est":99,"arguments":{"message":"hi"}}'
```

Response includes `blocked.message` (`🛑 REQUEST BLOCKED`).  
Dashboard: **Test tool-loop block**.

> Clients must send `tool_calls_est` (or equivalent). Without it, loop depth cannot be hard-denied.

### Freeze

```bash
tollgate freeze --reason "incident"
tollgate unfreeze
# env: TOLLGATE_FROZEN=1  (or TOLLGATE_ADMISSION_FROZEN=1)
```

### Global cost guard

- `cost_guard.max_usd_day_global` (default 5.0)  
- High-risk providers (Google, …) **off** until explicitly enabled with caps  
- Soft warn ~80% budget → optional webhook  

```bash
tollgate high-risk list
tollgate high-risk add azure_openai
```

---

## 6. Route

```bash
curl -s http://127.0.0.1:8787/v1/route \
  -H 'Content-Type: application/json' \
  -H 'X-Consumer-Key: support-agent' \
  -d '{"intent":"free_llm","tokens_est":1000}'
```

```bash
tollgate circuits list
tollgate circuits reset deepseek
tollgate circuits reset --all
```

Config: `circuits.failure_threshold`, `cooldown_s`, `hard_cooldown_s`, jitter.

---

## 7. Prove

```bash
tollgate chaos test opencode_zen --requests 10
tollgate resilience
tollgate certificate --application "Customer Support Agent"
tollgate demo
tollgate demo --skip-chaos
```

Dashboard → **Prove** → Run test.

Chaos typically needs **≥2 providers** in the intent chain and valid keys for a full proof.

---

## 8. Control Room WebUI

http://127.0.0.1:8787/dashboard  

| Screen | Question |
|--------|----------|
| Overview | Safe? Broken? Expensive? What to do? |
| Agents | Protection, budgets, edit, loop test |
| Providers | Health, latency, cost |
| Prove | Chaos + certificate |
| Audit | Who was blocked and why |

Badge: **PROTECTED** · **ATTENTION** · **FROZEN**  
**Setup** wizard: name agent → set limits → save (first lane without CLI).  
Key field (top right): open-mode label or `id:secret` (stored in localStorage).

OpenAPI: http://127.0.0.1:8787/docs  

---

## 9. Connect clients

### OpenAI drop-in

```bash
export OPENAI_BASE_URL=http://127.0.0.1:8787/v1
export OPENAI_API_KEY=support-agent
# models: tollgate/free | tollgate/auto | provider ids
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
Success headers: `X-Tollgate-Provider`, … · Deny: `error.tollgate`.

See [OPENAI.md](OPENAI.md) · Anthropic: [ANTHROPIC.md](ANTHROPIC.md) · n8n: [N8N.md](N8N.md) · MCP: [MCP.md](MCP.md).

---

## 10. CLI reference

```text
tollgate help [topic]
  topics: start | protect | route | prove | ui | api | ops
          troubleshoot | commands | env | config | faq
```

| Command | Purpose |
|---------|---------|
| `serve` / `mcp` | HTTP (`HOST`/`PORT`) / MCP servers |
| `doctor` | Install/config diagnose |
| `status` / `health` / `paths` / `control` | State |
| `certificate` | Reliability scorecard |
| `demo` | Live Protect + Prove |
| `consumer-add` / `consumer-budget` | Lanes + envelopes + scopes |
| `chaos` / `resilience` | DR proof |
| `freeze` / `unfreeze` | Kill switch |
| `circuits` | List/reset breakers |
| `audit` / `report` | Trail + day brief |
| `alert` | Webhook catalog/test |
| `snapshot` | Export/import desk |
| `search` | Repo search |
| `high-risk` / `provider-add` / `suggest` | Provider ops |

### `consumer-budget` flags

```text
--list
--max-calls-day --max-tokens-day --max-usd-day
--max-usd-request --max-usd-hour --max-requests-minute
--max-tokens-request --max-tool-calls
--allow-provider / --block-provider
--allow-intent / --block-intent
--allow-op / --block-op
--clear-scopes | --clear
```

---

## 11. HTTP API (summary)

Base: `http://127.0.0.1:8787`

| Method | Path | Role |
|--------|------|------|
| GET | `/dashboard` | Control Room |
| GET | `/docs` | OpenAPI |
| GET | `/v1/health` · `/v1/control` · `/v1/status` | Health / pane / glance |
| GET | `/v1/certificate` · `/v1/resilience` | Prove signals |
| GET/POST | `/v1/chaos` · `/v1/chaos/test` | DR |
| GET | `/v1/audit` · `/v1/budget` | Audit / budget |
| GET/POST | `/v1/config` | Policy (admin when auth) |
| POST | `/v1/route` · `/v1/invoke` | Route / call |
| POST | `/v1/chat/completions` · `/v1/messages` | Drop-ins |
| GET | `/v1/models` | Model list |
| GET/POST | `/v1/freeze` · `/v1/circuits*` | Ops controls |
| GET | `/metrics` | Prometheus (may require auth) |

```bash
curl -s -X POST http://127.0.0.1:8787/v1/config \
  -H 'Content-Type: application/json' \
  -H 'X-Consumer-Key: desk' \
  -d '{"cost_guard":{"max_usd_day_global":3.0}}'
```

Invalid patches → **HTTP 400** (not written). Full schemas: `/docs`.

---

## 12. Ops extras

**Webhooks:** `TOLLGATE_ALERT_WEBHOOK` or `cost_guard.alert_webhook_url` · `tollgate alert test`  

**Snapshot:**

```bash
tollgate snapshot export -o desk.tgz              # no Key.txt
tollgate snapshot export -o full.tgz --include-secrets
tollgate snapshot import desk.tgz
```

**Portable USB:** [PORTABLE.md](PORTABLE.md)

---

## 13. Troubleshooting

| Issue | Check |
|-------|--------|
| Won’t start | `doctor` · port 8787 · Python 3.11+ |
| 401 | Auth mode needs `id:secret` |
| Always blocked | Envelope / freeze / scope |
| Chaos failed | ≥2 providers in chain · keys |
| Stale UI | Hard refresh · `/v1/health` version |
| Metrics 401 | Token / consumer / `TOLLGATE_METRICS_PUBLIC=1` |
| Wrong data dir | `tollgate paths` · `TOLLGATE_HOME` |
| Config 400 | Schema invalid |
| Multi-worker drift | shared `TOLLGATE_HOME` |

Desk log often: `/tmp/tollgate-desk.log`  
More: [FAQ.md](FAQ.md) · `tollgate help troubleshoot`

---

## 14. Security checklist

- Provider secrets only in vault (`Key.txt`)  
- Use auth mode off localhost  
- Don’t expose `/metrics` or config without auth  
- Ledger holds ops counters only — never chat transcripts  
- Use freeze during incidents  
- High-risk providers off by default  
- Prefer snapshot export **without** secrets  

---

## 15. Doc map

| Doc | Use when |
|-----|----------|
| [TEN_MINUTE.md](TEN_MINUTE.md) | First contact |
| [DEMO.md](DEMO.md) | Pitch / screen share |
| [FAQ.md](FAQ.md) | Common questions |
| [HILFE.md](HILFE.md) | German full help |
| [PRODUCT.md](PRODUCT.md) | Positioning |
| [COST_LIMITS.md](COST_LIMITS.md) | Envelope fields |
| [OPERATIONS.md](OPERATIONS.md) | Deploy / ops |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Layers |
| [MAP.md](MAP.md) | Code index |
| [STABILITY.md](STABILITY.md) | Multi-worker / schema |

```bash
tollgate search budget
tollgate search --map
```

---

## 16. Environment variables

| Variable | Purpose |
|----------|---------|
| `TOLLGATE_HOME` | Data root (`User/`) |
| `GNOM_WS` | Fallback data root |
| `TOLLGATE_CONFIG` / `GNOM_KEYS_CONFIG` | Absolute config path |
| `TOLLGATE_PORTABLE` | Portable path resolution |
| `TOLLGATE_REQUIRE_AUTH` | Force auth mode |
| `TOLLGATE_CONSUMERS` | Consumers file override |
| `TOLLGATE_FROZEN` / `TOLLGATE_ADMISSION_FROZEN` | Kill switch |
| `TOLLGATE_ALERT_WEBHOOK` | Alert URL |
| `TOLLGATE_METRICS_TOKEN` / `TOLLGATE_METRICS_PUBLIC` | Metrics auth |
| `TOLLGATE_STRICT_CONFIG` | Hard-fail invalid config |
| `TOLLGATE_URL` / `TOLLGATE_CONSUMER` | Client defaults |
| `HOST` / `PORT` | `serve` bind (default 127.0.0.1:8787) |

Provider keys: `User/Key.txt` or process env (`OPENCODE_API_KEY`, …).  
CLI: `tollgate help env`

---

## 17. Config recipes (`keys_app.json`)

Written under `$TOLLGATE_HOME/User/` from `DEFAULT_CONFIG` on first load.

```json
{
  "cost_guard": {
    "enabled": true,
    "max_usd_day_global": 3.0,
    "soft_warn_ratio": 0.8,
    "alert_webhook_url": "",
    "high_risk_providers": ["google", "gemini", "vertex"]
  },
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
  },
  "reliability": {
    "availability_target": 99.9,
    "max_failover_time_s": 5.0,
    "required_fallbacks": 2,
    "gradual_recovery_s": 60.0
  },
  "admission": {
    "frozen": false,
    "allow_system_when_frozen": true
  }
}
```

SSoT for defaults: `src/tollgate/app_config.py`. Field detail: [COST_LIMITS.md](COST_LIMITS.md).

---

## 18. Admission path

```text
Request
  → Auth (open vs id:secret)
  → Freeze?  → DENY
  → Consumer envelope / scopes
  → Agent guard (tool_calls, rpm, $/request, …)
  → Cost guard global / provider caps
  → Circuit open? → failover / DENY
  → Route (intent, prefer_free, health)
  → Invoke
  → Ledger + Audit + Metrics
```

Fail-closed where it matters (ledger/config errors prefer deny over open).  
Code: `gateway/admit.py`, `agent_guard.py`, `limits.py`.

---

## 19. Day-to-day recipes

**Morning ops**

```bash
tollgate status
tollgate report --format md
tollgate audit --event admit_deny --limit 50
```

**New agent in 5 minutes**

```bash
tollgate consumer-budget coding-agent \
  --max-usd-day 10 --max-tool-calls 15 \
  --allow-provider opencode_zen --allow-intent free_llm --allow-op chat
export OPENAI_BASE_URL=http://127.0.0.1:8787/v1
export OPENAI_API_KEY=coding-agent
```

**Incident**

```bash
tollgate freeze --reason "runaway"
# fix policy
tollgate consumer-budget coding-agent --max-tool-calls 5
tollgate unfreeze
```

**Weekly prove**

```bash
tollgate chaos test opencode_zen --requests 12
tollgate certificate --application "Prod Agents"
tollgate snapshot export -o "desk-$(date +%F).tgz"
```

**n8n lane**

```bash
tollgate consumer-add n8n
tollgate consumer-budget n8n --max-usd-day 0.5 --max-tool-calls 10
# OpenAI node base_url → Tollgate; key = id:secret
```

---

## 20. Glossary

| Term | Meaning |
|------|---------|
| **Consumer / lane** | Logical agent identity + envelope |
| **Envelope** | Per-consumer caps |
| **Admit** | Pre-call allow/deny |
| **Fail-closed** | Prefer deny on error |
| **Circuit** | Breaker state per provider |
| **Freeze** | Global billable kill switch |
| **Chaos** | Simulated outage + failover measure |
| **Certificate** | Protect·Route·Prove scorecard |
| **Distill** | Provider truth JSON |
| **Control Room** | `/dashboard` |
| **tool_calls_est** | Client estimate of loop depth |
| **Ledger / audit** | Usage counters / deny trail (not chat logs) |

---

**Pay the toll — or don't call.** · MIT · https://github.com/landjunge/TollGate  
CLI: `tollgate help` · FAQ: [FAQ.md](FAQ.md) · DE: [HILFE.md](HILFE.md)
