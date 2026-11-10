from fastapi.testclient import TestClient

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
