# Quickstart — 5–10 minutes to protect your first agent

> **Connect your agent. Tollgate protects it automatically.**

**Port:** `8787` (not 8000).

---

## 1. Install & run cold path

```bash
git clone https://github.com/landjunge/TollGate.git tollgate && cd tollgate
python3 -m venv .venv && .venv/bin/pip install -e .
./scripts/ten-minute.sh
```

You should see a **tool-loop BLOCKED** (Protect) and a scorecard.  
Dashboard opens at: **http://127.0.0.1:8787/dashboard**

Skip browser open: `OPEN_DASHBOARD=0 ./scripts/ten-minute.sh`

---

## 2. Point an existing OpenAI app at Tollgate

```bash
export OPENAI_BASE_URL=http://127.0.0.1:8787/v1
export OPENAI_API_KEY=my-agent          # open mode: any label = agent lane
# auth mode:  OPENAI_API_KEY=id:secret
```

Python:

```python
from openai import OpenAI
client = OpenAI(base_url="http://127.0.0.1:8787/v1", api_key="my-agent")
print(client.chat.completions.create(
    model="tollgate/free",
    messages=[{"role": "user", "content": "hi"}],
).choices[0].message.content)
```

**No other code changes.** Same SDK, new endpoint.

Keep the server running: `tollgate serve` (binds **127.0.0.1:8787** by default).

---

## 3. Control Room

http://127.0.0.1:8787/dashboard

| Button | Meaning |
|--------|---------|
| **Protect my first agent** | Name lane + budget + tool-loop limit |
| **See protection in action** | Simulate runaway loop → hard stop |
| **Prove my setup** | Failover test when ≥2 providers + keys |

---

## Keys (optional for Protect)

Protect (tool-loop) works **without** provider API keys.  
Real chat / Route Prove need keys in `$TOLLGATE_HOME/User/Key.txt` (default `~/.tollgate/User/Key.txt`).

---

## Next

| Doc | When |
|-----|------|
| [HOW_IT_WORKS.md](HOW_IT_WORKS.md) | Understand Protect · Route · Prove |
| [PRODUCTION_CHECKLIST.md](PRODUCTION_CHECKLIST.md) | Before real traffic |
| [OPENAI.md](OPENAI.md) | Drop-in details, models, tool_calls_est |
| [E2E_GNOM_HUB.md](E2E_GNOM_HUB.md) | Real stack: gnom-hub-v1 → Tollgate |

If the first 10 minutes confuse you, **that is a product bug** — say where.
