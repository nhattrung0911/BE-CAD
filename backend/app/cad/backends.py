import math
import tempfile
from pathlib import Path
from typing import Any

from app.cad.registry import template_registry
from app.cad.template_base import GeneratedModel


class CadBackend:
    name = "base"

    def generate(self, product_id: str, params: dict[str, Any], fmt: str, quality: str) -> GeneratedModel:
        raise NotImplementedError


class MockCadBackend(CadBackend):
    name = "mock"

    def generate(self, product_id: str, params: dict[str, Any], fmt: str, quality: str) -> GeneratedModel:
        template = template_registry.get_by_product(product_id)
        return template.generate(params, fmt, quality)


class CadQueryBackend(CadBackend):
    name = "cadquery"

    def __init__(self) -> None:
        try:
            import cadquery as cq
        except ImportError as exc:
            raise RuntimeError("CAD_BACKEND=cadquery requires cadquery to be installed") from exc
        self.cq = cq

    def generate(self, product_id: str, params: dict[str, Any], fmt: str, quality: str) -> GeneratedModel:
        family = template_registry.get_by_product(product_id).family
        if family == "hex_bolt":
            shape = self._hex_bolt(params)
        elif family == "hex_nut":
            shape = self._hex_nut(params)
        elif family == "washer":
            shape = self._washer(params)
        elif family == "retaining_ring":
            shape = self._retaining_ring(params)
        else:
            raise KeyError(f"No CadQuery generator for family={family}")
        content, export_metadata = self._export(shape, fmt, family, params, quality)
        return GeneratedModel(
            content=content,
            format=fmt,
            metadata={"generator": self.name, "template": family, "params": params, **export_metadata},
        )

    def _washer(self, params: dict[str, Any]):
        for key in ["OD", "ID", "h"]:
            if key not in params:
                raise ValueError(f"Missing required params: ['{key}']")
        return (
            self.cq.Workplane("XY")
            .circle(float(params["OD"]) / 2)
            .circle(float(params["ID"]) / 2)
            .extrude(float(params["h"]))
        )

    def _retaining_ring(self, params: dict[str, Any]):
        for key in ["OD", "d1", "h"]:
            if key not in params:
                raise ValueError(f"Missing required params: ['{key}']")
        od = float(params["OD"])
        inner = float(params["d1"])
        gap_angle = math.radians(24)
        outer_pts = []
        inner_pts = []
        for i in range(48):
            angle = gap_angle / 2 + (2 * math.pi - gap_angle) * i / 47
            outer_pts.append((math.cos(angle) * od / 2, math.sin(angle) * od / 2))
            inner_pts.append((math.cos(angle) * inner / 2, math.sin(angle) * inner / 2))
        return self.cq.Workplane("XY").polyline(outer_pts).polyline(list(reversed(inner_pts))).close().extrude(float(params["h"]))

    def _hex_bolt(self, params: dict[str, Any]):
        for key in ["d", "L", "P", "k", "s", "b"]:
            if key not in params:
                raise ValueError(f"Missing required params for hex_bolt: {key!r}")
        d = float(params["d"])
        total_length = float(params["L"])
        head_height = float(params["k"])
        across_flats = float(params["s"])
        thread_length = float(params["b"])
        pitch = float(params["P"])
        shank_radius = d / 2
        circumradius = across_flats / math.sqrt(3)
        grip_length = max(total_length - thread_length, 0.0)
        minor_radius = max(shank_radius - 0.6134 * pitch, shank_radius * 0.75)

        head = self.cq.Workplane("XY").polygon(6, circumradius * 2).extrude(head_height)
        try:
            head = head.faces(">Z").chamfer(min(1.0, head_height * 0.12))
            head = head.faces("<Z").chamfer(min(0.5, head_height * 0.08))
        except Exception:
            pass

        bolt = head
        if grip_length > 0:
            grip = (
                self.cq.Workplane("XY")
                .workplane(offset=head_height)
                .circle(shank_radius)
                .extrude(grip_length)
            )
            bolt = bolt.union(grip)

        thread_start = head_height + grip_length
        if thread_length > 0:
            thread_core = (
                self.cq.Workplane("XY")
                .workplane(offset=thread_start)
                .circle(minor_radius)
                .extrude(thread_length)
            )
            bolt = bolt.union(thread_core)

        return bolt

    def _hex_nut(self, params: dict[str, Any]):
        for key in ["d", "s", "m"]:
            if key not in params:
                raise ValueError(f"Missing required params for hex_nut: {key!r}")

        d = float(params["d"])
        across_flats = float(params["s"])
        nut_height = float(params["m"])
        circumradius = across_flats / math.sqrt(3)
        bore_radius = d / 2

        nut = self.cq.Workplane("XY").polygon(6, circumradius * 2).extrude(nut_height)
        try:
            chamfer_size = min(0.8, nut_height * 0.1)
            nut = nut.faces(">Z").chamfer(chamfer_size)
            nut = nut.faces("<Z").chamfer(chamfer_size)
        except Exception:
            pass

        return nut.faces(">Z").workplane().circle(bore_radius).cutThruAll()

    def _export(self, shape, fmt: str, family: str, params: dict[str, Any], quality: str) -> tuple[bytes, dict[str, Any]]:
        if fmt == "glb":
            return self._export_glb(shape, family, quality)

        suffix = ".step" if fmt == "step" else ".stl"
        export_type = "STEP" if fmt == "step" else "STL"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            path = Path(tmp.name)
        try:
            self.cq.exporters.export(shape, str(path), exportType=export_type)
            return path.read_bytes(), {"exporter": f"cadquery_{export_type.lower()}"}
        finally:
            path.unlink(missing_ok=True)

    def _export_glb(self, shape, family: str, quality: str) -> tuple[bytes, dict[str, Any]]:
        with tempfile.NamedTemporaryFile(suffix=".glb", delete=False) as tmp:
            path = Path(tmp.name)
        try:
            assembly = self.cq.Assembly()
            assembly.add(shape, color=self.cq.Color(0.72, 0.72, 0.70), name=f"{family}_{quality}")
            assembly.export(str(path), tolerance=0.1, angularTolerance=0.2)
            data = path.read_bytes()
            if not data.startswith(b"glTF"):
                raise RuntimeError("CadQuery GLB export did not produce a binary glTF payload")
            return data, {"exporter": "cadquery_assembly_glb"}
        finally:
            path.unlink(missing_ok=True)


def get_cad_backend(name: str) -> CadBackend:
    if name == "mock":
        return MockCadBackend()
    if name == "cadquery":
        return CadQueryBackend()
    raise ValueError(f"Unknown CAD_BACKEND={name}")
