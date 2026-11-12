#!/usr/bin/env bash
# Build a local Intel-macOS candidate: compile the Swift host, derive the ICNS
# from the original dark PNGs, and bundle a .app with a self-contained backend
# source. This produces a TEMPORARY candidate only — it never overwrites an
# existing app, never installs and never changes productive paths. Bundle,
# install and start remain a separate Codex-gated step.
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(cd ../.. && pwd)"

OUT="${TOLLGATE_APP_OUT:-$ROOT/native/macos/build/TollGate.app}"
EVIDENCE="$ROOT/native/macos/build/evidence.json"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/tollgate-host.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

echo "== compile Swift host =="
swiftc -O FamilySwitch.swift main.swift -o "$WORK/TollGateHost"

echo "== derive ICNS from original dark PNGs =="
ICONSET="$WORK/TollGate.iconset"
mkdir -p "$ICONSET"
ICONS="$ROOT/assets/design/icons/dark"
cp "$ICONS/TollGate-dark-16.png"   "$ICONSET/icon_16x16.png"
cp "$ICONS/TollGate-dark-32.png"   "$ICONSET/icon_16x16@2x.png"
cp "$ICONS/TollGate-dark-32.png"   "$ICONSET/icon_32x32.png"
cp "$ICONS/TollGate-dark-64.png"   "$ICONSET/icon_32x32@2x.png"
cp "$ICONS/TollGate-dark-128.png"  "$ICONSET/icon_128x128.png"
cp "$ICONS/TollGate-dark-256.png"  "$ICONSET/icon_128x128@2x.png"
cp "$ICONS/TollGate-dark-256.png"  "$ICONSET/icon_256x256.png"
cp "$ICONS/TollGate-dark-512.png"  "$ICONSET/icon_256x256@2x.png"
cp "$ICONS/TollGate-dark-512.png"  "$ICONSET/icon_512x512.png"
cp "$ICONS/TollGate-dark-1024.png" "$ICONSET/icon_512x512@2x.png"
iconutil -c icns "$ICONSET" -o "$WORK/TollGate.icns"

echo "== bundle .app candidate =="
APP="$WORK/TollGate.app"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources/backend/src"
cp "$WORK/TollGateHost" "$APP/Contents/MacOS/TollGateHost"
cp "$WORK/TollGate.icns"  "$APP/Contents/Resources/TollGate.icns"
cp Info.plist             "$APP/Contents/Info.plist"
# Self-contained backend source (pinned working tree, no dev-WT runtime dependency).
rsync -a --exclude '__pycache__' --exclude '*.pyc' \
  "$ROOT/src/tollgate/" "$APP/Contents/Resources/backend/src/tollgate/"

echo "== evidence =="
mkdir -p "$(dirname "$OUT")"
rm -rf "$OUT"
mv "$APP" "$OUT"

SOURCE_PIN="$(git -C "$ROOT" rev-parse HEAD)"
BINARY_SHA="$(shasum -a 256 "$OUT/Contents/MacOS/TollGateHost" | awk '{print $1}')"
ICNS_SHA="$(shasum -a 256 "$OUT/Contents/Resources/TollGate.icns" | awk '{print $1}')"
SIGNATURE="$(codesign -dv "$OUT" 2>&1 || echo "unsigned")"

python3 - "$OUT" "$EVIDENCE" "$SOURCE_PIN" "$BINARY_SHA" "$ICNS_SHA" "$SIGNATURE" <<'PY'
import hashlib, json, sys
from pathlib import Path
app, evidence, pin, binary_sha, icns_sha, signature = sys.argv[1:7]
root = Path(app)
files = []
for p in sorted(root.rglob("*")):
    if p.is_file():
        files.append({"path": str(p.relative_to(root)), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()})
json.dump({
    "kind": "local-macos-candidate",
    "bundle_id": "de.netzwerkpunkt.tollgate",
    "source_pin": pin,
    "binary_sha256": binary_sha,
    "icns_sha256": icns_sha,
    "codesign": signature,
    "files": files,
}, open(evidence, "w"), indent=2)
print(json.dumps({"candidate": app, "source_pin": pin, "codesign": signature.splitlines()[0] if signature != "unsigned" else "unsigned"}))
PY

echo "built: $OUT"
echo "evidence: $EVIDENCE"
