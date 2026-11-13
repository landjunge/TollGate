# n8n + Tollgate

n8n holds **no** DeepSeek/Brave/Google secrets — only a consumer id + secret when auth is enabled.

**Product:** https://github.com/landjunge/TollGate

## Run Tollgate

```bash
# desk or USB
./scripts/run.sh
# → http://127.0.0.1:8787/docs
```

Portable stick: see [PORTABLE.md](PORTABLE.md).

### Optional auth (recommended if n8n is not only-localhost)

```bash
tollgate consumer-add n8n
# → secret printed once
# Header becomes: X-Consumer-Key: n8n:<secret>
```

Without consumers.json, open mode accepts any `X-Consumer-Key` / Bearer label (desk).

### Cap n8n spend independently of Gnom

```bash
tollgate consumer-budget n8n \
  --max-usd-day 0.5 --max-calls-day 200 \
  --max-tool-calls 15 --max-requests-minute 30
curl -s http://127.0.0.1:8787/v1/budget -H 'X-Consumer-Key: n8n'
```

### Tool-loop protection from n8n

| Path | How to send loop depth |
|------|------------------------|
| **Community node Chat/Invoke** | Field `tool_calls_est` (v0.2+) |
| **OpenAI node** | Often no custom fields — use HTTP Request node with body `tool_calls_est`, or header `X-Tollgate-Tool-Calls-Est` |
| **Auto** | If the agent keeps tool messages in history, Tollgate counts them on `/v1/chat/completions` |

Without `tool_calls_est` (or tool history), `max_tool_calls` will not fire on simple single-turn OpenAI nodes.

See [COST_LIMITS.md](COST_LIMITS.md) · [OPENAI.md](OPENAI.md).

## A) Community node (recommended)

Package in-repo: [`n8n-nodes-tollgate/`](../n8n-nodes-tollgate/) (**v0.2** — control, report, resilience, audit, `tool_calls_est`)

```bash
mkdir -p ~/.n8n/custom && cd ~/.n8n/custom
npm init -y
npm install /path/to/tollgate/n8n-nodes-tollgate
export N8N_CUSTOM_EXTENSIONS=~/.n8n/custom
# restart n8n → node "Tollgate" + credential "Tollgate API"
```

| Credential | Example |
|------------|---------|
| Base URL | `http://127.0.0.1:8787` (Docker n8n: `http://host.docker.internal:8787`) |
| Consumer Key | `n8n` or `n8n:<secret>` |

Operations: **Chat · Route · Budget · Invoke · Search · Health**.

## B) OpenAI credential (no custom node)

Many n8n AI nodes speak OpenAI format:

- Base URL: `http://127.0.0.1:8787/v1`
- API Key: `n8n` (open) or `n8n:<secret>`
- Model: `tollgate/free` or `tollgate/auto`

Siehe [OPENAI.md](OPENAI.md). Env template: [`configs/n8n-openai.env.example`](../configs/n8n-openai.env.example).

### Community node operations (v0.2)

| Op | Path | Notes |
|----|------|--------|
| Chat | `POST /v1/chat/completions` | + `tool_calls_est` for loop protection |
| Invoke | `POST /v1/invoke` | + `tool_calls_est` / `tokens_est` |
| Budget / Route / Search / Health | as before | |
| **Control** | `GET /v1/control` | burn + attention |
| **Report** | `GET /v1/report` | daily brief JSON |
| **Resilience** | `GET /v1/resilience` | score 0–100 |
| **Audit** | `GET /v1/audit` | who was denied |

On 402/429 denies, body may include `error.tollgate.protection` for IF nodes.

## C) Import HTTP workflows

| File | What |
|------|------|
| [`configs/n8n-openai-chat.workflow.json`](../configs/n8n-openai-chat.workflow.json) | Manual → chat completions smoke |
| [`configs/n8n-budget-gate.workflow.json`](../configs/n8n-budget-gate.workflow.json) | Budget → IF allowed → chat |
| [`configs/n8n-search.workflow.json`](../configs/n8n-search.workflow.json) | Brave search via invoke |
| [`configs/n8n-route-invoke.workflow.json`](../configs/n8n-route-invoke.workflow.json) | route free_llm → invoke chat |
| [`configs/n8n-webhook-alerts.workflow.json`](../configs/n8n-webhook-alerts.workflow.json) | Receive Protect/chaos webhooks |

Import in n8n: **Workflows → Import from File**.  
Docker: change `127.0.0.1` → `host.docker.internal`.

## Smoke without n8n UI

```bash
./scripts/n8n-smoke.sh
# KEY=n8n:secret BASE=http://127.0.0.1:8787 ./scripts/n8n-smoke.sh
```

Hits health, budget, route, chat (+ optional Brave search).

## Native HTTP reference

### Route free LLM

`POST /v1/route` · Header `X-Consumer-Key: n8n`

```json
{ "intent": "free_llm", "tokens_est": 2000, "prefer_free": true }
```

### Invoke

`POST /v1/invoke`

```json
{
  "provider": "opencode_zen",
  "op": "chat",
  "arguments": {
    "message": "={{ $json.prompt }}",
    "model": "deepseek-v4-flash-free",
    "max_tokens": 256
  },
  "agent_id": "n8n-workflow-42",
  "job_id": "={{ $execution.id }}",
  "request_class": "batch"
}
```

### Budget

`GET /v1/budget`

### Web search

```json
{
  "provider": "brave",
  "op": "search",
  "arguments": { "query": "…", "count": 5 },
  "request_class": "batch",
  "agent_id": "n8n-search"
}
```

## Anthropic path

If a node speaks Anthropic Messages: base `http://127.0.0.1:8787`, key as `x-api-key`.  
See [ANTHROPIC.md](ANTHROPIC.md).

## Later

- Publish `n8n-nodes-tollgate` to npm / community nodes UI
- Credential-only OpenAI preset export
