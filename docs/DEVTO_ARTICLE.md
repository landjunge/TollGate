# Ready to paste: Dev.to / Hashnode / Medium

**Title:** Protect · Route · Prove: a safety layer for AI agents (not another LLM gateway)

**Tags:** ai, agents, python, opensource, devops

**Canonical URL (set on Dev.to):** https://landjunge.github.io/TollGate/blog/launch.html

---

Most “agent infrastructure” posts are about connecting more models.

This one is about **keeping agents in line**.

## The gap

You can wire OpenAI, Anthropic, and local models in an afternoon.
What you cannot wing:

- runaway **tool loops** that burn tokens and time
- a single dead provider that freezes your desk
- “we think failover works” with **no drill**

## Two open tools that fit together

### 1) Gnom-Hub — the desk

Local multi-agent control hub.

- Brainstorm freely in chat
- Workers that spend money or touch files start only when you press **Execute**
- No Docker · visible agent cards · safe computer-use (dry-run until God-Mode)

Site: https://landjunge.github.io/gnom-hub-v1/  
Repo: https://github.com/landjunge/gnom-hub-v1

### 2) Tollgate — the gate

Safety layer between agents and the internet: **Protect · Route · Prove**.

| Mode | What it does |
|------|----------------|
| **Protect** | Budgets, tool-loop hard deny, freeze, scopes |
| **Route** | Health-aware failover + circuit breakers |
| **Prove** | Chaos/DR tests + reliability certificate scorecard |

OpenAI drop-in `base_url`, Anthropic, MCP, n8n.

Site: https://landjunge.github.io/TollGate/  
Repo: https://github.com/landjunge/TollGate

## Not LiteLLM

LiteLLM (and friends) are great at **connecting** models.

Tollgate is a **control plane**: hard denies *before* the call, freeze, audit, and a chaos scorecard you can show someone who does not care about your demo.

## 10-minute cold path (Protect needs no keys)

```bash
git clone https://github.com/landjunge/TollGate.git tollgate && cd tollgate
python3 -m venv .venv && .venv/bin/pip install -e .
./scripts/ten-minute.sh
# → blocked tool-loop + certificate
# Dashboard: http://127.0.0.1:8787/dashboard
```

## Production checklist

Long form: https://landjunge.github.io/TollGate/blog/checklist.html

## Feedback we want

If the cold path is confusing in the first 10 minutes — **that is the bug**.
Open a discussion or issue. Resilience scores from real runs are gold.

---

*By landjunge · MIT · local-first*
