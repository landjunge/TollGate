# Tollgate — Masterpiece Architecture

**Product:** [landjunge/TollGate](https://github.com/landjunge/TollGate)  
**Status:** living design (2026-08-11)  
**Team research:** industry gateways (LiteLLM, Portkey, OpenRouter, CF AI Gateway) + failure-mode analysis + current module audit.

## North star

A runaway agent must hit a **hard deny in &lt;1s with an audit row**, never a surprise invoice.  
Brave / ElevenLabs / DeepSeek / Zen share **one** admission + metering plane.  
Google stays **off** until an admin unlocks a $ envelope.  
**Metaphor:** every call pays the toll (budget) or the gate stays shut.

## What exists in industry (steal ideas, not the whole stack)

| System | Steal | Avoid for local desk |
|--------|--------|----------------------|
| **LiteLLM** | Virtual keys, tag budgets, cooldowns, dual metering | Full proxy + Postgres as desk core |
| **Portkey** | Circuit breakers, policy configs, failover | Cloud lock-in as control plane |
| **OpenRouter** | Multi-model catalog, sticky routing, free RPM traps awareness | Trusting it alone for local budgets |
| **Cloudflare AI Gateway** | Edge rate limits, cache | Wrong default for local multi-agent |
| **Semantic routers** (Martian/Not Diamond) | Optional quality routing later | Before budget/health — never |

## Why systems suffer when routers are bad

1. **Bill shock** — post-hoc logs, no pre-admission; agent loops × long context × Google.  
2. **Silent downgrade** — free fallback without surfacing model in response.  
3. **Thundering herd** — all agents failover together; no jitter/shared cooldown.  
4. **401 loops** — rotating keys on auth failure instead of marking dead.  
5. **Free-tier RPM traps** — OpenRouter free 50/day-class caps; 429 without failover.  
6. **Mixed auth** — Bearer-only breaks EL / Brave / Anthropic / Google.  
7. **No attribution** — who spent $ at 3am?  
8. **EDGE_BLOCK vs 429** — Cloudflare bot block treated as rate limit → wrong policy.

## 7 layers (ownership)

```
L1  Secret Vault        Key.txt / env handles — never in agent memory
L2  Provider Specs      distill/*.json (auth, URLs, errors, ops) — data not code
L3  Virtual Identity    consumer scopes (allow/block provider·intent·op) + request class
L4  Admission Control   soft/hard budget, dual-window, cost velocity, cost_guard
L5  Router Policy       intent chain, sticky, failover, health scores
L6  Transport Adapter   headers from L2; one HTTP path; error taxonomy
L7  Meter + Audit       token + $ dual meter; append-only events
```

**Code implements interpreters. Specs implement truth.**

## Request classes

| Class | Use | Budget rule |
|-------|-----|-------------|
| `interactive` | User chat | Priority; limited paid fallback |
| `batch` | Background jobs | Cheap models; bulk of daily $ |
| `free` | Free-tier only | Never spill to paid without flag |
| `system` | Probes / auto_update | Tiny fixed; billable=false |

## Error taxonomy (required)

| Code | Next action |
|------|-------------|
| `AUTH_DEAD` | Mark key dead; no rotate loop |
| `RATE_LIMIT` | Cooldown + optional failover |
| `PROVIDER_DOWN` | Failover / circuit open |
| `EDGE_BLOCK` | No key rotate; fix UA/IP |
| `EMPTY_COMPLETION` | Retry once or degrade |
| `POLICY_DENY` | Hard stop; show budget |
| `BUDGET_HARD` | Fail closed |
| `BUDGET_SOFT` | Degrade to free/cheaper |

## Circuit breaker

- Per **`(provider, model?, key_ref?)`** — never whole Google for one model 429.  
- States: CLOSED → OPEN → HALF_OPEN.  
- Trip: N failures / high 429 rate / AUTH_DEAD.  
- Cooldown + jitter; single canary on half-open.

## Budget envelopes

- **Soft:** warn, prefer free, drop batch.  
- **Hard:** deny before HTTP.  
- Dual meter: **tokens** and **USD** (estimate; reconcile when usage present).  
- Cost-velocity: burn ≫ daily/$ remaining → early trip.  
- Google: `enabled=false` + high_risk + `max_usd_day` + global guard.

## Scale & multi-worker

See [STABILITY.md](STABILITY.md). Summary:

- Ledger + circuits: **disk + file lock** (safe across uvicorn workers on one `TOLLGATE_HOME`)
- Response cache: process-local only
- Multi-host LB: **not** supported for global $ caps (needs Redis/Postgres later)

## HTTP surface & desk security (known gaps)

| Endpoint | Status |
|----------|--------|
| `/v1/providers` | Inventory grades; key material **masked** |
| `/v1/config` GET/POST | Policy file only (`keys_app.json`) — **not** `Key.txt`. No admin auth yet. Bind **127.0.0.1** until Phase 3 consumer scopes |
| `/v1/invoke` | Spend path; needs consumer secrets before public multi-tenant |
| MCP stdio | Local process; inherits user secrets from env / `TOLLGATE_HOME` |

Documented so agents do not assume “own repo ⇒ safe on 0.0.0.0”.

## Anti-patterns (banned)

1. Post-call-only budgeting  
2. Shared god key without attribution  
3. Retry 401/403 / key-rotate on AUTH  
4. Provider-wide cooldown for one model  
5. Silent free fallback  
6. Free→paid spill without policy  
7. Bearer-only for all providers  
8. Hardcoded provider docs in if-trees  
9. Failover without jitter  
10. Google enabled by key presence alone  
11. EDGE_BLOCK treated as RATE_LIMIT  
12. Semantic router before admission  

## Gateway memory / cache (L7+)

**Cache yes (narrow). Memory no.** Enforced in code (`ops_boundary`, `response_cache`).

Operational only — shared across Gnom, n8n, MCP clients:

- **Append-only ledger** (provider, tokens, usd, consumer id, op, timestamp) — **no `content`/`message`/`prompt`**
- **Aggregates** (day/consumer/provider)  
- **Circuit + dead-key state**  
- **Response cache** (`response_cache`): TTL for `search` / `status` / `quota` / `models` only; request_class `free|batch|system`; key includes **consumer**; never high-risk; never interactive by default  
- **Health / inventory** short TTL (already via `use_cache`)

Do **not** store user wishes, chat transcripts, or project files here.  
Agent memory stays on the **consumer** (Gnom/n8n/Cursor). Tollgate must not become a second source of truth for conversation state.

Code guards:

| Module | Role |
|--------|------|
| `ops_boundary.sanitize_meta` | strips forbidden fields from ledger meta |
| `ops_boundary.assert_no_memory_fields` | test/CI invariant on usage day JSON |
| `response_cache` | policy + consumer-scoped keys |

## Implementation order

1. ~~Distill SSoT~~ · ~~cost_guard Google~~ · MCP · grades  
2. ~~Admission + taxonomy + circuit~~ (foundation)  
3. Seal all spend paths through gateway  
4. **SQLite gateway memory** (ledger + circuits + optional cache) + agent_id/consumer  
5. ~~Real execute failover for LLM chat~~  
6. ~~Own repo + CI~~ · ~~consumer API keys (hash + open mode)~~ · ~~USB portable~~  
7. ~~OpenAI-compatible `/v1/chat/completions` + `/v1/models`~~ (SSE synthetic stream)  
8. ~~Real token streaming~~ · ~~per-consumer budget envelopes~~  
9. ~~Prometheus `/metrics`~~ · ~~webhook alerts~~ · ~~Anthropic messages~~ · ~~n8n node pack~~  


## Success metrics

| Metric | Target |
|--------|--------|
| Runaway loop | Hard deny &lt;1s + audit event |
| Dashboard vs reality | Same path meters agent + tools |
| Doc change | Distill JSON only |
| Google accident | Impossible without explicit enable + $ cap |
