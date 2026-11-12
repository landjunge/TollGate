#!/usr/bin/env bash
# Candidate only; explicit existing runtime + original ICNS, no installation.
set -euo pipefail
NATIVE_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_PYTHON="${TOLLGATE_BUILD_PYTHON:-${TOLLGATE_PYTHON:?Set TOLLGATE_PYTHON to an existing Python 3.11+ environment}}"
exec "$BUILD_PYTHON" "$NATIVE_DIR/build_candidate.py"
