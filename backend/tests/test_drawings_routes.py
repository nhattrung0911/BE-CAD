import xml.dom.minidom

import pytest
from fastapi.testclient import TestClient

from app.main import app

pytest.importorskip("cadquery")

client = TestClient(app)


def test_2d_svg_returns_wellformed_drawing_for_a_bolt():
    resp = client.get("/api/v1/drawings/hex-bolt-iso4014-m8x30/2d.svg")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/svg+xml")
    body = resp.text
    assert body.startswith("<svg")
    # parses as XML
    xml.dom.minidom.parseString(body)
    # has real projected geometry
    assert "<polyline" in body
    assert "viewBox=" in body


def test_2d_svg_supports_named_views():
    for view in ("front", "top", "right"):
        resp = client.get(f"/api/v1/drawings/hex-nut-iso4032-m8/2d.svg?view={view}")
        assert resp.status_code == 200, (view, resp.status_code)
        assert resp.text.startswith("<svg")


def test_2d_svg_rejects_unknown_view():
    resp = client.get("/api/v1/drawings/hex-nut-iso4032-m8/2d.svg?view=isometric")
    assert resp.status_code == 400


def test_2d_svg_404_for_unknown_variant():
    resp = client.get("/api/v1/drawings/does-not-exist/2d.svg")
    assert resp.status_code == 404
