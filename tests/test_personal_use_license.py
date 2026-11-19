"""Family license checker for GitHub CI and installation packages."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _tool():
    spec = importlib.util.spec_from_file_location(
        "check_personal_use_license", ROOT / "scripts/check_personal_use_license.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_self_test_and_this_repo():
    tool = _tool()
    assert tool.main(["--self-test"]) == 0
    assert tool.main(["--product", "tollgate", "--repo", str(ROOT)]) == 0


def test_a_valid_license_file_cannot_mask_a_conflicting_tauri_identifier(tmp_path):
    import json

    tool = _tool()
    conf = tmp_path / "src-tauri" / "tauri.conf.json"
    conf.parent.mkdir()
    conf.write_text(json.dumps({"bundle": {"license": "MIT", "licenseFile": "../LICENSE"}}))
    assert any("bundle.license" in p for p in tool.check_tauri(tmp_path))
    conf.write_text(json.dumps({"bundle": {"licenseFile": "../LICENSE"}}))
    assert not [p for p in tool.check_tauri(tmp_path) if "bundle" in p]


def test_repository_names_are_matched_case_insensitively(monkeypatch):
    tool = _tool()
    for name, product in (
        ("landjunge/ThreadDesk", "threaddesk"),
        ("landjunge/threaddesk", "threaddesk"),
        ("landjunge/AgentAuthority", "agent-authority"),
        ("landjunge/KiraBridge", "kirabridge"),
    ):
        monkeypatch.setenv("GITHUB_REPOSITORY", name)
        assert tool.detect_product(None) == product


def test_tauri_and_cargo_license_files_must_equal_the_root_license(tmp_path):
    import json

    tool = _tool()
    (tmp_path / "LICENSE").write_text("Netzwerkpunkt Personal Use License 1.0\n")
    app = tmp_path / "app" / "src-tauri"
    app.mkdir(parents=True)
    (app / "OTHER_LICENSE").write_text("MIT License\n")
    conf = app / "tauri.conf.json"
    cargo = app / "Cargo.toml"
    conf.write_text(json.dumps({"bundle": {"licenseFile": "OTHER_LICENSE"}}))
    cargo.write_text('license-file = "OTHER_LICENSE"\n')
    problems = tool.check_tauri(tmp_path)
    assert any("bundle.licenseFile stimmt nicht" in p for p in problems)
    assert any("Cargo.toml: license-file stimmt nicht" in p for p in problems)
    (app / "LICENSE").write_text("Netzwerkpunkt Personal Use License 1.0\n")
    conf.write_text(json.dumps({"bundle": {"licenseFile": "LICENSE"}}))
    cargo.write_text('license-file = "LICENSE"\n')
    assert not tool.check_tauri(tmp_path)


def test_npm_license_reference_must_be_exact(tmp_path):
    import json

    tool = _tool()
    (tmp_path / "LICENSE").write_text("Netzwerkpunkt Personal Use License 1.0\n")
    manifest = tmp_path / "package.json"
    for value, accepted in (
        (tool.ALLOWED_LICENSE_REF, True),
        ("LicenseRef-Netzwerkpunkt-Commercial-Only-2.0", False),
        (tool.ALLOWED_LICENSE_REF + "-changed", False),
    ):
        manifest.write_text(json.dumps({"name": "x", "license": value}))
        assert (not tool.check_package_json(tmp_path)) is accepted, value


def test_packaging_proofs_are_concrete_and_ignore_comments(tmp_path):
    tool = _tool()
    for relative, proofs in tool.PACKAGER_PROOFS.items():
        original = ROOT / relative
        text = original.read_text(encoding="utf-8")
        recipe = tmp_path / relative
        recipe.parent.mkdir(parents=True, exist_ok=True)
        recipe.write_text(text, encoding="utf-8")
        assert not tool.check_packagers(tmp_path), relative
        for proof in proofs:
            removed = text.replace(proof, "REMOVED_PRODUCT_INCLUSION")
            recipe.write_text(removed, encoding="utf-8")
            assert tool.check_packagers(tmp_path), (relative, proof)
            commented = "\n".join(
                "# " + line if proof in line else line for line in text.splitlines()
            )
            recipe.write_text(commented, encoding="utf-8")
            assert tool.check_packagers(tmp_path), (relative, proof, "commented")
        recipe.write_text(text, encoding="utf-8")
