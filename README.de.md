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

## Ein konkreter Anwendungsfall: Werkzeugschleifen stoppen

**Problem:** Ein KI-Agent wiederholt unkontrolliert Aufrufe angeschlossener Werkzeuge. **TollGate** kann Aufrufe über seinen eingerichteten Gateway stoppen; beliebige Terminalprozesse stoppt es nicht, und die tatsächliche Anbieterrechnung wird nicht garantiert begrenzt.

**Protect-Demo aus dem Quellcode (Python 3.11+, Nutzung nur gemäß [LICENSE](LICENSE)):**

```sh
git clone https://github.com/landjunge/tollgate.git && cd tollgate
python3 -m venv .venv && .venv/bin/pip install -e .
./scripts/ten-minute.sh
```

Das Demo soll einen **blockierten Werkzeug-Loop** und eine Auswertung zeigen; das lokale Dashboard liegt unter `http://127.0.0.1:8787/dashboard`. Für diese Demo sind keine Anbieter-API-Schlüssel nötig. [Ausführlicher Schnellstart](docs/QUICKSTART.md) · [Funktionsgrenzen](docs/WORKFLOW-CONTROL.md). **Ein Desktop-Installer ist noch nicht veröffentlicht.**

## Die Werkzeugfamilie und ihre Grenzen

**KiraBridge ist der zentrale Weg zur Sprach- und Computersteuerung in der NetzwerkPunkt-Werkzeugfamilie.** Darüber lassen sich mit den nötigen Rechten Programme öffnen, Fenster wechseln, Notizen schreiben, Texte direkt eingeben und Shortcuts ausführen. **TollGate ergänzt diese Steuerung als Sicherheits- und Budgetgrenze:** Ein bequemer Sprachauftrag soll nicht zu unkontrollierten Wiederholungen, verdecktem Verbrauch oder überraschenden Kosten führen.

Die Familie umfasst **KiraBridge** für die Verbindung und direkte Computersteuerung, **ThreadDesk** für Projekte und Arbeitsstände, **4AllPass** für Zugänge und Schlüssel, **TollGate** für Nutzungsgrenzen und Budgets sowie **Agent Authority** für ausschließlich lesende Beobachtung und Nachweise. Jedes Werkzeug bleibt eigenständig. Die durchgängige gemeinsame Bedienung über natürliche Sprache ist ein Entwicklungsziel; einzelne Integrationen und Pläne sind nicht automatisch produktiv verfügbar.

## Verbrauch und Grenzen im Sprachablauf verstehen

**Die natürliche Sprachbedienung von Computer und KI-Werkzeugen für alle ist das übergreifende Ziel der NetzwerkPunkt-Familie.** KiraBridge vermittelt die Aufträge, während TollGate bei angeschlossenen Aufrufen Verbrauch, Warnungen, Budgetgrenzen und Stopps nachvollziehbar machen soll. Auch ein einfach formulierter Sprachauftrag muss sicher kontrollierbar bleiben.

**Barrierearme Nutzung wird dabei mitgedacht, ist aber nicht das Hauptziel oder eine ausschließliche Zielgruppe.** Verständliche Rückmeldungen können Menschen mit Behinderungen oder eingeschränkter Mobilität besonders helfen, sind aber für alle sinnvoll, die per Sprache oder ohne komplizierte Oberflächen arbeiten. Sprache ersetzt weder Zugriffsprüfungen noch menschliche Entscheidungen über wichtige Kosten und Aktionen.

**Entwicklungsstand:** TollGate ist kein Versprechen für eine fertige, providerübergreifende Verbrauchsüberwachung. Modell- und Tarifregeln, Resetzeitpunkte und Datenzugriffe müssen für jeden Anbieter und Produkttyp gesondert belegt werden. Insbesondere sind individuelle Grok-Team-Wochenkontingente pro Sitz und gemeinsam genutztes Zusatzguthaben getrennt zu modellieren; dokumentierte xAI-API-Endpunkte beweisen keinen entsprechenden Zugriff für Grok-Abonnements. Wir verbessern die Zuverlässigkeit und Transparenz fortlaufend, ohne unbestätigte Daten als live verfügbar auszugeben.

TollGate prüft angeschlossene Modell- und Werkzeugaufrufe, bevor sie ausgeführt werden. Es hilft, wiederholte Aufrufe zu stoppen, Verbrauch zu begrenzen und Entscheidungen nachzuvollziehen.

**Quellstand: 1.0.12 · In Entwicklung · Python 3.11 oder neuer**

[Schnellstart aus dem Quellcode](docs/QUICKSTART.md) · [Quellcode ansehen](https://github.com/landjunge/tollgate/tree/main)

Es gibt keinen veröffentlichten Desktop-Installer. Das [Ankündigungsrelease](https://github.com/landjunge/tollgate/releases/tag/announce-public) enthält keine fertigen Pakete. Die Nutzung benötigt eine Erlaubnis gemäß [Lizenz](LICENSE).

## Wobei TollGate dir hilft

- **Protect:** Verbrauchsgrenzen, Schleifenschutz, Regeln für erlaubte Zugriffe und eine Sperre für neue Aufrufe.
- **Route:** zustandsabhängige Weiterleitung und Ausweichen auf konfigurierte Anbieter.
- **Prove:** Ausfall- und Wiederanlauf-Simulationen mit Berichten über das geprüfte Setup.
- **Anbindung:** OpenAI-kompatibles Gateway, MCP und n8n; deutsch- und englischsprachige Bedienung.

Der lokale Auftragskontrollkern ergänzt dauerhafte Reservierungen und Stopps für ausdrücklich angeschlossene Adapter. Auf diesem Budget- und Wiederholungsjournal werden strukturierte Agentenereignisse nach Auftrag, Sitzung und Ereignis idempotent zugeordnet: Eine Auftrags-Task-ID ist keine Anbieter-Sitzungs-ID, und ein unbekannter oder gestoppter Ausgang blockiert weitere Dispatches, statt sie erneut auszuführen. Das ist lokale Ereigniszuordnung, kein Live-Anbieter und keine universelle Kostengrenze. Die Abnahme mit synthetischen Adaptern ist kein fertig eingerichteter KiraBridge-/4AllPass-Produktionsbetrieb. Kostenschätzungen sind keine Anbieterrechnungen und garantieren kein Kostenlimit für beliebige Terminalagenten.

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
