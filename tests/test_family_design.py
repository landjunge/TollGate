"""Family-design shared module + native host checks (no provider/OS action)."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tollgate.server_v1 import app

ROOT = Path(__file__).resolve().parents[1]
NP = ROOT / "src" / "tollgate" / "static" / "np"
MACOS = ROOT / "native" / "macos"

client = TestClient(app)


def test_shared_module_files_match_sha256():
    sums = {}
    for line in (
        (NP / "networkpunkt-appbar-SHA256SUMS").read_text(encoding="utf-8").splitlines()
    ):
        if not line.strip():
            continue
        digest, _, name = line.partition("  ")
        sums[name.strip()] = digest.strip()
    assert len(sums) == 13
    bundle = json.loads(
        (NP / "networkpunkt-appbar-bundle.json").read_text(encoding="utf-8")
    )
    assert bundle["version"] == "1.2.2"
    assert set(bundle["files"]) <= set(sums)
    for name, expected in sums.items():
        assert hashlib.sha256((NP / name).read_bytes()).hexdigest() == expected, name
    # The SHA list itself is pinned.
    assert hashlib.sha256(
        (NP / "networkpunkt-appbar-SHA256SUMS").read_bytes()
    ).hexdigest() == (
        "689bf4c25bdcff41c095791c6f63128b46dc69785adef52b6ffc8c78fd82081e"
    )


def test_dashboard_has_family_switch_bridge_and_open_target():
    html = client.get("/dashboard").text
    assert "data-product-header" in html
    assert "mountProductHeader" in html
    assert "openTarget: (appId) => window.__tgFamilySwitch(appId)" in html
    assert "messageHandlers.familySwitch" in html
    # Only the catalog id crosses the boundary; no URL/PID/argv in the bridge.
    assert "postMessage({requestId: requestId, appId: appId})" in html


def test_static_header_assets_whitelist_still_serve():
    assert client.get("/static/np/networkpunkt-appbar.js").status_code == 200
    assert client.get("/static/np/networkpunkt-appbar.css").status_code == 200
    assert client.get("/static/np/networkpunkt.css").status_code == 200
    assert client.get("/static/np/np-appbar-tollgate-dark-256.png").status_code == 200
    assert client.get("/static/np/..%2Fserver_v1.py").status_code == 404


@pytest.mark.skipif(sys.platform != "darwin", reason="Cocoa/WebKit require macOS")
def test_native_host_typechecks():
    assert shutil.which("swiftc"), "macOS acceptance requires swiftc"
    result = subprocess.run(
        [
            "swiftc",
            "-target",
            "x86_64-apple-macos13.0",
            "-typecheck",
            "FamilySwitch.swift",
            "NativeBackend.swift",
            "main.swift",
        ],
        cwd=str(MACOS),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr
