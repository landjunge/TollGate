# n8n-nodes-tollgate

Community node for **[Tollgate](https://github.com/landjunge/tollgate)** — local multi-consumer API admission gateway.

n8n never holds DeepSeek / Brave / Google keys. Only a **consumer label** (open mode) or `id:secret`.

## Install

### Local / custom nodes (desk)

```bash
# from tollgate repo
cd n8n-nodes-tollgate
npm pack   # optional

# link into n8n custom folder
mkdir -p ~/.n8n/custom
cd ~/.n8n/custom
npm init -y
npm install /path/to/tollgate/n8n-nodes-tollgate
# restart n8n
```

Env for n8n to load custom nodes:

```bash
export N8N_CUSTOM_EXTENSIONS=~/.n8n/custom
# or install into n8n's node_modules as community node when published
```

### Docker n8n

Mount or npm-install the package into the container’s custom extensions path, and point Base URL to:

`http://host.docker.internal:8787`

## Credentials

| Field | Example |
|-------|---------|
| Base URL | `http://127.0.0.1:8787` |
| Consumer Key | `n8n` (open) or `n8n:<secret>` |

```bash
tollgate consumer-add n8n
tollgate consumer-budget n8n --max-usd-day 0.5 --max-calls-day 200
```

## Operations

| Op | Endpoint |
|----|----------|
| **Chat** | `POST /v1/chat/completions` → field `text` convenience |
| **Route** | `POST /v1/route` |
| **Budget** | `GET /v1/budget` |
| **Invoke** | `POST /v1/invoke` |
| **Search** | invoke `brave` / `search` |
| **Health** | `GET /v1/health` |

## Without this node

Import HTTP workflows from `../configs/`:

- `n8n-openai-chat.workflow.json`
- `n8n-budget-gate.workflow.json`
- `n8n-search.workflow.json`
- `n8n-route-invoke.workflow.json`

See [docs/N8N.md](../docs/N8N.md).

## License

Netzwerkpunkt Personal Use License 1.0. See [LICENSE](LICENSE).
