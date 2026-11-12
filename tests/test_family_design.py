"""Family-design shared module + native host checks (no provider/OS action)."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
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
    assert bundle["version"] == "1.2.1"
    assert set(bundle["files"]) <= set(sums)
    for name in sums:
        target = NP / name if (NP / name).is_file() else NP / name
        assert hashlib.sha256(target.read_bytes()).hexdigest() == sums[name], name
    # The SHA list itself is pinned.
    assert hashlib.sha256(
        (NP / "networkpunkt-appbar-SHA256SUMS").read_bytes()
    ).hexdigest() == (
        "0cc066e86e9f1ea8a6e7add8f6a4da4f22a3b4574bd5f7d7715c3dcc854e176a"
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


def test_family_switch_abi_outcome_mapping():
    # Mirrors FamilySwitch.outcome; the CLI ABI JSON shapes must stay stable.
    def outcome(data: bytes, target: str) -> str:
        try:
            value = json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return "uncertain"
        if not isinstance(value, dict):
            return "uncertain"
        if value.get("success") is True:
            return "focused" if value.get("active_product") == target else "uncertain"
        if value.get("execution_outcome_unknown"):
            return "uncertain"
        code = (value.get("error") or {}).get("code", "")
        return "missing" if code == "missing" else "failed"

    ok = {
        "success": True,
        "active_product": "threaddesk",
        "actual_outer_bounds": {"x": 0, "y": 0, "width": 1360, "height": 780},
        "visible_family_windows": 1,
    }
    assert outcome(json.dumps(ok).encode(), "threaddesk") == "focused"
    assert outcome(json.dumps(ok).encode(), "tollgate") == "uncertain"
    assert (
        outcome(
            json.dumps(
                {
                    "success": False,
                    "error": {"code": "missing", "message": ""},
                    "execution_outcome_unknown": False,
                }
            ).encode(),
            "tollgate",
        )
        == "missing"
    )
    assert (
        outcome(
            json.dumps(
                {
                    "success": False,
                    "error": {"code": "busy", "message": ""},
                    "execution_outcome_unknown": False,
                }
            ).encode(),
            "tollgate",
        )
        == "failed"
    )
    assert (
        outcome(
            json.dumps({"success": False, "execution_outcome_unknown": True}).encode(),
            "tollgate",
        )
        == "uncertain"
    )
    assert outcome(b"not json", "tollgate") == "uncertain"


@pytest.mark.skipif(shutil.which("swiftc") is None, reason="swiftc not available")
def test_native_host_typechecks():
    result = subprocess.run(
        ["swiftc", "-typecheck", "FamilySwitch.swift", "main.swift"],
        cwd=str(MACOS),
        capture_output=True,
        text=True,
        timeout=120,
    )
    # Only the known non-fatal WebKit Sendable warning is tolerated.
    assert result.returncode == 0, result.stderr
