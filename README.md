**English** · [Deutsch](README.de.md)

<p align="center">
  <img src="assets/design/icons/dark/TollGate-dark-256.png" alt="TollGate" width="256" height="256">
</p>

<p align="center">
  <a href="https://github.com/landjunge/threaddesk/blob/main/README.md" title="ThreadDesk"><img src="assets/readme/ThreadDesk-dark-128.png" alt="ThreadDesk" width="48" height="48"></a>
  &nbsp;
  <a href="https://github.com/landjunge/KiraBridge/blob/main/README.md" title="KiraBridge"><img src="assets/readme/KiraBridge-dark.svg" alt="KiraBridge" width="48" height="48"></a>
  &nbsp;
  <a href="https://github.com/landjunge/4AllPass/blob/main/README.md" title="4AllPass"><img src="assets/readme/4AllPass-dark-128.png" alt="4AllPass" width="48" height="48"></a>
  &nbsp;
  <a href="https://github.com/landjunge/agent-authority-lab/blob/main/README.md" title="AgentAuthority"><img src="assets/readme/Agent-Authority-dark.svg" alt="AgentAuthority" width="48" height="48"></a>
</p>

<p align="center"><img src="assets/design/wordmarks/TollGate-dark.svg" alt="TollGate" width="280"></p>

<p align="center"><strong>A safety gate for AI agents.</strong></p>

TollGate checks connected model and tool calls before they execute. It helps stop repeated calls, limit usage and explain decisions.

**Source version: 1.0.12 · In development · Python 3.11 or newer**

[Quick start from source](docs/QUICKSTART.md) · [View source](https://github.com/landjunge/tollgate/tree/main)

There is no published desktop installer. The [announcement release](https://github.com/landjunge/tollgate/releases/tag/announce-public) has no packaged downloads. Use requires permission under the [license](LICENSE).

## What TollGate helps you do

- **Protect:** usage limits, loop protection, rules for permitted access and a freeze for new calls.
- **Route:** health-aware routing and failover to configured providers.
- **Prove:** outage and recovery simulations with reports about the tested setup.
- **Connections:** an OpenAI-compatible gateway, MCP and n8n; English and German controls.

The local workflow-control core adds durable reservations and stops for explicitly connected adapters. Acceptance with synthetic adapters is separate from configured production use with KiraBridge or 4AllPass. Cost estimates are not provider invoices and do not guarantee a spending cap for arbitrary terminal agents.

**Boundary:** Freeze blocks new connected calls. It does not terminate arbitrary processes or undo effects already sent. [Workflow control](docs/WORKFLOW-CONTROL.md) · [Process stops](docs/WORKFLOW-PROCESS-STOP.md).

## Get started

With permission to use the software and Python 3.11 or newer:

1. **Set up.** Follow the [quick start](docs/QUICKSTART.md) to install TollGate locally.
2. **Run the demo.** Run the Protect demo from the quick start.
3. **Inspect the result.** Open the local dashboard to see why TollGate allowed or blocked a call.

The Protect demo needs no provider keys. Then check the local dashboard to see why a call was allowed or blocked. Real model calls and routing require your own provider accounts. [Quick start](docs/QUICKSTART.md).

## Planned collaboration

The five products remain independent. The goal is a shared workflow with **KiraBridge as the communication hub**:

| Product | Role in the shared workflow |
| --- | --- |
| [ThreadDesk](https://github.com/landjunge/threaddesk/blob/main/README.md) | Keeps project context, knowledge and results. |
| [KiraBridge](https://github.com/landjunge/KiraBridge/blob/main/README.md) | Relays tasks, questions and replies between chat, local agents and tools. |
| [4AllPass](https://github.com/landjunge/4AllPass/blob/main/README.md) | Manages credentials; is intended to enable specifically approved access. |
| [TollGate](https://github.com/landjunge/tollgate/blob/main/README.md) | Checks connected calls and enforces usage limits and stops. |
| [AgentAuthority](https://github.com/landjunge/agent-authority-lab/blob/main/README.md) | Shows observations, contradictions and missing evidence; does not approve actions. |

Some interfaces already exist. A fully configured and verified workflow across all five products is still planned. Approvals stay with the responsible tool and the human. KiraBridge and AgentAuthority require access to their private repositories.

## License

[Source-available, all rights reserved](LICENSE). Visible source does not grant general permission to use or redistribute it. Historical MIT license rights remain intact.

Product concept and architecture: **Daniel Filipek (landjunge)**. AI assists with implementation and documentation. The documented checks do not replace an independent security audit; verifiable reviews are welcome.

[User guide](docs/USER_GUIDE.md) · [Documentation](docs/README.md) · [Developer details](docs/DEVELOPERS.md) · [Product website](https://tollgate.netzwerkpunkt.de/)
