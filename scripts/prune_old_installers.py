#!/usr/bin/env python3
"""Keep only the current shipping installers on GitHub Releases.

Each product offers one current desktop line (newest published unprefixed
release with installer files). KiraBridge also keeps its newest ``linux-*``
Debian Remote line. ``windows-*`` is unused and never kept. Older installer
binaries are deleted. Git tags, release notes, LICENSE files, checksums and
third-party notices stay.

Drafts never count as the current line. Prereleases count, because 4AllPass
and KiraBridge currently ship that way. GitHub ``prerelease=false`` is not
the filter.

Shared identical copy for 4AllPass, ThreadDesk, KiraBridge, TollGate and
Agent Authority (see TOOL_VERSION).

Usage:
  prune_old_installers.py              dry-run (print keep/delete, change nothing)
  prune_old_installers.py --apply      delete listed installer assets
  prune_old_installers.py --self-test  check the keep/delete rules, no network
Environment: GITHUB_REPOSITORY (owner/name) and GITHUB_TOKEN or GH_TOKEN.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

TOOL_VERSION = "1.0.1"
API = "https://api.github.com"
USER_AGENT = "newest-stable-downloads"

# Same installer extensions as update_readme_downloads.py, plus wheels and
# install-*.sh which are installation files but never README buttons.
INSTALLER = re.compile(
    r"(?:install-.*\.sh$|\.(?:dmg|pkg|exe|msi|appimage|deb|rpm|apk|whl|zip|tar\.gz)$)",
    re.IGNORECASE,
)
EVIDENCE = re.compile(
    r"(?:^LICENSE(?:\.[A-Za-z0-9]+)?$|checksum|sha256|sha512|sbom|"
    r"third-party-notices|(?:^|[^A-Za-z])notices|\.sig$|\.asc$)",
    re.IGNORECASE,
)
# Matches the README updater's NOT_PACKAGE names so a source/debug archive
# cannot become the shipping line and wipe the previous desktop installers.
NOT_SHIPPING = re.compile(
    r"(?:checksum|sha256|sha512|sbom|manifest|symbols|debug|notices|evidence|"
    r"source|\.sig$|\.asc$|\.whl$|-review|build-only|historical-)",
    re.IGNORECASE,
)
PIN_DOWNLOAD = re.compile(
    r"gh\s+release\s+download\s+([^\s]+)",
    re.IGNORECASE,
)
PIN_CHANNEL = re.compile(
    r"""(?:FOURALLPASS_RELEASE:-|CHANNEL=\{?\$\{[^}]+:-|else\s*\{\s*")(v?[0-9][^"'\s}]+)""",
)


def lane(tag: str):
    """desktop = unprefixed; remote = linux-*; windows-* is unused."""
    name = (tag or "").lower()
    if name.startswith("linux-"):
        return "remote"
    if name.startswith("windows-"):
        return None
    return "desktop"


def published(releases):
    return sorted(
        (r for r in releases if not r.get("draft") and r.get("published_at")),
        key=lambda r: r["published_at"],
        reverse=True,
    )


def is_installer(name: str) -> bool:
    if not name or EVIDENCE.search(name):
        return False
    if name.lower().endswith(".whl"):
        return True
    if NOT_SHIPPING.search(name):
        return False
    return bool(INSTALLER.search(name))


def is_shipping_asset(asset) -> bool:
    """True when this asset may select the current shipping release."""
    name = asset.get("name") or ""
    if asset.get("state") not in (None, "uploaded"):
        return False
    if not asset.get("size"):
        return False
    if not name or EVIDENCE.search(name) or NOT_SHIPPING.search(name):
        return False
    return bool(INSTALLER.search(name))


def has_shipping_installer(release) -> bool:
    return any(is_shipping_asset(a) for a in release.get("assets") or [])


def newest_kept(releases):
    """Newest published release per lane with a finished shipping installer."""
    kept = {}
    for release in published(releases):
        wanted = lane(release.get("tag_name") or "")
        if wanted is None or wanted in kept:
            continue
        if not has_shipping_installer(release):
            continue
        kept[wanted] = release
        if "desktop" in kept and "remote" in kept:
            break
    return kept


def pinned_tags(root="."):
    """Tags still named by install scripts or workflow fixture downloads."""
    tags = set()
    root = Path(root)
    paths = list(root.glob("scripts/install.*")) + list(root.glob(".github/workflows/*.yml"))
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for match in PIN_DOWNLOAD.finditer(text):
            tag = match.group(1).strip("\"'")
            if tag and not tag.startswith("-") and not tag.startswith("$"):
                tags.add(tag)
        for match in PIN_CHANNEL.finditer(text):
            tags.add(match.group(1))
    return tags


def plan(releases, extra_keep_tags=()):
    kept = newest_kept(releases)
    keep_tags = {r["tag_name"] for r in kept.values()}
    keep_tags.update(extra_keep_tags)
    delete = []
    keep_installers = []
    evidence = []
    for release in releases:
        tag = release.get("tag_name") or ""
        for asset in release.get("assets") or []:
            name = asset.get("name") or ""
            row = {
                "tag": tag,
                "id": asset.get("id"),
                "name": name,
                "size": asset.get("size"),
                "draft": bool(release.get("draft")),
            }
            if is_installer(name):
                if tag in keep_tags:
                    keep_installers.append(row)
                else:
                    delete.append(row)
            else:
                evidence.append(row)
    return {
        "keep_tags": sorted(keep_tags),
        "lanes": {lane_name: rel["tag_name"] for lane_name, rel in kept.items()},
        "keep_installers": keep_installers,
        "delete": delete,
        "evidence": evidence,
    }


def _token():
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        raise SystemExit("GITHUB_TOKEN or GH_TOKEN is required")
    return token


def _repo():
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo or "/" not in repo:
        raise SystemExit("GITHUB_REPOSITORY (owner/name) is required")
    return repo


def api(method: str, path: str, ok=(200, 204)):
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {_token()}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": USER_AGENT,
    }
    last_error = None
    for attempt in range(3):
        try:
            request = urllib.request.Request(API + path, method=method, headers=headers)
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read()
                if not raw:
                    return None
                return json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as error:
            if error.code in ok:
                return None
            last_error = error
            if error.code in {429, 500, 502, 503, 504} and attempt < 2:
                time.sleep(2 * (attempt + 1))
                continue
            body = error.read().decode("utf-8", "replace")[:400]
            raise SystemExit(f"{method} {path} failed: HTTP {error.code} {body}") from error
        except (urllib.error.URLError, TimeoutError) as error:
            last_error = error
            if attempt < 2:
                time.sleep(2 * (attempt + 1))
                continue
            raise SystemExit(f"{method} {path} failed: {error}") from error
    raise SystemExit(f"{method} {path} failed: {last_error}")


def all_releases(repo: str):
    items = []
    page = 1
    while True:
        chunk = api("GET", f"/repos/{repo}/releases?per_page=100&page={page}") or []
        if not isinstance(chunk, list):
            raise SystemExit(f"unexpected releases payload for {repo}")
        items.extend(chunk)
        if len(chunk) < 100:
            break
        page += 1
    return items


def self_test():
    failed = []
    desktop_new = {
        "tag_name": "v0.1.2-rc.3",
        "draft": False,
        "published_at": "2026-11-11T21:25:26Z",
        "assets": [
            {"id": 1, "name": "4AllPass_0.1.2-rc.3_x64.dmg", "size": 10},
            {"id": 2, "name": "LICENSE", "size": 20},
            {"id": 3, "name": "SHA256SUMS", "size": 30},
            {"id": 4, "name": "third-party-notices-macOS.zip", "size": 40},
            {"id": 5, "name": "4AllPass_0.1.2-rc.3_x64.dmg.sha256", "size": 50},
        ],
    }
    desktop_old = {
        "tag_name": "v0.1.2-rc.2",
        "draft": False,
        "published_at": "2026-10-18T16:13:48Z",
        "assets": [
            {"id": 11, "name": "4AllPass_0.1.2-rc.2_x64.dmg", "size": 10},
            {"id": 12, "name": "LICENSE", "size": 20},
            {"id": 13, "name": "SHA256SUMS", "size": 30},
            {"id": 14, "name": "third-party-notices-macOS.zip", "size": 40},
        ],
    }
    linux_new = {
        "tag_name": "linux-v0.8.0rc41",
        "draft": False,
        "published_at": "2026-11-07T12:00:00Z",
        "assets": [
            {"id": 21, "name": "KiraBridge-0.8.0rc41-Linux-x86_64.tar.gz", "size": 10},
            {"id": 22, "name": "LICENSE", "size": 20},
            {"id": 23, "name": "SHA256SUMS", "size": 30},
        ],
    }
    linux_old = {
        "tag_name": "linux-v0.8.0rc40",
        "draft": False,
        "published_at": "2026-11-01T12:00:00Z",
        "assets": [
            {"id": 31, "name": "KiraBridge-0.8.0rc40-Linux-x86_64.tar.gz", "size": 10},
            {"id": 32, "name": "LICENSE", "size": 20},
        ],
    }
    windows = {
        "tag_name": "windows-v0.8.0rc37.dev1",
        "draft": False,
        "published_at": "2026-11-05T12:00:00Z",
        "assets": [
            {"id": 41, "name": "KiraBridge-0.8.0rc37.dev1-x64-setup.exe", "size": 10},
            {"id": 42, "name": "LICENSE", "size": 20},
        ],
    }
    draft = {
        "tag_name": "v0.8.0rc17",
        "draft": True,
        "published_at": None,
        "assets": [
            {"id": 51, "name": "KiraBridge-macos.tar.gz", "size": 10},
            {"id": 52, "name": "LICENSE", "size": 20},
        ],
    }
    wheel_old = {
        "tag_name": "v0.8.0rc14",
        "draft": False,
        "published_at": "2026-10-22T20:54:20Z",
        "assets": [
            {"id": 61, "name": "kirabridge-0.8.0rc14-py3-none-any.whl", "size": 10},
        ],
    }
    source_only = {
        "tag_name": "announce-public",
        "draft": False,
        "published_at": "2026-08-11T21:11:53Z",
        "assets": [],
    }
    source_newer = {
        "tag_name": "v0.3.0",
        "draft": False,
        "published_at": "2026-11-12T00:00:00Z",
        "assets": [
            {"id": 71, "name": "ThreadDesk-source.tar.gz", "size": 10, "state": "uploaded"},
        ],
    }
    incomplete = {
        "tag_name": "v0.3.1",
        "draft": False,
        "published_at": "2026-11-13T00:00:00Z",
        "assets": [
            {"id": 81, "name": "ThreadDesk-macOS.dmg", "size": 0, "state": "starter"},
        ],
    }

    cases = [
        (
            "4AllPass keeps newest desktop installers",
            [desktop_new, desktop_old],
            ["v0.1.2-rc.3"],
            [11],
            [1],
            (),
        ),
        (
            "KiraBridge keeps desktop plus linux independently",
            [desktop_new, linux_new, linux_old, windows, draft, wheel_old],
            ["linux-v0.8.0rc41", "v0.1.2-rc.3"],
            [31, 41, 51, 61],
            [1, 21],
            (),
        ),
        (
            "source-only repo deletes nothing",
            [source_only],
            [],
            [],
            [],
            (),
        ),
        (
            "source archive does not displace desktop installers",
            [source_newer, desktop_new, desktop_old],
            ["v0.1.2-rc.3"],
            [11],
            [1],
            (),
        ),
        (
            "incomplete upload does not displace desktop installers",
            [incomplete, desktop_new, desktop_old],
            ["v0.1.2-rc.3"],
            [81, 11],
            [1],
            (),
        ),
        (
            "workflow fixture tag keeps its wheel",
            [desktop_new, wheel_old],
            ["v0.1.2-rc.3", "v0.8.0rc14"],
            [],
            [1, 61],
            ("v0.8.0rc14",),
        ),
    ]
    for title, releases, keep_tags, delete_ids, keep_ids, extra in cases:
        result = plan(releases, extra_keep_tags=extra)
        if result["keep_tags"] != keep_tags:
            failed.append(f"{title}: keep_tags {result['keep_tags']} != {keep_tags}")
        got_delete = [row["id"] for row in result["delete"]]
        if got_delete != delete_ids:
            failed.append(f"{title}: delete {got_delete} != {delete_ids}")
        got_keep = [row["id"] for row in result["keep_installers"]]
        if got_keep != keep_ids:
            failed.append(f"{title}: keep_installers {got_keep} != {keep_ids}")
        evidence_names = {row["name"] for row in result["evidence"]}
        if (
            "LICENSE" in {a["name"] for r in releases for a in r["assets"]}
            and "LICENSE" not in evidence_names
        ):
            failed.append(f"{title}: LICENSE was not kept as evidence")
        if any(row["name"] == "third-party-notices-macOS.zip" for row in result["delete"]):
            failed.append(f"{title}: notices zip was listed for delete")

    if is_installer("LICENSE") or is_installer("SHA256SUMS") or is_installer("foo.dmg.sha256"):
        failed.append("evidence files classified as installers")
    if not is_installer("install-macos.sh") or not is_installer("app.whl"):
        failed.append("install-macos.sh or wheel not classified as installer")
    if is_installer("ThreadDesk-source.tar.gz") or is_shipping_asset(
        {"name": "ThreadDesk-source.tar.gz", "size": 10, "state": "uploaded"}
    ):
        failed.append("source archive classified as shipping installer")
    if is_shipping_asset({"name": "App.dmg", "size": 0, "state": "starter"}):
        failed.append("empty starter upload classified as shipping")
    if (
        lane("linux-v0.8.0rc41") != "remote"
        or lane("windows-v1") is not None
        or lane("v0.2.0") != "desktop"
    ):
        failed.append("lane() mismatch")

    if failed:
        raise SystemExit("self-test failed:\n- " + "\n- ".join(failed))
    print(f"Self-test passed ({TOOL_VERSION}).")


def report(result, repo: str):
    print(f"repo={repo} tool={TOOL_VERSION}")
    print("keep_tags=" + ",".join(result["keep_tags"] or ["(none)"]))
    print("lanes=" + json.dumps(result["lanes"], sort_keys=True))
    print(f"keep_installers={len(result['keep_installers'])}")
    for row in result["keep_installers"]:
        print(f"  KEEP {row['tag']} {row['name']}")
    print(f"delete={len(result['delete'])}")
    for row in result["delete"]:
        draft = " draft" if row["draft"] else ""
        print(f"  DEL{draft} {row['tag']} {row['id']} {row['name']}")
    print(f"evidence_kept={len(result['evidence'])}")


def apply(repo: str, result):
    deleted = 0
    for row in result["delete"]:
        asset_id = row["id"]
        if not asset_id:
            raise SystemExit(f"missing asset id for {row}")
        api("DELETE", f"/repos/{repo}/releases/assets/{asset_id}", ok=(204, 404))
        deleted += 1
        print(f"deleted {row['tag']} {row['name']}")
        time.sleep(0.25)
    print(f"deleted_count={deleted}")
    return deleted


def main(argv):
    args = argv[1:]
    if "--self-test" in args:
        self_test()
        return 0
    apply_changes = "--apply" in args
    repo = _repo()
    extra = pinned_tags()
    result = plan(all_releases(repo), extra_keep_tags=extra)
    report(result, repo)
    if extra:
        print("pinned_tags=" + ",".join(sorted(extra)))
    if not apply_changes:
        print("dry-run: nothing deleted (pass --apply to delete older installers)")
        return 0
    apply(repo, result)
    verify = plan(all_releases(repo), extra_keep_tags=extra)
    leftover = verify["delete"]
    if leftover:
        names = ", ".join(f"{row['tag']}/{row['name']}" for row in leftover[:8])
        raise SystemExit(f"assets still listed for delete after apply: {names}")
    print("verify_ok keep_tags=" + ",".join(verify["keep_tags"] or ["(none)"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
