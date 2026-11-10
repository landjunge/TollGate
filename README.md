<!-- readme-header-v1: Kopf nach ThreadDesk docs/contracts/readme-header-v1.md. Nicht von Hand umgestalten; scripts/readme_header.py apply/check verwenden. -->

**English** · [Deutsch](README.de.md)

<p align="center">
  <img src="assets/readme/normalized/TollGate-large.svg" alt="TollGate" width="256" height="256">
</p>

<p align="center">
  <a href="https://github.com/landjunge/KiraBridge#readme" title="KiraBridge"><img src="assets/readme/normalized/KiraBridge-small.svg" alt="KiraBridge" width="48" height="48"></a>
  &nbsp;
  <a href="https://github.com/landjunge/threaddesk#readme" title="ThreadDesk"><img src="assets/readme/normalized/ThreadDesk-small.svg" alt="ThreadDesk" width="48" height="48"></a>
  &nbsp;
  <a href="https://github.com/landjunge/4AllPass#readme" title="4AllPass"><img src="assets/readme/normalized/4AllPass-small.svg" alt="4AllPass" width="48" height="48"></a>
  &nbsp;
  <a href="https://github.com/landjunge/agent-authority-lab#readme" title="Agent Authority"><img src="assets/readme/normalized/Agent-Authority-small.svg" alt="Agent Authority" width="48" height="48"></a>
  &nbsp;
  <a href="https://github.com/landjunge/blockdesign#readme" title="BlockDesign"><img src="assets/readme/normalized/BlockDesign-small.svg" alt="BlockDesign" width="48" height="48"></a>
</p>

<p align="center"><picture><source media="(prefers-color-scheme: dark)" srcset="assets/design/wordmarks/TollGate-dark.svg"><img src="assets/design/wordmarks/TollGate-light.svg" alt="TollGate" width="280"></picture></p>

<!-- AUTO-DOWNLOADS:START -->
<p align="center">
  <a href="https://github.com/landjunge/tollgate/archive/refs/heads/main.zip" title="tollgate-main.zip herunterladen / download"><img src="assets/readme/download-source.svg" alt="Download Quellcode / Source ZIP · 1.0.12" width="190" height="52"></a>
</p>
<!-- AUTO-DOWNLOADS:END -->

<p align="center"><strong>A safety gate for AI agents.</strong></p>

**Part of the NetzwerkPunkt tool family:** KiraBridge connects ChatGPT to tools on your computer and is the central path for voice or chat control. The family includes **KiraBridge** (connection and control), **ThreadDesk** (projects and work history), **4AllPass** (accounts and credentials), **TollGate** (usage limits and budgets), and **Agent Authority** (observation and evidence only). Each tool also works in its own role. **Voice-driven integration across all five is the shared development goal:** existing connections and planned features are documented separately rather than presented as fully released.

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
| [AgentAuthority](https://github.com/landjunge/agent-authority-lab/blob/master/README.md) | Shows observations, contradictions and missing evidence; does not approve actions. |

Some interfaces already exist. A fully configured and verified workflow across all five products is still planned. Approvals stay with the responsible tool and the human. KiraBridge and AgentAuthority require access to their private repositories.

## License

[Source-available, all rights reserved](LICENSE). Visible source does not grant general permission to use or redistribute it. Historical MIT license rights remain intact.

Product concept and architecture: **Daniel Filipek (landjunge)**. AI assists with implementation and documentation. The documented checks do not replace an independent security audit; verifiable reviews are welcome.

[User guide](docs/USER_GUIDE.md) · [Documentation](docs/README.md) · [Developer details](docs/DEVELOPERS.md) · [Product website](https://tollgate.netzwerkpunkt.de/)
