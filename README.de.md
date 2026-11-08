<!-- readme-header-v1: Kopf nach ThreadDesk docs/contracts/readme-header-v1.md. Nicht von Hand umgestalten; scripts/readme_header.py apply/check verwenden. -->

[English](README.md) · **Deutsch**

<p align="center">
  <img src="assets/readme/normalized/TollGate-large.svg" alt="TollGate" width="256" height="256">
</p>

<p align="center">
  <a href="https://github.com/landjunge/KiraBridge/blob/main/README.de.md" title="KiraBridge"><img src="assets/readme/normalized/KiraBridge-small.svg" alt="KiraBridge" width="48" height="48"></a>
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

<p align="center"><strong>Eine Sicherheitsschranke für KI-Agenten.</strong></p>

TollGate prüft angeschlossene Modell- und Werkzeugaufrufe, bevor sie ausgeführt werden. Es hilft, wiederholte Aufrufe zu stoppen, Verbrauch zu begrenzen und Entscheidungen nachzuvollziehen.

**Quellstand: 1.0.12 · In Entwicklung · Python 3.11 oder neuer**

[Schnellstart aus dem Quellcode](docs/QUICKSTART.md) · [Quellcode ansehen](https://github.com/landjunge/tollgate/tree/main)

Es gibt keinen veröffentlichten Desktop-Installer. Das [Ankündigungsrelease](https://github.com/landjunge/tollgate/releases/tag/announce-public) enthält keine fertigen Pakete. Die Nutzung benötigt eine Erlaubnis gemäß [Lizenz](LICENSE).

## Wobei TollGate dir hilft

- **Protect:** Verbrauchsgrenzen, Schleifenschutz, Regeln für erlaubte Zugriffe und eine Sperre für neue Aufrufe.
- **Route:** zustandsabhängige Weiterleitung und Ausweichen auf konfigurierte Anbieter.
- **Prove:** Ausfall- und Wiederanlauf-Simulationen mit Berichten über das geprüfte Setup.
- **Anbindung:** OpenAI-kompatibles Gateway, MCP und n8n; deutsch- und englischsprachige Bedienung.

Der lokale Auftragskontrollkern ergänzt dauerhafte Reservierungen und Stopps für ausdrücklich angeschlossene Adapter. Die Abnahme mit synthetischen Adaptern ist kein fertig eingerichteter KiraBridge-/4AllPass-Produktionsbetrieb. Kostenschätzungen sind keine Anbieterrechnungen und garantieren kein Kostenlimit für beliebige Terminalagenten.

**Grenze:** „Freeze“ blockiert neue angeschlossene Aufrufe. Es beendet keine beliebigen Prozesse und macht bereits ausgelöste Wirkungen nicht rückgängig. [Auftragskontrolle](docs/WORKFLOW-CONTROL.md) · [Prozessstopps](docs/WORKFLOW-PROCESS-STOP.md).

## Loslegen

Mit Nutzungserlaubnis und Python 3.11 oder neuer:

1. **Einrichten.** Folge dem [Schnellstart](docs/QUICKSTART.md), um TollGate lokal zu installieren.
2. **Demo starten.** Führe die Protect-Demo aus dem Schnellstart aus.
3. **Ergebnis ansehen.** Öffne das lokale Dashboard und sieh nach, warum TollGate einen Aufruf erlaubt oder blockiert hat.

Die Protect-Demo braucht keine Anbieter-Schlüssel. Prüfe anschließend im lokalen Dashboard, warum ein Aufruf erlaubt oder blockiert wurde. Für echte Modellaufrufe und Weiterleitung brauchst du eigene Anbieterzugänge. [Schnellstart](docs/QUICKSTART.md).

## Geplante Zusammenarbeit

Die fünf Produkte bleiben eigenständig. Geplant ist ein gemeinsamer Ablauf mit **KiraBridge als Kommunikationszentrale**:

| Produkt | Aufgabe im gemeinsamen Ablauf |
| --- | --- |
| [ThreadDesk](https://github.com/landjunge/threaddesk/blob/main/README.md) | Bewahrt Projektstand, Wissen und Ergebnisse. |
| [KiraBridge](https://github.com/landjunge/KiraBridge/blob/main/README.de.md) | Vermittelt Aufträge, Rückfragen und Antworten zwischen Chat, lokalen Agenten und Werkzeugen. |
| [4AllPass](https://github.com/landjunge/4AllPass/blob/main/README.md) | Verwaltet Zugangsdaten; soll gezielt erlaubte Zugriffe ermöglichen. |
| [TollGate](https://github.com/landjunge/tollgate/blob/main/README.de.md) | Prüft angeschlossene Aufrufe und setzt Verbrauchsgrenzen und Stopps durch. |
| [AgentAuthority](https://github.com/landjunge/agent-authority-lab/blob/master/README.md) | Zeigt Beobachtungen, Widersprüche und fehlende Belege; erteilt keine Freigaben. |

Einzelne Schnittstellen sind vorhanden. Ein vollständig eingerichteter und geprüfter Ablauf aller fünf Produkte ist noch geplant. Freigaben bleiben beim zuständigen Werkzeug und beim Menschen. KiraBridge und AgentAuthority benötigen Zugriff auf ihre privaten Repositorys.

## Lizenz

[Source-available, alle Rechte vorbehalten](LICENSE). Sichtbarer Quellcode erteilt keine allgemeine Nutzungs- oder Weiterverteilungserlaubnis. Historische MIT-Lizenzrechte bleiben erhalten.

Produktidee und Architektur: **Daniel Filipek (landjunge)**. KI unterstützt Implementierung und Dokumentation. Die dokumentierten Prüfungen ersetzen kein unabhängiges Sicherheitsaudit; nachvollziehbare Reviews sind willkommen.

[Hilfe auf Deutsch](docs/HILFE.md) · [Dokumentation](docs/README.md) · [Entwicklerdetails](docs/DEVELOPERS.md) · [Produktseite](https://tollgate.netzwerkpunkt.de/)
