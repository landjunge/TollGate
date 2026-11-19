# TollGate: setup and developer reference

Setup, commands and language options moved from the README on 31 October 2026. This describes source version 1.0.12, not a new packaged release. [Workflow control](WORKFLOW-CONTROL.md) and [process stops](WORKFLOW-PROCESS-STOP.md) define adapter and cost limits. Use requires permission under [LICENSE](../LICENSE). Return to [English](../README.md) or [Deutsch](../README.de.md).

## 10 minutes (cold start)

**Primary path: native Python — no Docker.** Protect demo needs no provider keys.

```bash
git clone https://github.com/landjunge/TollGate.git tollgate && cd tollgate
python3 -m venv .venv && .venv/bin/pip install -e .
./scripts/ten-minute.sh
# 60-second Protect story (optional, server on :8787):
./scripts/demo-agent-safety.sh
```

**USB stick / portable desk** (venv + data on the volume):

```bash
./scripts/portable-setup.sh
./scripts/run.sh
# details: docs/PORTABLE.md
```

You should experience:

| Step | What happens |
|------|----------------|
| **Protect** | Agent tool-loop → `🛑 REQUEST BLOCKED` (no $ required) |
| **Prove** | Chaos / failover simulation → survived or clear next step |
| **Result** | `tollgate certificate` scorecard + [dashboard](http://127.0.0.1:8787/dashboard) |

**Start here (3 docs):**  
[Quickstart](../docs/QUICKSTART.md) · [Portable / USB](../docs/PORTABLE.md) · [How it works](../docs/HOW_IT_WORKS.md) · [Production checklist](../docs/PRODUCTION_CHECKLIST.md)

**More:** [SECURITY.md](../docs/SECURITY.md) · [OPENAI.md](../docs/OPENAI.md) · [HILFE.md](../docs/HILFE.md) (DE) · [FAQ.md](../docs/FAQ.md) · `tollgate help` · `tollgate doctor`

If that path is confusing, **stop shipping features** — fix the path.

---

## Who it’s for

| | |
|--|--|
| Teams running agents in production | cost · loops · outages · audit · freeze |
| Agent frameworks (LangGraph, CrewAI, …) | sit in front of tools + LLMs |
| n8n / automation | stop workflow agent-loops at the gate |

**Wedge:** LiteLLM connects models. Helicone shows traffic. **TollGate keeps agents in line.**

---

## Product (short)

| Pillar | Job |
|--------|-----|
| **Protect** | Budgets, tool-loop hard stops, scopes, freeze, audit |
| **Route** | Health-aware failover, circuits |
| **Prove** | Chaos/DR tests, resilience score, certificate scorecard |

Deep dive: [docs/PRODUCT.md](../docs/PRODUCT.md) · Architecture: [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md)

---

## Everyday commands (after the 10 minutes)

```bash
tollgate status
tollgate certificate --application "Customer Support Agent"
tollgate consumer-budget support-agent --max-usd-day 2 --max-tool-calls 20
tollgate chaos test opencode_zen --requests 10
tollgate freeze --reason "panic"    # blocks new controlled calls; not process termination
tollgate report                     # day brief
```

Point an agent / OpenAI SDK:

```bash
export OPENAI_BASE_URL=http://127.0.0.1:8787/v1
export OPENAI_API_KEY=support-agent   # open mode label, or id:secret
```

## Language / Sprache

Tollgate speaks English and German. English stays the default, so existing
scripts that read CLI output keep working.

| Way | Example |
|---|---|
| Once | `tollgate --lang de help` |
| Always | `export TOLLGATE_LANG=de` |
| Automatic | from `LC_ALL`, `LC_MESSAGES` or `LANG` |

`LANG=C` and `LANG=POSIX` mean "no preference" and are skipped, so a server
shell never lands on a language nobody chose.

The section words argparse prints itself (`usage:`, `options:`) come from
Python and stay English.

The Control Room at `/dashboard` follows the same choice: `?lang=de` picks a
language and is remembered in a cookie for a year, otherwise the browser
decides. The switch sits in the header and inside the setup wizard, so it is
reachable even on a first visit.

### Plain or expert wording / Klartext oder Fachsprache

Independent of English/German there are two levels of wording. **Plain is the
default, expert is opt-in** — never the other way round. Whoever knows the
terms switches them on; whoever does not is not run over by them.

| Way | Example |
|---|---|
| Once | `tollgate --mode expert control` |
| Always | `export TOLLGATE_MODE=expert` |
| Control Room | switch next to DE/EN, remembered in a cookie for a year |

| Plain (default) | Expert |
|---|---|
| Leitstand · Nachweis · Protokoll · Anbieter | Control Room · Prove · Audit · Provider |
| "Start Tollgate so agents can reach it" | "Run HTTP server (uvicorn)" |
| Response time · Safety switch · State | Latency · Circuit · Health |

The level is **not** guessed from the browser or the environment: plain
applies to everyone until someone says otherwise. Both switches carry the
other one's choice in their links, so picking EN does not throw the wording
level away.

Not yet in expert wording: the twelve handbook topics behind
`tollgate help <topic>`. The switch is wired (`<topic>#expert`), no topic has
a second version yet, so plain stays.

Not yet translated: text that arrives from the API (`/v1/control` headline and
recommendations). Those would need the API to carry codes instead of English
sentences — a change to the JSON contract, tracked separately.

---

## Docs index

| Doc | When |
|-----|------|
| [HILFE.md](../docs/HILFE.md) | **Hilfe (Deutsch)** |
| [USER_GUIDE.md](../docs/USER_GUIDE.md) | **User guide (English)** |
| [FAQ.md](../docs/FAQ.md) | **FAQ** |
| [TEN_MINUTE.md](../docs/TEN_MINUTE.md) | First 10 minutes |
| [DEMO.md](../docs/DEMO.md) | Pitch / screen share |
| [GETTING_STARTED.md](../docs/GETTING_STARTED.md) | Setup details |
| [MAP.md](../docs/MAP.md) · `tollgate search` | Find code |
| [N8N.md](../docs/N8N.md) · [OPENAI.md](../docs/OPENAI.md) | Integrations |
| [CHANGELOG.md](../CHANGELOG.md) | Releases · **v1.0.0+** |

**License:** All Rights Reserved · **Python:** ≥ 3.11 · **Repo:** [landjunge/TollGate](https://github.com/landjunge/TollGate)

### Owned CLI stop-only adapter / Auftragseigener CLI-Stopp

An optional trusted process adapter can share the durable workflow stop barrier;
CLI cost remains unknown, without a hard dollar cap or invented zero-cost quote.
Optionale betreibergebundene Prozessadapter teilen die dauerhafte Auftragssperre;
Kosten bleiben unbekannt. [DE/EN contract](../docs/WORKFLOW-PROCESS-STOP.md).
