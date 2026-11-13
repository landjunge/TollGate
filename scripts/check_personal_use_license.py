#!/usr/bin/env python3
"""Check Netzwerkpunkt Personal Use License 1.0 in a product repo and packages.

Shared by 4AllPass, TollGate, ThreadDesk, KiraBridge and Agent Authority.
The five copies are identical (see TOOL_VERSION). The script only reads; it
never writes LICENSE or README. GitHub Actions runs it on pull requests and
on the default branch.

Exit 0 when LICENSE, README, package metadata and packaging recipes agree.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

TOOL_VERSION = "1.0.2"
LICENSE_TITLE = "Netzwerkpunkt Personal Use License 1.0"

PRODUCTS = {
    "4allpass": "4AllPass",
    "tollgate": "TollGate",
    "threaddesk": "ThreadDesk",
    "kirabridge": "KiraBridge",
    "agent-authority": "Agent Authority",
}
REPO_TO_PRODUCT = {
    "4AllPass": "4allpass",
    "tollgate": "tollgate",
    "threaddesk": "threaddesk",
    "KiraBridge": "kirabridge",
    "agent-authority-lab": "agent-authority",
}
FOREIGN = (
    "4AllPass",
    "TollGate",
    "ThreadDesk",
    "KiraBridge",
    "Gnom-Hub",
    "Agent Authority",
    "BlockDesign",
)
ALLOWED_LICENSE_REF = "LicenseRef-Netzwerkpunkt-Personal-Use-1.0"
PACKAGE_JSON_FIXED = (
    "package.json",
    "frontend/package.json",
    "extension/package.json",
    "n8n-nodes-tollgate/package.json",
    "packaging/tauri/package.json",
)
PACKAGERS = (
    "scripts/build_release.py",
    "scripts/make-dmg.sh",
    "scripts/check-release-license.py",
    "native/macos/scripts/build_app.py",
    "native/macos/build_candidate.py",
    ".github/workflows/desktop.yml",
    ".github/workflows/desktop-build.yml",
    "packaging/server/Dockerfile",
    "Dockerfile",
)


def detect_product(explicit: str | None) -> str:
    if explicit:
        key = explicit.lower()
        if key not in PRODUCTS:
            raise SystemExit(f"Unknown product {explicit!r}; expected {sorted(PRODUCTS)}")
        return key
    repo = os.environ.get("GITHUB_REPOSITORY", "").split("/")[-1]
    if repo in REPO_TO_PRODUCT:
        return REPO_TO_PRODUCT[repo]
    raise SystemExit("Pass --product KEY or set GITHUB_REPOSITORY")


def check_license_file(repo: Path, product_name: str) -> list[str]:
    path = repo / "LICENSE"
    if not path.is_file():
        return ["LICENSE fehlt"]
    text = path.read_text(encoding="utf-8")
    problems = []
    if not text.startswith(LICENSE_TITLE):
        problems.append(f"LICENSE: erste Zeile muss {LICENSE_TITLE} sein")
    if "DEUTSCH — maßgebliche Fassung" not in text:
        problems.append("LICENSE: deutsche Fassung fehlt")
    if "ENGLISH — translation" not in text:
        problems.append("LICENSE: englische Übersetzung fehlt")
    for foreign in FOREIGN:
        if foreign == product_name:
            continue
        if foreign in text:
            problems.append(f"LICENSE: fremder Produktname in der Historie: {foreign}")
    return problems


def check_readmes(repo: Path) -> list[str]:
    problems = []
    pages = [repo / "README.md"]
    de = repo / "README.de.md"
    if de.is_file():
        pages.append(de)
    if not pages[0].is_file():
        return ["README.md fehlt"]
    for page in pages:
        body = page.read_text(encoding="utf-8")
        if LICENSE_TITLE not in body:
            problems.append(f"{page.name}: Lizenzname fehlt")
        if "](LICENSE)" not in body:
            problems.append(f"{page.name}: Link auf LICENSE fehlt")
    return problems


def project_table(text: str) -> str:
    match = re.search(r"(?ms)^\[project\](.*?)(?=^\[|\Z)", text)
    return match.group(1) if match else ""


def check_pyproject(repo: Path) -> list[str]:
    path = repo / "pyproject.toml"
    if not path.is_file():
        return []
    section = project_table(path.read_text(encoding="utf-8"))
    if not section:
        return []
    as_string = re.search(r'(?m)^license\s*=\s*"([^"]+)"', section)
    as_file = re.search(r'(?m)^license\s*=\s*\{\s*file\s*=\s*"([^"]+)"', section)
    as_text = re.search(r'(?m)^license\s*=\s*\{\s*text\s*=\s*"([^"]+)"', section)
    if as_string:
        value = as_string.group(1)
        if value == ALLOWED_LICENSE_REF or LICENSE_TITLE in value:
            return []
        return [f"pyproject.toml: license {value!r} ist nicht Personal Use 1.0"]
    if as_file:
        if as_file.group(1) == "LICENSE":
            return []
        return [f"pyproject.toml: license.file muss LICENSE sein, nicht {as_file.group(1)}"]
    if as_text:
        value = as_text.group(1)
        if LICENSE_TITLE in value or value == ALLOWED_LICENSE_REF:
            return []
        return [f"pyproject.toml: license.text {value!r} ist nicht Personal Use 1.0"]
    return ["pyproject.toml: license-Feld fehlt"]


def package_json_files(repo: Path) -> list[Path]:
    paths = [repo / rel for rel in PACKAGE_JSON_FIXED if (repo / rel).is_file()]
    for path in sorted(repo.glob("packages/*/package.json")):
        if "node_modules" not in path.parts:
            paths.append(path)
    return paths


def check_package_json(repo: Path) -> list[str]:
    problems = []
    expected = (repo / "LICENSE").read_bytes() if (repo / "LICENSE").is_file() else None
    for path in package_json_files(repo):
        rel = path.relative_to(repo).as_posix()
        data = json.loads(path.read_text(encoding="utf-8"))
        license_field = data.get("license")
        if not isinstance(license_field, str) or not license_field.startswith(
            ("SEE LICENSE IN ", "LicenseRef-Netzwerkpunkt")
        ):
            problems.append(f"{rel}: license muss SEE LICENSE IN LICENSE sein")
            continue
        if license_field.startswith("SEE LICENSE IN "):
            target = (path.parent / license_field.removeprefix("SEE LICENSE IN ")).resolve()
            if expected is not None and (not target.is_file() or target.read_bytes() != expected):
                problems.append(f"{rel}: {target.name} stimmt nicht mit der Stamm-LICENSE überein")
    return problems


def check_tauri(repo: Path) -> list[str]:
    problems = []
    for conf in repo.glob("**/tauri.conf.json"):
        if "node_modules" in conf.parts:
            continue
        rel = conf.relative_to(repo).as_posix()
        bundle = json.loads(conf.read_text(encoding="utf-8")).get("bundle") or {}
        license_file = str(bundle.get("licenseFile") or "")
        license_id = str(bundle.get("license") or "")
        ok_file = license_file.endswith("LICENSE")
        ok_id = license_id == ALLOWED_LICENSE_REF or LICENSE_TITLE in license_id
        if not (ok_file or ok_id):
            problems.append(
                f"{rel}: bundle.licenseFile oder bundle.license muss Personal Use 1.0 sein"
            )
        cargo = conf.parent / "Cargo.toml"
        if cargo.is_file() and not re.search(
            r'(?m)^license-file\s*=\s*".*LICENSE"', cargo.read_text(encoding="utf-8")
        ):
            problems.append(
                f"{cargo.relative_to(repo).as_posix()}: license-file muss LICENSE nennen"
            )
    return problems


def check_packagers(repo: Path) -> list[str]:
    problems = []
    for rel in PACKAGERS:
        path = repo / rel
        if path.is_file() and "LICENSE" not in path.read_text(encoding="utf-8"):
            problems.append(f"{rel}: Installationsrezept muss LICENSE mit ausliefern")
    return problems


def run_checks(repo: Path, product: str) -> list[str]:
    name = PRODUCTS[product]
    problems = []
    problems.extend(check_license_file(repo, name))
    problems.extend(check_readmes(repo))
    problems.extend(check_pyproject(repo))
    problems.extend(check_package_json(repo))
    problems.extend(check_tauri(repo))
    problems.extend(check_packagers(repo))
    return problems


def self_test() -> None:
    import tempfile

    failed = []
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        (repo / "LICENSE").write_text(
            LICENSE_TITLE
            + "\nDEUTSCH — maßgebliche Fassung\n"
            + "ENGLISH — translation\nProbeTool-Fassungen\n",
            encoding="utf-8",
        )
        (repo / "README.md").write_text(
            f"## License\n**{LICENSE_TITLE}**\nSee [LICENSE](LICENSE).\n",
            encoding="utf-8",
        )
        (repo / "pyproject.toml").write_text(
            '[project]\nname = "probe"\nlicense = { file = "LICENSE" }\n',
            encoding="utf-8",
        )
        problems = run_checks(repo, "threaddesk")
        if problems:
            failed.append(f"happy: {problems}")
        (repo / "pyproject.toml").write_text(
            '[project]\nname = "probe"\nlicense = { text = "Proprietary" }\n',
            encoding="utf-8",
        )
        problems = run_checks(repo, "threaddesk")
        if not any("pyproject.toml" in p for p in problems):
            failed.append(f"proprietary: {problems}")
        (repo / "pyproject.toml").write_text(
            '[project]\nname = "probe"\nlicense = "MIT"\nlicense-files = ["LICENSE"]\n',
            encoding="utf-8",
        )
        problems = run_checks(repo, "threaddesk")
        if not any("MIT" in p for p in problems):
            failed.append(f"mit-string: {problems}")
        (repo / "pyproject.toml").write_text(
            '[project]\nname = "probe"\nlicense = { file = "LICENSE" }\n',
            encoding="utf-8",
        )
        nested = repo / "packages" / "crypto"
        nested.mkdir(parents=True)
        (nested / "package.json").write_text(
            '{"name":"probe-crypto","license":"MIT"}\n', encoding="utf-8"
        )
        problems = run_checks(repo, "threaddesk")
        if not any("packages/crypto/package.json" in p for p in problems):
            failed.append(f"workspace: {problems}")
        (nested / "package.json").unlink()
        tauri_dir = repo / "src-tauri"
        tauri_dir.mkdir()
        (tauri_dir / "tauri.conf.json").write_text(
            json.dumps(
                {
                    "bundle": {
                        "license": "MIT",
                        "resources": ["../LICENSE"],
                    }
                }
            ),
            encoding="utf-8",
        )
        problems = run_checks(repo, "threaddesk")
        if not any("tauri.conf.json" in p for p in problems):
            failed.append(f"tauri-mit: {problems}")
        (tauri_dir / "tauri.conf.json").write_text(
            json.dumps({"bundle": {"licenseFile": "../LICENSE"}}),
            encoding="utf-8",
        )
        (tauri_dir / "Cargo.toml").write_text(
            '[package]\nname = "probe"\nlicense-file = "../LICENSE"\n',
            encoding="utf-8",
        )
        problems = run_checks(repo, "threaddesk")
        extra = [p for p in problems if "tauri.conf.json" in p or "Cargo.toml" in p]
        if extra:
            failed.append(f"tauri-ok: {extra}")
        (tauri_dir / "tauri.conf.json").unlink()
        (tauri_dir / "Cargo.toml").unlink()
        (repo / "LICENSE").write_text(
            LICENSE_TITLE + "\nDEUTSCH — maßgebliche Fassung\nENGLISH — translation\n4AllPass\n",
            encoding="utf-8",
        )
        (repo / "pyproject.toml").write_text(
            '[project]\nname = "probe"\nlicense = { file = "LICENSE" }\n',
            encoding="utf-8",
        )
        problems = run_checks(repo, "threaddesk")
        if not any("4AllPass" in p for p in problems):
            failed.append(f"foreign: {problems}")
    if failed:
        raise SystemExit("Self-test failed:\n  " + "\n  ".join(failed))
    print(f"Self-test passed, tool {TOOL_VERSION}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--product", default="")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)
    if args.self_test:
        self_test()
        return 0
    product = detect_product(args.product or None)
    repo = Path(args.repo).resolve()
    problems = run_checks(repo, product)
    for line in problems:
        print("FEHLER", line)
    if problems:
        print(f"{len(problems)} Abweichung(en), tool {TOOL_VERSION}")
        return 1
    print(f"OK {PRODUCTS[product]}: LICENSE, README und Paketmetadaten, tool {TOOL_VERSION}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
