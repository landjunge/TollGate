# Tollgate — Vision (locked)

**Product / repo:** **[landjunge/TollGate](https://github.com/landjunge/TollGate)**  
**Status:** agreed 2026-08-11 · **name locked** · control-plane direction locked  
**Killer use case:** *“My AI agent must never go out of control.”*  
**One-liner:** **Tollgate is the safety layer between your AI agents and the internet.**  
**Product:** **Protects AI agents in production** — Control cost · Survive outages · Prove it.  
**Architecture label:** AI Reliability & Control Plane — Protect · Route · Prove.

**Tagline:** *Pay the toll — or don't call.*  
**Promise:** *Prove your AI agent survives a provider outage — and never runs away on cost or tool loops.*  
**Vs field:** *LiteLLM connects models · Helicone shows traffic · Tollgate keeps agents in line (and proves DR).*

See **[PRODUCT.md](PRODUCT.md)** · **[DEMO.md](DEMO.md)** (30-second + live script).

---

## Destination

```
Gnom-Hub ──┐
n8n ───────┼──►  tollgate (control plane)  ──► Provider APIs
Cursor/MCP ┤         admit · budget · health · explain
Agents ────┘         HTTP + MCP + OpenAI/Anthropic drop-ins
```

| Property | Target |
|----------|--------|
| Repo | `tollgate` |
| Role | **AI traffic control plane** (not “just a proxy”) |
| Pillars | Reliability · Cost · Control |
| Consumers | Gnom, n8n, Cursor/MCP, agents, internal tools |
| Truth | `distill/*.json` + day ledger + circuits (ops memory only) |
| Gnom role | First-class **client**, thin integration |

---

## Why

- Many tools × many keys = bill shock and no single admission point  
- Agents and n8n loops fail open on cost without a gate  
- Provider outages without health-aware failover burn time and money  
- Orgs need **explainable** spend and routing, not black-box proxying  

---

## Public contract (stable)

| Surface | Purpose |
|---------|---------|
| `POST /v1/route` | intent → provider/model + fallbacks + **explain** |
| `POST /v1/invoke` | admit + call + meter |
| `GET  /v1/budget` | remaining calls/tokens/usd + consumer envelope |
| `GET  /v1/control` | **health · consumer burn · headline** (product pane) |
| `GET  /v1/audit` | **who was denied and why** (append-only trail query) |
| `GET  /v1/report` | **daily operator brief** (json \| markdown) |
| `GET  /v1/health` | liveness + circuits |
| `GET  /v1/providers` | inventory grades (masked) |
| `POST /v1/chat/completions` | OpenAI drop-in |
| `POST /v1/messages` | Anthropic drop-in |
| `GET  /dashboard` | human-readable control plane |
| MCP stdio | same ops for Cursor / Claude Desktop |

---

## Gateway memory (ops only)

| Store | Role |
|-------|------|
| Ledger | tokens, $, calls, latency averages — day / provider / **consumer** |
| Circuits | open/half-open cooldowns |
| Health scores | success rate + circuit + spend → ranking input |
| Response cache | free/batch probes — **not** agent memory |
| Audit log | append-only deny/spend events |

---

## Roadmap status

| Phase | Outcome | Status |
|-------|---------|--------|
| Foundation | Admit, budgets, circuits, distill, own repo | **done** |
| Multi-consumer | Auth, envelopes, n8n node, OpenAI/Anthropic | **done** |
| Failover | Execute-time hop on retriable errors | **done** |
| Control plane v0.2 | Provider health · consumer burn · explain · mini UI | **done** |
| Agent protection | request/hour/minute hard stops | **done (v0.2.1)** |
| Health-aware route | Prefer healthy/cheap automatically | **done (v0.2.2)** |
| Prove (chaos + score) | DR tests + Resilience Score | **done (v0.2.4–0.2.6)** |
| Safe defaults | Protect-on `_default`, metrics auth, circuit jitter | **done (v0.3.0)** |
| Audit query | who/why denied — CLI · HTTP · dashboard · MCP | **done (v0.3.1)** |
| Operator report | daily Protect·Route·Prove brief + deny meta headers | **done (v0.3.2)** |
| Snapshot + n8n v0.2 | portable export/import · tool_calls on chat · control ops | **done (v0.3.3)** |
| Structured alerts | webhook schema v1 · chaos events · alert CLI | **done (v0.3.4)** |
| Consumer scopes | allow/block providers · intents · ops per lane | **done (v0.3.5)** |
| Freeze + circuits | global kill switch · circuit reset CLI/API | **done (v0.3.6)** |
| Desk status | compact status + success response headers | **done (v0.3.7)** |
| Review harden | freeze fail-closed · circuit mtime reload · ledger E2E | **done (v0.3.8)** |
| **v1.0.0** | Stable Core release tag | **done** |
| Organization layer | Teams, SSO/RBAC, fleet ops (not a Core paywall) | later — see PRODUCT_TIERS.md |

---

## Non-goals (for now)

- Replacing LiteLLM/Portkey as global SaaS catalog  
- Semantic “best model” before admission is correct  
- Mixing agent project memory into Tollgate  

---

## Success

1. One control plane for agents **and** n8n without secrets in either.  
2. Runaway loop → hard deny + audit, not invoice.  
3. Operator can answer: *which agent burns $? which provider is sick? why this model?*  
4. Product feels like **governance**, not plumbing.
