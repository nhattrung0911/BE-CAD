import logging
import math
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

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
        elif family == "button_head":
            shape = self._button_head(params)
        else:
            raise KeyError(f"No CadQuery generator for family={family}")
        content, export_metadata = self._export(shape, fmt, family, params, quality)
        return GeneratedModel(
            content=content,
            format=fmt,
            metadata={"generator": self.name, "template": family, "params": params, **export_metadata},
        )

    def _build_threaded_shank(self, *, length: float, major_r: float, pitch: float, z_start: float = 0.0):
        """Threaded shank = solid core cylinder (minor_r) unioned with an outer
        ringed sleeve (annulus revolve, inner=minor_r, outer=major_r with grooves).

        Implementation note: a single-revolve profile that touches the rotation
        axis (radius=0) makes OCC emit a degenerate face that surfaces in the
        GLB as a huge flat disc. We avoid that by building two separate solids
        and unioning them — both profiles stay strictly off-axis.
        """
        if length <= 0 or pitch <= 0:
            raise ValueError("threaded shank requires positive length and pitch")
        minor_r = max(major_r - 0.6134 * pitch, major_r * 0.7)
        n_rings = max(int(round(length / pitch)), 1)
        actual_length = n_rings * pitch

        # 1) Solid inner core
        core = (
            self.cq.Workplane("XY")
            .circle(minor_r)
            .extrude(actual_length)
        )

        # 2) Outer ringed sleeve via revolve of a closed annulus profile.
        #    Inner edge at minor_r, outer edge oscillates between major_r and minor_r.
        sleeve_pts = [(minor_r, 0.0)]
        for i in range(n_rings):
            z0 = i * pitch
            sleeve_pts.append((major_r, z0 + pitch * 0.40))
            sleeve_pts.append((minor_r, z0 + pitch * 0.55))
            sleeve_pts.append((major_r, z0 + pitch))
        sleeve_pts.append((minor_r, actual_length))

        try:
            sleeve = (
                self.cq.Workplane("XZ")
                .polyline(sleeve_pts)
                .close()
                .revolve(360, axisStart=(0, 0, 0), axisEnd=(0, 1, 0))
            )
            body = core.union(sleeve)
        except Exception as exc:
            logger.warning(
                "threaded sleeve build failed (major_r=%s, pitch=%s, L=%s): %s; using plain cylinder",
                major_r, pitch, length, exc,
            )
            body = (
                self.cq.Workplane("XY")
                .circle(major_r)
                .extrude(actual_length)
            )

        if z_start:
            body = body.translate((0, 0, z_start))
        return body

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
        chamfer_applied = True
        try:
            head = head.faces(">Z").chamfer(min(1.0, head_height * 0.12))
            head = head.faces("<Z").chamfer(min(0.5, head_height * 0.08))
        except Exception as exc:
            chamfer_applied = False
            logger.warning("hex_bolt chamfer skipped (k=%s, s=%s): %s", head_height, across_flats, exc)
        self._last_chamfer_ok = chamfer_applied

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
            threaded = self._build_threaded_shank(
                length=thread_length,
                major_r=shank_radius,
                pitch=pitch,
                z_start=thread_start,
            )
            bolt = bolt.union(threaded)

        return bolt

    def _button_head(self, params: dict[str, Any]):
        for key in ["d", "L", "dk", "k", "s", "t"]:
            if key not in params:
                raise ValueError(f"Missing required params for button_head: {key!r}")
        d = float(params["d"])
        total_length = float(params["L"])
        head_dia = float(params["dk"])
        head_height = float(params["k"])
        socket_size = float(params["s"])
        socket_depth = float(params["t"])
        shank_radius = d / 2
        head_radius = head_dia / 2

        # Domed head: cylinder + filleted top edge approximated by spherical cap
        head = (
            self.cq.Workplane("XY")
            .circle(head_radius)
            .extrude(head_height)
        )
        try:
            fillet_r = min(head_height * 0.6, head_radius * 0.4)
            head = head.faces(">Z").edges().fillet(fillet_r)
        except Exception as exc:
            logger.warning("button_head fillet skipped (k=%s, dk=%s): %s", head_height, head_dia, exc)

        # Hex socket cut from top of head
        socket_circumradius = socket_size / math.sqrt(3)
        try:
            head = (
                head.faces(">Z")
                .workplane()
                .polygon(6, socket_circumradius * 2)
                .cutBlind(-min(socket_depth, head_height * 0.9))
            )
        except Exception as exc:
            logger.warning("button_head socket cut skipped: %s", exc)

        pitch = float(params.get("P") or 0)
        if pitch > 0:
            shank = self._build_threaded_shank(
                length=total_length,
                major_r=shank_radius,
                pitch=pitch,
                z_start=head_height,
            )
        else:
            shank = (
                self.cq.Workplane("XY")
                .workplane(offset=head_height)
                .circle(shank_radius)
                .extrude(total_length)
            )
        return head.union(shank)

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
        except Exception as exc:
            logger.warning("hex_nut chamfer skipped (m=%s, s=%s): %s", nut_height, across_flats, exc)

        # Estimate pitch from d (coarse-thread default per ISO 261)
        pitch = self._coarse_pitch_for_diameter(d)
        if pitch > 0:
            try:
                threaded_plug = self._build_threaded_shank(
                    length=nut_height + 0.4,
                    major_r=bore_radius + 0.6134 * pitch * 0.5,  # bore = major thread r
                    pitch=pitch,
                    z_start=-0.2,
                )
                return nut.cut(threaded_plug)
            except Exception as exc:
                logger.warning("hex_nut threaded bore skipped (d=%s, P=%s): %s", d, pitch, exc)
        return nut.faces(">Z").workplane().circle(bore_radius).cutThruAll()

    @staticmethod
    def _coarse_pitch_for_diameter(d: float) -> float:
        """ISO 261 coarse-thread pitch lookup. Returns 0 if d not supported."""
        # Conservative table — common coarse pitches.
        table = [
            (1.6, 0.35), (2.0, 0.4), (2.5, 0.45), (3.0, 0.5), (4.0, 0.7),
            (5.0, 0.8), (6.0, 1.0), (8.0, 1.25), (10.0, 1.5), (12.0, 1.75),
            (14.0, 2.0), (16.0, 2.0), (18.0, 2.5), (20.0, 2.5), (22.0, 2.5),
            (24.0, 3.0), (27.0, 3.0), (30.0, 3.5), (33.0, 3.5), (36.0, 4.0),
        ]
        best = (0.0, 0.0)
        for diameter, pitch in table:
            if abs(diameter - d) < abs(best[0] - d):
                best = (diameter, pitch)
        return best[1] if abs(best[0] - d) <= max(2.0, d * 0.15) else 0.0

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


@lru_cache(maxsize=4)
def _build_cad_backend(name: str) -> CadBackend:
    if name == "mock":
        return MockCadBackend()
    if name == "cadquery":
        return CadQueryBackend()
    raise ValueError(f"Unknown CAD_BACKEND={name}")


def get_cad_backend(name: str) -> CadBackend:
    """Return a process-wide singleton backend instance.

    CadQueryBackend imports OCC/cadquery on first construction (~hundreds of ms).
    Caching avoids that cost on every request when MODEL_SYNC_GENERATION=true
    or inside Celery worker processes that handle many jobs.
    """
    return _build_cad_backend(name)


def reset_cad_backend_cache() -> None:
    """For tests that monkeypatch CAD_BACKEND between cases."""
    _build_cad_backend.cache_clear()
