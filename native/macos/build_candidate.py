"""Build a new, signed local candidate; never install, start or replace an app."""

from __future__ import annotations

import hashlib
import json
import os
import plistlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def run(*args, cwd=None):
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)


def output_paths(out: Path, evidence: Path):
    # Check resolved parents too; a symlink must not turn a build into installation.
    for path in (out, evidence):
        resolved = path.resolve()
        if any(
            resolved.is_relative_to(base)
            for base in (Path("/Applications"), Path.home() / "Applications")
        ):
            raise ValueError("Production Applications paths are not candidate output")
        if path.exists() or path.is_symlink():
            raise ValueError(f"Refusing to replace existing candidate/evidence: {path}")
    if out.suffix != ".app" or evidence.is_relative_to(out):
        raise ValueError("Expected a new .app and separate evidence file")


def clean_source(root=ROOT):
    if run("git", "status", "--porcelain", "--untracked-files=normal", cwd=root).stdout:
        raise ValueError(
            "Commit the reviewed sources before building (dirty source refused)"
        )
    return run("git", "rev-parse", "HEAD", cwd=root).stdout.strip()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if sys.version_info < (3, 11):  # noqa: UP036 - separate external build interpreter
        raise SystemExit("Build requires Python 3.11+; set TOLLGATE_BUILD_PYTHON")
    native = ROOT / "native/macos"
    out = Path(
        os.environ.get("TOLLGATE_APP_OUT", str(native / "build/candidate/TollGate.app"))
    ).absolute()
    evidence = Path(
        os.environ.get("TOLLGATE_EVIDENCE_OUT", str(out.parent / "bundle-check.json"))
    ).absolute()
    output_paths(out, evidence)
    pin = clean_source()
    if sys.platform != "darwin":
        raise ValueError("Native macOS build required")
    runtime = Path(os.environ["TOLLGATE_PYTHON"]).absolute()
    icon = Path(os.environ["TOLLGATE_ICNS"]).absolute()
    if (
        not os.access(runtime, os.X_OK)
        or not icon.is_file()
        or icon.read_bytes()[:4] != b"icns"
    ):
        raise ValueError("Explicit existing Python and original ICNS are required")
    original_icon_sha = sha(icon)
    prerequisites = json.loads(
        run(str(runtime), "-I", "-B", str(native / "backend_host.py"), "--check").stdout
    )
    source_files = [
        str(native / name)
        for name in ("FamilySwitch.swift", "NativeBackend.swift", "main.swift")
    ]
    with tempfile.TemporaryDirectory(prefix="tollgate-candidate-") as temporary:
        app = Path(temporary) / "TollGate.app"
        macos, resources = app / "Contents/MacOS", app / "Contents/Resources"
        macos.mkdir(parents=True)
        resources.mkdir()
        target = ["-target", "x86_64-apple-macos13.0"]
        run("swiftc", *target, "-typecheck", *source_files)
        run("swiftc", *target, "-O", *source_files, "-o", str(macos / "TollGateHost"))
        shutil.copy2(native / "Info.plist", app / "Contents/Info.plist")
        shutil.copy2(icon, resources / "TollGate.icns")
        shutil.copytree(
            ROOT / "src/tollgate",
            resources / "backend/src/tollgate",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        shutil.copy2(native / "backend_host.py", resources / "backend/backend_host.py")
        (resources / "runtime-python.txt").write_text(str(runtime) + "\n")
        (resources / "runtime-prerequisite.json").write_text(
            json.dumps(prerequisites, indent=2) + "\n"
        )
        with (app / "Contents/Info.plist").open("rb") as source:
            assert plistlib.load(source)["CFBundleIconFile"] == "TollGate.icns"
        run("codesign", "--force", "--sign", "-", str(app))
        verified = run(
            "codesign", "--verify", "--deep", "--strict", "--verbose=2", str(app)
        )
        signature = run("codesign", "-dv", "--verbose=4", str(app))
        if clean_source() != pin:
            raise ValueError("Source changed while building")
        output_paths(out, evidence)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.mkdir()  # atomic exclusive claim; never rm/move over an existing bundle
        for child in app.iterdir():
            shutil.copytree(child, out / child.name)
        run("codesign", "--verify", "--deep", "--strict", "--verbose=2", str(out))
        if sha(out / "Contents/Resources/TollGate.icns") != original_icon_sha:
            raise ValueError("Original ICNS changed during build")
        result = {
            "kind": "local-macos-candidate",
            "source_pin": pin,
            "source_dirty": False,
            "installed": False,
            "gui_started": False,
            "app": str(out),
            "bundle_id": "de.netzwerkpunkt.tollgate",
            "architecture": run(
                "lipo", "-archs", str(out / "Contents/MacOS/TollGateHost")
            ).stdout.strip(),
            "binary_sha256": sha(out / "Contents/MacOS/TollGateHost"),
            "icns_sha256": original_icon_sha,
            "original_icns": str(icon),
            "codesign_verified": True,
            "codesign_verify": verified.stderr,
            "codesign_display": signature.stderr,
            "runtime_bundled": False,
            "runtime_python": str(runtime),
            "runtime_prerequisites": prerequisites,
            "files": [
                {"path": str(p.relative_to(out)), "sha256": sha(p)}
                for p in sorted(out.rglob("*"))
                if p.is_file()
            ],
        }
        evidence.parent.mkdir(parents=True, exist_ok=True)
        with evidence.open("x") as target:
            json.dump(result, target, indent=2)
            target.write("\n")
        print(
            json.dumps(
                {
                    "candidate": str(out),
                    "evidence": str(evidence),
                    "source_pin": pin,
                    "source_dirty": False,
                    "codesign_verified": True,
                }
            )
        )


if __name__ == "__main__":
    main()
