# Tollgate — MCP

**Product:** [landjunge/TollGate](https://github.com/landjunge/TollGate)  
**Package entry:** `python -m tollgate` (or `tollgate mcp`)

No `gnom_hub.keys` module. Gnom is only a **client**.

---

## 1) Stdio MCP (Cursor / Claude Desktop / agents)

```bash
# After: pip install -e .  (or git+https://github.com/landjunge/TollGate.git)
# Desk:   unset → ~/.tollgate
# USB:    auto if repo under /Volumes|/media|/mnt, or:
export TOLLGATE_PORTABLE=1
# Explicit data root (best on multi-host stick):
# export TOLLGATE_HOME=/path/to/WS-tollgate

python -m tollgate
# same: tollgate mcp
```

### Cursor `mcp.json` (no machine-local absolute paths)

```json
{
  "mcpServers": {
    "tollgate": {
      "command": "python",
      "args": ["-m", "tollgate"],
      "env": {
        "TOLLGATE_PORTABLE": "1"
      }
    }
  }
}
```

USB details: [PORTABLE.md](PORTABLE.md).

Repo example: [`configs/mcp-tollgate.example.json`](../configs/mcp-tollgate.example.json).

### Tools (stdio) — names match `src/tollgate/mcp_tools.py`

| Tool | Zweck |
|------|--------|
| `keys_dashboard` | Grades, usage, smart route |
| `keys_control` | Health, burn, resilience, attention (Protect·Route·Prove) |
| `keys_desk_status` | Compact status (freeze · score · spend) |
| `keys_resilience` | AI Resilience Score 0–100 + policy |
| `keys_chaos_status` | Chaos injects + last DR report |
| `keys_agent_protect_check` | Dry-run max_tool_calls / budgets for a consumer |
| `keys_audit` | Query deny/usage audit trail (who/why) or summary |
| `keys_report` | Daily Protect·Route·Prove operator brief (json/md) |
| `keys_alert_test` | Webhook probe or event catalog |
| `keys_diagnose` | Issues + actions |
| `keys_status` | Inventory / one provider |
| `keys_route` | Intent → provider + fallbacks |
| `keys_preflight` | Spend-gate before a call |
| `keys_usage` | Today’s token/call ledger |
| `keys_config_get` / `keys_config_patch` | Read / deep-merge `keys_app.json` |
| `keys_limits` | Remaining budget for a provider |
| `keys_auto_update` | start / stop / once |
| `keys_call` | Generic provider op |
| `keys_web_search` | Brave via admission |
| `keys_elevenlabs_budget` | TTS floor (`ELEVENLABS_MIN_REMAINING`) |
| `keys_zen_chat` | OpenCode Zen free chat |
| `keys_research` | Offline distill research |

### Resources

| URI | Inhalt |
|-----|--------|
| `keys://app/config` | `keys_app.json` |
| `keys://app/usage` | `keys_usage.json` |
| `keys://app/dashboard` | Dashboard snapshot |
| `keys://app/research` | Research notes |

---

## 2) HTTP surface (Tollgate server, **:8787**)

Run:

```bash
tollgate serve
# → http://127.0.0.1:8787/docs
```

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/v1/health` | Liveness + circuits |
| `GET` | `/v1/providers` | Inventory grades (masked keys) |
| `GET` | `/v1/budget` | Remaining limits |
| `POST` | `/v1/route` | intent → provider/model |
| `POST` | `/v1/invoke` | admit + call + meter |
| `GET` | `/v1/usage` | Daily ledger |
| `GET` / `POST` | `/v1/config` | Read / deep-merge config (**desk-local; not for public bind**) |

Header: `X-Consumer-Key: n8n` (placeholder until hashed consumer secrets).

```bash
curl -s http://127.0.0.1:8787/v1/health | jq .
curl -s -X POST http://127.0.0.1:8787/v1/route \
  -H 'Content-Type: application/json' \
  -H 'X-Consumer-Key: cursor' \
  -d '{"intent":"free_llm"}'
```

> **Not** Gnom hub `:8080` `/api/mcp/keys/*`. That was the old in-hub surface. Prefer this product’s `/v1/*` or stdio MCP.

---

## 3) Gnom as client (optional)

Gnom may still expose hub tools that **delegate** into Tollgate after `pip install tollgate`.  
That is integration, not ownership — implement against `from tollgate import …`, not a forked keys tree.

---

## Metering through MCP

`keys_zen_chat`, `keys_web_search`, and `keys_call` go through `KeysService.call` / gateway →  
**limits + usage + circuit feedback** on the response.
