# Tollgate docs

**Repo:** https://github.com/landjunge/TollGate  
**Website:** https://landjunge.github.io/TollGate/ (static pages in `site/`)  
**Package path for provider truth:** `src/tollgate/distill/*.json`

| Doc | Topic |
|-----|--------|
| **[HILFE.md](HILFE.md)** | **Deutsche Hilfe & Handbuch** |
| **[USER_GUIDE.md](USER_GUIDE.md)** | **English user handbook** |
| **[FAQ.md](FAQ.md)** | **FAQ (DE/EN questions)** |
| [TEN_MINUTE.md](TEN_MINUTE.md) | **Cold customer — first 10 minutes** |
| [GETTING_STARTED.md](GETTING_STARTED.md) | Setup details |
| [DEMO.md](DEMO.md) | **Killer demo — agent loop + DR proof** |
| [MAP.md](MAP.md) | **Repo map — modules, HTTP, CLI, concepts** |
| [VISION.md](VISION.md) | Product lock, multi-consumer |
| [PRODUCT.md](PRODUCT.md) | Safety layer for AI agents · Protect · Route · Prove |
| [ARCHITECTURE.md](ARCHITECTURE.md) | 7 layers, circuits, taxonomy |
| [COST_LIMITS.md](COST_LIMITS.md) | Google off, budgets, `/v1/config` |
| [MCP.md](MCP.md) | stdio MCP + HTTP `/v1/*` |
| [N8N.md](N8N.md) | n8n as consumer |
| [KEYS_MODULE.md](KEYS_MODULE.md) | Module map (legacy; prefer MAP.md) |
| [PORTABLE.md](PORTABLE.md) | USB stick / no host paths |
| [OPENAI.md](OPENAI.md) | OpenAI drop-in base_url |
| [STABILITY.md](STABILITY.md) | Scale, multi-worker, schema version, deprecation |
| [OPERATIONS.md](OPERATIONS.md) | doctor, deploy, auto-maintenance boundary |

## CLI help

```bash
tollgate help
tollgate help protect
tollgate help env
tollgate help config
tollgate help faq
tollgate help troubleshoot
```

## Search the repo

```bash
tollgate search circuit breaker
tollgate search budget --kind concept
tollgate search --map
```

Also: root [`llms.txt`](../llms.txt) for agents.

## Rule (no more code thrash)

| Do | Don't |
|----|--------|
| Update distill JSON when APIs change | Invent endpoints inside random `.py` files |
| Add `ops[]` for new MCP functions | Copy-paste limits into 5 modules |
| Bump `distilled_at` | Rewrite router/service for every doc tweak |

## Providers

| ID | Distill JSON |
|----|----------------|
| deepseek | `src/tollgate/distill/deepseek.json` |
| worker | `src/tollgate/distill/worker.json` |
| brave | `src/tollgate/distill/brave.json` |
| elevenlabs | `src/tollgate/distill/elevenlabs.json` |
| openrouter | `src/tollgate/distill/openrouter.json` |
| nvidia | `src/tollgate/distill/nvidia.json` |
| minimax | `src/tollgate/distill/minimax.json` |
| opencode_zen | `src/tollgate/distill/opencode_zen.json` |
| google | `src/tollgate/distill/google.json` (high_risk, off by default) |
| telegram | `src/tollgate/distill/telegram.json` |

```python
from tollgate.distill.loader import load_distill, research_view, ops_for

spec = load_distill("brave")
for op in ops_for("brave"):
    print(op["name"], "→", op["maps_to"])
```
| [DESK.md](DESK.md) | Gnom + n8n runbook |
