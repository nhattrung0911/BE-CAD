import sys
import types

import pytest

from app.cad.backends import get_cad_backend
from app.cad.registry import template_registry


def test_hex_nut_template_registered():
    template = template_registry.get_by_family("hex_nut")
    assert template.family == "hex_nut"


def test_hex_nut_registry_by_product_id():
    template = template_registry.get_by_product("hex-nut-iso4032")
    assert template.family == "hex_nut"


def test_lock_nut_registry_maps_to_hex_nut():
    template = template_registry.get_by_product("lock-nut-heavy-pattern")
    assert template.family == "hex_nut"


def test_mock_backend_generates_distinct_payloads_per_size():
    backend = get_cad_backend("mock")

    small = backend.generate(
        "hex-bolt-iso4014",
        {"d": 6, "L": 30, "P": 1, "k": 4, "s": 10, "b": 18},
        "glb",
        "preview",
    )
    large = backend.generate(
        "hex-bolt-iso4014",
        {"d": 12, "L": 50, "P": 1.75, "k": 7.5, "s": 19, "b": 30},
        "glb",
        "preview",
    )

    assert small.content != large.content


def test_mock_backend_generates_hex_nut_payload():
    backend = get_cad_backend("mock")

    result = backend.generate(
        "hex-nut-iso4032",
        {"d": 8, "s": 13.0, "m": 6.8},
        "glb",
        "preview",
    )

    assert b"hex_nut" in result.content
    assert result.metadata["template"] == "hex_nut"


def test_cadquery_backend_is_isolated_when_dependency_missing():
    try:
        import cadquery  # noqa: F401
    except ImportError:
        with pytest.raises(RuntimeError, match="requires cadquery"):
            get_cad_backend("cadquery")
    else:
        assert get_cad_backend("cadquery").name == "cadquery"


def test_cadquery_backend_exports_preview_glb_with_assembly_export(monkeypatch):
    exported_paths = []

    class FakeShape:
        def union(self, other):
            return self

        def translate(self, vector):
            return self

    class FakeWorkplane:
        def __init__(self, plane="XY"):
            self.plane = plane

        def circle(self, radius):
            return self

        def cutThruAll(self):
            return FakeShape()

        def close(self):
            return self

        def extrude(self, height):
            return FakeShape()

        def faces(self, selector):
            return self

        def chamfer(self, size):
            return FakeShape()

        def polygon(self, sides, diameter):
            return self

        def polyline(self, points):
            return self

        def workplane(self, offset=0):
            return self

    class FakeColor:
        def __init__(self, *args):
            self.args = args

    class FakeAssembly:
        def add(self, shape, color=None, name=None):
            self.shape = shape
            self.color = color
            self.name = name

        def export(self, path, tolerance=None, angularTolerance=None):
            exported_paths.append((path, tolerance, angularTolerance))
            with open(path, "wb") as handle:
                handle.write(b"glTF\x02\x00\x00\x00fake-binary-gltf")

    fake_cadquery = types.SimpleNamespace(
        Assembly=FakeAssembly,
        Color=FakeColor,
        Workplane=FakeWorkplane,
    )
    monkeypatch.setitem(sys.modules, "cadquery", fake_cadquery)

    backend = get_cad_backend("cadquery")
    generated = backend.generate(
        "hex-bolt-iso4014",
        {"d": 8, "L": 30, "P": 1.25, "k": 5.3, "s": 13, "b": 22},
        "glb",
        "preview",
    )

    assert generated.content.startswith(b"glTF")
    assert generated.metadata["generator"] == "cadquery"
    assert generated.metadata["exporter"] == "cadquery_assembly_glb"
    assert exported_paths[0][0].endswith(".glb")


def test_cadquery_backend_generates_real_preview_glb_when_installed():
    pytest.importorskip("cadquery")

    backend = get_cad_backend("cadquery")
    generated = backend.generate(
        "hex-bolt-iso4014",
        {"d": 8, "L": 30, "P": 1.25, "k": 5.3, "s": 13, "b": 22},
        "glb",
        "preview",
    )

    assert generated.content.startswith(b"glTF")
    assert len(generated.content) > 1000
    assert generated.metadata["exporter"] == "cadquery_assembly_glb"


def test_cadquery_backend_generates_real_hex_nut_preview_glb_when_installed():
    pytest.importorskip("cadquery")

    backend = get_cad_backend("cadquery")
    generated = backend.generate(
        "hex-nut-iso4032",
        {"d": 8, "s": 13.0, "m": 6.8},
        "glb",
        "preview",
    )

    assert generated.content.startswith(b"glTF")
    assert len(generated.content) > 1000
    assert generated.metadata["template"] == "hex_nut"
