# TollGate macOS candidate / macOS-Kandidat

DE: Entwicklungsstand, keine produktive Installation oder native Fünf-App-Abnahme.
Der Host zeigt das bestehende Dashboard; bestehende Budget-, Stop-, Provider- und
Auth-Verträge bleiben maßgeblich. Er vergibt keine zusätzlichen Rechte.

Der Host reserviert einen Listener ausschließlich auf `127.0.0.1` und übergibt ihn
seinem eigenen Python-Kind über fd 0. Er lädt erst nach bestätigtem Kind-PID und
frischem Nonce. Es gibt keine Übernahme eines fremden Servers. Close verbirgt das
Fenster und erhält Backend/Zustand; Quit beendet nur das eigene Kind. Die
WK-Bridge verlangt die eigene WebView, Mainframe, aktuellen Dokument-Origin und
exakten Port. Navigation ist an denselben Origin gebunden. Aus dem Web kommen
nur `requestId` und Katalog-ID, niemals Pfad, URL, PID oder argv.

Ein Familienwechsel verwendet die feste installierte KiraBridge-CLI. Das IPC
läuft außerhalb des MainActor, leert beide Pipes mit je 64 KiB Grenze und wartet
höchstens 30,5 Sekunden plus kurzer Kindbereinigung. Nur ein Versuch ist aktiv;
UNKNOWN bleibt gesperrt, ohne automatischen Retry oder neuen Brokerstart. Ein
Erfolg benötigt Exit 0, echtes JSON-Bool, passendes Ziel, genau ein sichtbares
Familienfenster und endliche positive äußere Maße. Bekannte Ablehnungen benötigen
Exit 2, Fehlercode und explizit `execution_outcome_unknown: false`. Andere oder
widersprüchliche Ergebnisse bleiben UNKNOWN. Dokumentwechsel erhalten keine
veralteten Callbacks. Das kanonische Modul 1.2.2 erhält 31 Sekunden für das native
Resultat; seine Peer-Prüfung bleibt davon getrennt.

## Voraussetzungen und Build

Das Bundle enthält Backend-**Sources**, keinen eigenständigen Python-Runtime.
Erforderlich ist eine explizit gewählte vorhandene Python-3.11+-Umgebung mit
FastAPI >= 0.110, Uvicorn >= 0.27 und Pydantic >= 2.0 aus `pyproject.toml`.
Der Build und der Host prüfen die Imports, installieren aber nichts. Fehlt die
Umgebung oder eine Abhängigkeit, wird verständlich abgebrochen. Ein anderer
Interpreter, ein globales pip oder ein fremder Server sind kein Fallback.
Ein anderer Rechner benötigt diese Voraussetzung erneut; dieser Kandidat ist
kein portables, vollständig gebündeltes Runtime-Paket.

Außerdem: ein Intel-Mac (x86_64, Ziel macOS 13+), Swift/Cocoa/WebKit und die vorhandene originale `TollGate.icns`.
Beispiel (alle Pfade müssen bereits passend vorhanden sein):

```sh
TOLLGATE_PYTHON="/path/to/existing/venv/bin/python" \
TOLLGATE_ICNS="/path/to/original/TollGate.icns" \
TOLLGATE_APP_OUT="/path/to/new-candidate/TollGate.app" \
TOLLGATE_EVIDENCE_OUT="/path/to/new-candidate/bundle-check.json" \
  native/macos/build.sh
```

Der Build verlangt saubere committed Sources, prüft den gesamten Swift-Host und
signiert den **neuen** Kandidaten ad hoc. `codesign --verify --deep --strict`
muss bestehen. Vorhandene Kandidaten und Belege werden nie ersetzt;
Applications-Ziele sind gesperrt. Der Beleg nennt Quellcommit, `source_dirty:
false`, tatsächliche Architektur, Binär-/Originalicon-Hashes, Signaturprüfung,
externe Python-Voraussetzungen und alle Bundle-Dateihashes. Kein Appstart,
Installer oder produktiver Schreibpfad gehört zum Build.

## EN

Development candidate only; installation and real five-app acceptance are separate.
The display host preserves existing dashboard authorization and budget/stop/provider
contracts. It reserves its own loopback listener, passes fd 0 to its exact child
and checks fresh nonce + child PID before loading. It never adopts another server.
Close hides and retains state; Quit terminates only its owned backend.

Native messages require the owned WebView, main frame and exact current loopback
origin/port. Navigation uses the same binding. The page supplies only request ID
and catalog ID; the native host owns all CLI arguments and its caller PID. IPC
runs off the main thread, drains both bounded pipes, permits one in-flight switch
and has a 30.5-second deadline plus short child cleanup. UNKNOWN never retries and
blocks later requests. Strict receipts require real booleans, matching target,
exit status, one visible window and finite positive outer bounds. Navigation
invalidates callbacks to the former document. Shared module 1.2.2 allows 31 seconds
for native completion, separately from peer checks.

The bundle ships backend **sources**, not a self-contained Python runtime. Supply
an existing Python 3.11+ environment with the `pyproject.toml` dependencies and the
original existing ICNS via the build variables above. No installation or global
pip fallback occurs. Missing prerequisites fail visibly. The external interpreter
is required on the target machine; its observed dependency versions are recorded.

Build requires clean committed source, full macOS typechecking, ad-hoc signing
and strict signature verification. It refuses existing outputs and Applications
paths, preserving older candidates. Evidence records the commit, clean source,
actual architecture, binary/icon hashes, runtime prerequisites and every bundle
file hash. Building never launches or installs the product. Linux CI skips only
the Cocoa host check; the actual Foundation Swift receipt/IPC fixture runs wherever
Swift is available. On macOS the compiler and full host check are mandatory.
