#!/usr/bin/env python3
"""Refresh verified installer slots in both READMEs; keep source downloads separate."""
import json
import os
import re
import urllib.request
from html import escape
from pathlib import Path

START = "<!-- AUTO-DOWNLOADS:START -->"
END = "<!-- AUTO-DOWNLOADS:END -->"
SLOTS = [("macos-apple-silicon", "macOS Apple Silicon"), ("macos-intel", "macOS Intel"), ("windows", "Windows"), ("linux-desktop", "Linux Desktop"), ("debian-server", "Debian Server")]

def classify(name):
    n = name.lower()
    if any(x in n for x in ("source", "checksum", "sha256", "debug", "symbols", "sbom", "manifest")):
        return []
    if n.endswith((".dmg", ".pkg")):
        if "universal" in n:
            return ["macos-apple-silicon", "macos-intel"]
        return ["macos-apple-silicon" if re.search(r"(arm64|aarch64|apple.?silicon)", n) else "macos-intel"]
    if n.endswith((".exe", ".msi")) and re.search(r"(win|setup)", n):
        return ["windows"]
    if n.endswith((".appimage", ".deb", ".rpm")):
        return ["debian-server" if "server" in n else "linux-desktop"]
    return []

def select(releases):
    found = {}
    for release in sorted((r for r in releases if not r.get("draft") and r.get("published_at")), key=lambda r: r["published_at"], reverse=True):
        for asset in release.get("assets", []):
            if asset.get("state") != "uploaded" or not asset.get("size") or not asset.get("browser_download_url"):
                continue
            for key in classify(asset["name"]):
                found.setdefault(key, (release["tag_name"], asset["browser_download_url"]))
    return found

def render(found, repo, branch):
    items = []
    for key, label in SLOTS:
        path = "assets/readme/download-" + key + ".svg"
        if key in found:
            version, url = found[key]
            items.append('<a href="' + escape(url, quote=True) + '" title="' + escape(label + " " + version, quote=True) + '"><img src="' + path + '" alt="Download ' + escape(label) + '" width="190" height="52"></a>')
        else:
            items.append('<img src="' + path + '" alt="' + escape(label) + ': In Vorbereitung / Coming soon" width="190" height="52">')
    source = "https://github.com/" + repo + "/archive/refs/heads/" + branch + ".zip"
    return '<p align="center">\n  ' + '\n  &nbsp;\n  '.join(items) + '\n</p>\n<p align="center"><a href="' + source + '">Quellcode herunterladen / Download source ZIP</a></p>'

def main():
    repo = os.environ["GITHUB_REPOSITORY"]
    branch = os.environ.get("SOURCE_BRANCH", "main")
    token = os.environ.get("GITHUB_TOKEN", "")
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "installer-readme-refresh"}
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request("https://api.github.com/repos/" + repo + "/releases?per_page=100", headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        releases = json.load(response)
    found = select(releases)
    block = render(found, repo, branch)
    for page in (Path("README.md"), Path("README.de.md")):
        original = page.read_text(encoding="utf-8")
        if original.count(START) != 1 or original.count(END) != 1:
            raise SystemExit("Missing or duplicate download markers: " + str(page))
        head, tail = original.split(START, 1)
        remainder = tail.split(END, 1)[1]
        updated = head + START + "\n" + block + "\n" + END + remainder
        if updated != original:
            page.write_text(updated, encoding="utf-8")
    print("Updated download sections in both READMEs; verified asset metadata for", len(found), "platforms")

if __name__ == "__main__":
    main()
