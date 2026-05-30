"""Geometry-orientation guard for the ISO 7380 button head.

CadQuery is not installed in this test environment, so we cannot render a real
GLB and inspect its bounding box here. Instead we instrument a fake `cadquery`
module (same technique as test_cad_backends.py) and assert the *build logic*
produces a correctly oriented screw:

  - the shank is built from the base (z_start == 0) spanning the full length L,
    NOT offset upward by the head height;
  - the head is created ABOVE the shank (workplane offset == L);
  - a hexagon socket is cut into the head's free top face (polygon(6) + a
    negative-depth cutBlind).

The previous implementation attached the shank on the SAME top face the socket
was cut into, burying the socket under the shank — this guard locks that out.
"""

import sys
import types

from app.cad.backends import get_cad_backend, reset_cad_backend_cache


class _Recorder:
    def __init__(self):
        self.offsets = []
        self.polygons = []
        self.cuts = []
        self.extrudes = []
        self.faces = []


def _make_fake_cadquery(rec: _Recorder):
    class FakeWP:
        def __init__(self, plane="XY"):
            self.plane = plane

        def workplane(self, offset=0, **kwargs):
            rec.offsets.append(offset)
            return self

        def circle(self, radius):
            return self

        def polygon(self, sides, diameter):
            rec.polygons.append((sides, diameter))
            return self

        def extrude(self, height):
            rec.extrudes.append(height)
            return self

        def faces(self, selector):
            rec.faces.append(selector)
            return self

        def edges(self, selector=None):
            return self

        def fillet(self, radius):
            return self

        def chamfer(self, radius):
            return self

        def cutBlind(self, depth):
            rec.cuts.append(depth)
            return self

        def cutThruAll(self):
            return self

        def union(self, other):
            return self

        def translate(self, vector):
            return self

        def close(self):
            return self

        def polyline(self, points):
            return self

        def revolve(self, *args, **kwargs):
            return self

    return types.SimpleNamespace(
        Workplane=FakeWP,
        Color=lambda *a, **k: None,
        Assembly=object,
    )


M3_PARAMS = {"d": 3, "L": 6, "P": 0.5, "dk": 5.7, "k": 1.65, "s": 2.0, "t": 1.04}


def test_button_head_shank_starts_at_base_and_socket_on_free_top(monkeypatch):
    rec = _Recorder()
    monkeypatch.setitem(sys.modules, "cadquery", _make_fake_cadquery(rec))
    reset_cad_backend_cache()
    backend = get_cad_backend("cadquery")

    captured = {}

    def spy_shank(**kwargs):
        captured.update(kwargs)
        return backend.cq.Workplane("XY").circle(1).extrude(kwargs["length"])

    monkeypatch.setattr(backend, "_build_threaded_shank", spy_shank)

    backend._button_head(M3_PARAMS)

    # Shank spans the whole length, anchored at the base — head height must NOT
    # be folded into z_start (that was the inversion bug).
    assert captured["z_start"] == 0.0, captured
    assert captured["length"] == 6

    # Head is created above the shank: a workplane offset equal to L.
    assert 6 in rec.offsets, rec.offsets

    # Hexagon socket is cut into a free face (polygon(6) + negative cutBlind).
    assert any(sides == 6 for sides, _ in rec.polygons), rec.polygons
    assert any(depth < 0 for depth in rec.cuts), rec.cuts
