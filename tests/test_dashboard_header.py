import base64
import re
from pathlib import Path

from fastapi.testclient import TestClient

from tollgate import dashboard_html
from tollgate.server_v1 import app

client = TestClient(app)


def test_dashboard_has_shared_header_and_brand():
    html = client.get("/dashboard").text
    assert "data-product-header" in html
    assert "/static/np/networkpunkt-appbar.css" in html
    assert "--brand: #e77745" in html


def test_static_header_assets_whitelist():
    assert client.get("/static/np/networkpunkt-appbar.js").status_code == 200
    assert client.get("/static/np/np-appbar-tollgate-dark-256.png").headers["content-type"] == "image/png"
    assert client.get("/static/np/np-appbar-4allpass-dark-256.png").status_code == 200
    assert client.get("/static/np/..%2Fserver_v1.py").status_code == 404
    assert client.get("/static/np/secret.txt").status_code == 404


def test_dashboard_header_is_three_zone_64px_with_original_wordmark():
    html = client.get("/dashboard").text
    assert "grid-template-columns: minmax(190px, 1fr) auto minmax(190px, 1fr)" in html
    assert "height: 64px" in html
    assert '<div class="np-appbar-host" data-product-header></div>' in html
    assert '<details class="header-more" id="headerMore">' in html
    assert 'aria-label="More tools"' in html
    assert 'alt="TOLLGATE"' in html
    german = dashboard_html.dashboard_html("de")
    assert 'aria-label="Weitere Werkzeuge"' in german
    assert 'alt="TOLLGATE"' in german
    match = re.search(
        r'class="brand-mark".*?src="data:image/svg\+xml;base64,([^"]+)"', html
    )
    assert match, "original wordmark data URI missing"
    svg = base64.b64decode(match.group(1)).decode("utf-8")
    assert '<tspan fill="#ffffff">Toll</tspan>' in svg
    assert '<tspan fill="#e77745">Gate</tspan>' in svg
    assert "currentColor" not in svg
    # The data URI is the unchanged original asset, byte for byte.
    original = Path(__file__).resolve().parents[1] / "assets/design/wordmarks/TollGate-dark.svg"
    assert base64.b64decode(match.group(1)) == original.read_bytes()


def test_dashboard_cards_use_neutral_contours_not_brand_frames():
    html = client.get("/dashboard").text
    assert ".card, .auth-bar, .lang-switch { border-color: var(--line); }" in html
    assert ".card, .auth-bar, .badge, .lang-switch { border-color: var(--brand); }" not in html
    assert ".card, .auth-bar, .badge, .lang-switch" not in html


def test_secondary_header_tools_live_behind_the_plus_disclosure():
    html = client.get("/dashboard").text
    header = html.split("<header>", 1)[1].split("</header>", 1)[0]
    assert 'id="headerMore"' in header
    assert 'id="btnSetup"' in header and 'id="apiKey"' in header
    assert header.index('id="headerMore"') < header.index('id="btnSetup"')
    assert "data-product-header" in header
    # The appbar host is the centre zone, not nested inside the tools area.
    assert '<div class="np-appbar-host" data-product-header></div>' in header
