# Tollgate FAQ

**Version:** 1.0.7 · Handbooks: [HILFE.md](HILFE.md) (DE) · [USER_GUIDE.md](USER_GUIDE.md) (EN)  
CLI: `tollgate help faq`

---

## Product

### What is Tollgate in one sentence?
The **safety layer** between AI agents and the internet: **Protect · Route · Prove**.

### Is Tollgate an LLM gateway / LiteLLM alternative?
No. Gateways multi-route models. Tollgate’s job is: **hard-stop runaway agents**, **survive provider failure**, and **prove** it with chaos + certificate.

### Killer use case?
*“My AI agent must never go out of control.”*  
Demo: tool-loop → `🛑 REQUEST BLOCKED`, then chaos failover → certificate.

### Do I need API keys?
- **Protect demo / 10-minute path:** no  
- **Real chat / full chaos proof:** yes (`User/Key.txt`)

---

## Install & data

### Python version?
**≥ 3.11**. Use a venv: `python3 -m venv .venv && .venv/bin/pip install -e .`

### Where is my data?
`$TOLLGATE_HOME/User/` (fallback `GNOM_WS`, else `~/.tollgate`).  
Check: `tollgate paths` · `tollgate doctor`

### What files matter?

| File | Role |
|------|------|
| `Key.txt` | Secrets (never commit) |
| `keys_app.json` | Policy / envelopes / freeze |
| `keys_usage.json` | Daily ledger |
| `consumers.json` | Auth secrets (hashed) |
| `circuits.json` | Breakers |
| `audit.jsonl` | Deny/ops trail |

### Port / bind?
Default `http://127.0.0.1:8787` (`HOST` / `PORT` env). Prefer loopback unless you use auth.

---

## Auth & consumers

### Open mode vs auth mode?
- **Open:** empty consumers → any `X-Consumer-Key` label (local desk OK)  
- **Auth:** `consumers.json` populated or `TOLLGATE_REQUIRE_AUTH=1` → `id:secret`

### How do I create a secret?
```bash
tollgate consumer-add n8n
tollgate consumer-add desk --admin   # can patch config
```
Secret is shown **once**.

### Admin vs normal consumer?
Admin can change policy (`POST /v1/config`), reset circuits, run chaos tests, etc.

---

## Protect

### How do I set budgets?
```bash
tollgate consumer-budget support-agent \
  --max-usd-day 2 --max-tool-calls 20 --max-requests-minute 50
tollgate consumer-budget --list
```
Or Control Room → Agents → Edit / Setup wizard.

### What is `max_tool_calls`?
Hard cap on **tool-loop depth this turn**. Depth sources (first wins):

1. Body `tool_calls_est`
2. Header `X-Tollgate-Tool-Calls-Est`
3. Auto-count of `role:tool` + `assistant.tool_calls` in message history
4. Weak: `len(tools)` schema list

Without any of these, a plain one-shot chat has est=0 and will **not** hit the loop cap. See [OPENAI.md](OPENAI.md).

### Chaos says NOT_RUN or failed?
**NOT_RUN** is normal until you run a test — Protect can still PASS.  
**Failed** often means only one provider in the `free_llm` chain or missing keys.

```bash
tollgate doctor
tollgate chaos test opencode_zen --requests 8
# needs ≥2 enabled providers with usable keys
```

### Why am I always blocked?
1. `tollgate freeze status`  
2. Envelope too tight (`consumer-budget --list`)  
3. Scope allow/block lists  
4. Global `cost_guard` or provider disabled  
5. Circuit OPEN  

```bash
tollgate audit --event admit_deny --limit 20
```

### What does `0` mean on a limit field?
Unlimited **on that dimension only**. Other dimensions and global guards still apply.

### Freeze vs envelope deny?
- **Envelope:** one lane / one reason (budget, loop, scope)  
- **Freeze:** all billable admission denied until unfreeze / env cleared  

```bash
tollgate freeze --reason "incident"
tollgate unfreeze
# or: TOLLGATE_FROZEN=1
```

### High-risk providers (Google)?
Off by default. Enable only with tight caps. See [COST_LIMITS.md](COST_LIMITS.md).

```bash
tollgate high-risk list
```

---

## Route & Prove

### How does routing choose a provider?
Intent (`free_llm`, `llm`, `search`, …) + enabled providers + health/circuits + budgets + scopes.  
`POST /v1/route` returns choice + optional `explain`.

### Chaos test failed?
Need **≥2** usable providers in the chain, valid keys, and server running.  
Try: `tollgate doctor` · `tollgate circuits list` · enable a second free provider.

### What is the certificate?
Scorecard for Protect · Route · Prove (PASS / FAIL / NOT_RUN) + resilience score.

```bash
tollgate certificate --application "My Agents"
```

---

## Clients

### OpenAI SDK?
```bash
export OPENAI_BASE_URL=http://127.0.0.1:8787/v1
export OPENAI_API_KEY=support-agent   # or id:secret
# model: tollgate/free | tollgate/auto | …
```
See [OPENAI.md](OPENAI.md). Pass `tool_calls_est` when you have tools.

### Anthropic / n8n / MCP?
[ANTHROPIC.md](ANTHROPIC.md) · [N8N.md](N8N.md) · [MCP.md](MCP.md)

### Does Tollgate store chat transcripts?
No. Ledger/audit are **ops counters and deny reasons**, redacted — not full conversations.

---

## Ops

### Daily report?
```bash
tollgate report --format md
tollgate status
```

### Alerts / webhooks?
```bash
export TOLLGATE_ALERT_WEBHOOK=https://…
# or cost_guard.alert_webhook_url
tollgate alert events
tollgate alert test
```

### Metrics 401?
Use consumer key, set `TOLLGATE_METRICS_TOKEN`, or (lab only) `TOLLGATE_METRICS_PUBLIC=1`.

### Migrate / USB?
```bash
tollgate snapshot export -o desk.tgz          # no Key.txt
tollgate snapshot import desk.tgz
```
[PORTABLE.md](PORTABLE.md)

### Multi-worker?
Share the same `TOLLGATE_HOME`. Circuit + ledger are on disk. In-process cache is not shared. [STABILITY.md](STABILITY.md)

### Config patch rejected (400)?
Schema/semantic validation failed — invalid merge is **not** written. Check body; try `TOLLGATE_STRICT_CONFIG=1` + `doctor`.

---

## WebUI

### Control Room empty or stale?
Hard refresh. Check key field (top right). Confirm server version: `GET /v1/health`.

### Can I do first setup without CLI?
Yes — **Setup** wizard creates first protected agent via `/v1/config`.

---

## Development / repo

### How do I find code without guessing?
```bash
tollgate search circuit breaker
tollgate search budget --kind concept
tollgate search --map
```
[MAP.md](MAP.md) · root `llms.txt`

### Where is provider API truth?
`src/tollgate/distill/*.json` — update distill when upstream APIs change.

### Help offline?
```bash
tollgate help
tollgate help protect
tollgate help env
docs/HILFE.md · docs/USER_GUIDE.md
```

---

## Still stuck?

1. `tollgate doctor`  
2. `tollgate paths`  
3. `tollgate status`  
4. `GET /v1/health`  
5. Open issue: https://github.com/landjunge/TollGate  

**Pay the toll — or don't call.**
