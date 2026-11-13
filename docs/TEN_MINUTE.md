# 10-minute test (cold customer)

**You don’t know Tollgate.** You only get this page.

> **Tollgate protects your AI agents from cost explosions and provider outages.**

**Not:** install every integration. **Not:** read ARCHITECTURE.  
**Yes:** feel Protect → Route → Prove in one sitting.

---

## Promise

Within **10 minutes** you should be able to answer **yes** to:

| # | Question | Pass if |
|---|----------|---------|
| 1 | Do I know what this is for? | “Safety layer for AI agents” |
| 2 | Can I protect one agent? | Tool-loop **blocked** without spending $ |
| 3 | Can I prove failover? | Chaos test (or clear “need 2 providers”) |
| 4 | Do I see a result? | Resilience / certificate-style scorecard |

If any answer is **no**, the friction is a product bug — fix the path, don’t add features.

---

## Path A — Local (recommended for the demo)

```bash
git clone https://github.com/landjunge/TollGate.git tollgate
cd tollgate
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"

# One command: Protect Aha + Prove Aha + scorecard
./scripts/ten-minute.sh
```

Or step by step:

```bash
./scripts/desk-ready.sh          # server + doctor
./scripts/demo-agent-safety.sh   # same story as tollgate demo
tollgate certificate             # scorecard for the screen share
```

**Dashboard opens automatically** (macOS/Linux) at http://127.0.0.1:8787/dashboard  
Set `OPEN_DASHBOARD=0` to skip.

In the Control Room:

1. **Protect my first agent** (or you already did via the script)
2. **See protection in action** — feel the loop block again
3. **Prove my setup** — when you have ≥2 providers + keys

**Keys:** not required for Aha #1 (tool-loop block is local admission).  
Optional free path later: `OPENCODE_API_KEY` in `$TOLLGATE_HOME/User/Key.txt`.

**Security:** default bind is `127.0.0.1`. Do not run open mode on `0.0.0.0`.

---

## Path B — Docker

```bash
git clone https://github.com/landjunge/TollGate.git tollgate && cd tollgate
docker compose up -d --build

# Wait until healthy, then:
docker compose exec tollgate tollgate demo --skip-chaos
docker compose exec tollgate tollgate certificate
# Full demo with chaos (needs network + providers in image config):
# docker compose exec tollgate bash scripts/demo-agent-safety.sh
```

Dashboard: http://127.0.0.1:8787/dashboard  

---

## What you should feel (in order)

### 1. Protect (~2 min, no API keys)

Agent lane gets hard rules (example):

```text
$2 / day · $0.50 / request · 20 tool calls · 50 rpm
```

Simulated loop → response:

```text
🛑 REQUEST BLOCKED
Reason: max_tool_calls
Tool calls: 99 / 20
```

**Aha:** the agent cannot run away.

### 2. Route + Prove (~3–5 min)

```bash
tollgate chaos test opencode_zen --requests 8
```

```text
Primary injected down
Fallback activated (when a second provider is enabled)
Survived: yes / no
```

**Aha:** you can **show** recovery, not only configure it.

### 3. Result screen

```bash
tollgate certificate
```

```text
TOLLGATE — AI RELIABILITY REPORT
…
Budget Protection       PASS
Agent Loop Protection   PASS
…
Resilience Score        nn/100
```

---

## Cold-path friction we refuse to reintroduce

| Trap | Fix |
|------|-----|
| 12 docs before first success | This file + `ten-minute.sh` first |
| “What is this?” | Agent safety, not gateway |
| Demo needs paid keys | Protect works offline (admission only) |
| Feature wall | No new pillars until strangers pass this test |

---

## After you pass

Give it to **one** real user (n8n or agent-framework):

> “Protect one agent in 10 minutes. Tell us where you got stuck.”

Feedback > features.  
Full story: [DEMO.md](DEMO.md) · Product lock: [PRODUCT.md](PRODUCT.md)
