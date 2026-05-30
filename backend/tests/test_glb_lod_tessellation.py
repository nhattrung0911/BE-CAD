"""Integration: LOD must actually change GLB mesh density, and STEP/STL stay valid.

Requires a real cadquery/OCC install (skipped otherwise). Complements the pure
unit tests in test_tessellation.py.
"""

import json
import struct

import pytest

from app.cad.backends import get_cad_backend

pytest.importorskip("cadquery")

BUTTON = ("button-head-iso7380", {"d": 3, "L": 6, "P": 0.5, "dk": 5.7, "k": 1.65, "s": 2.0, "t": 1.04})


def _glb_triangle_count(data: bytes) -> int:
    assert data[:4] == b"glTF", "not a GLB"
    jlen = struct.unpack("<I", data[12:16])[0]
    gltf = json.loads(data[20 : 20 + jlen])
    tris = 0
    for mesh in gltf.get("meshes", []):
        for prim in mesh["primitives"]:
            acc = gltf["accessors"][prim["indices"]]
            tris += acc["count"] // 3
    return tris


def _glb_bbox(data: bytes):
    jlen = struct.unpack("<I", data[12:16])[0]
    gltf = json.loads(data[20 : 20 + jlen])
    lo = [1e9, 1e9, 1e9]
    hi = [-1e9, -1e9, -1e9]
    for acc in gltf.get("accessors", []):
        if acc.get("type") == "VEC3" and acc.get("componentType") == 5126 and "min" in acc:
            for i in range(3):
                lo[i] = min(lo[i], acc["min"][i])
                hi[i] = max(hi[i], acc["max"][i])
    return [hi[i] - lo[i] for i in range(3)]


def _gen(fmt, lod=None):
    backend = get_cad_backend("cadquery")
    pid, params = BUTTON
    p = dict(params)
    if lod is not None:
        p["lod"] = lod
    return backend.generate(pid, p, fmt, "preview").content


def test_higher_lod_produces_more_triangles():
    low = _glb_triangle_count(_gen("glb", "low"))
    medium = _glb_triangle_count(_gen("glb", "medium"))
    high = _glb_triangle_count(_gen("glb", "high"))
    assert low < medium < high, (low, medium, high)


def test_all_lods_share_the_same_geometry_bbox():
    # Different smoothness, same actual part dimensions.
    b_low = _glb_bbox(_gen("glb", "low"))
    b_high = _glb_bbox(_gen("glb", "high"))
    for i in range(3):
        assert b_low[i] == pytest.approx(b_high[i], abs=0.25)


def test_step_export_is_a_valid_solid():
    data = _gen("step")
    assert len(data) > 1000
    head = data[:200].decode("ascii", errors="ignore")
    assert "ISO-10303" in head


def test_stl_export_is_nonempty_binary_or_ascii():
    data = _gen("stl")
    assert len(data) > 200  # has real triangle data
