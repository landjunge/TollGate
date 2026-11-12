#!/usr/bin/env bash
# Compile the lean TollGate macOS host (AppKit WKWebView) into a standalone
# binary. This does NOT build a .app bundle, does NOT overwrite an existing app,
# does NOT install and does NOT start anything. Bundle/install/start remain a
# separate Codex-gated step.
set -euo pipefail
cd "$(dirname "$0")"

OUT="${TOLLGATE_HOST_OUT:-./build/TollGateHost}"
mkdir -p "$(dirname "$OUT")"

swiftc -O \
  FamilySwitch.swift main.swift \
  -o "$OUT"

echo "built: $OUT"
