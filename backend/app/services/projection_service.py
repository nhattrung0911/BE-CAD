"""2D orthographic drawing generation from a 3D solid.

Two layers:

- `polylines_to_svg` — pure, dependency-free serialization of 2D polylines (in a
  y-up drawing space) into an SVG document (y-down). Unit-tested without OCC.
- `project_solid` / `drawing_svg` — use OpenCASCADE hidden-line removal
  (HLRBRep) to project a solid to visible edges for a standard view, discretize
  the edges to polylines, and hand them to `polylines_to_svg`. These need a real
  cadquery/OCC install.

Coordinate note: the HLR projector returns edge geometry already flattened into
the projection plane, with the two in-plane axes as X/Y and the depth ~0.
"""

from __future__ import annotations

import logging
from typing import Iterable

logger = logging.getLogger(__name__)

Polyline = list[tuple[float, float]]

# Standard view directions: (eye-to-origin direction). Front looks along -Y, top
# along -Z, right along -X. These map a fastener's length/width/depth to sensible
# 2D drawings.
VIEWS = {
    "front": (0.0, 1.0, 0.0),
    "top": (0.0, 0.0, 1.0),
    "right": (1.0, 0.0, 0.0),
}

_STROKE = "#1b1f24"
_STROKE_WIDTH = 0.35


def _fmt(v: float) -> str:
    # Compact fixed-precision; drop trailing zeros for smaller payloads.
    s = f"{v:.3f}".rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"


def polylines_to_svg(polylines: Iterable[Polyline], *, margin: float = 4.0) -> str:
    """Serialize y-up 2D polylines to an SVG string (y-down, top-left origin).

    The viewBox is the geometry bounding box expanded by `margin` on each side.
    Polylines with fewer than 2 points are skipped. Y is flipped so the model's
    top renders at the top of the image.
    """
    lines = [pl for pl in polylines if pl and len(pl) >= 2]
    if not lines:
        side = max(margin * 2, 1.0)
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_fmt(side)} {_fmt(side)}">'
            f"</svg>"
        )

    xs = [p[0] for pl in lines for p in pl]
    ys = [p[1] for pl in lines for p in pl]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    width = (max_x - min_x) + 2 * margin
    height = (max_y - min_y) + 2 * margin

    def tx(x: float) -> float:
        return x - min_x + margin

    def ty(y: float) -> float:
        # flip: y-up model -> y-down svg
        return (max_y - y) + margin

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_fmt(width)} {_fmt(height)}">'
    ]
    for pl in lines:
        pts = " ".join(f"{_fmt(tx(x))},{_fmt(ty(y))}" for x, y in pl)
        parts.append(
            f'<polyline fill="none" stroke="{_STROKE}" stroke-width="{_STROKE_WIDTH}" points="{pts}" />'
        )
    parts.append("</svg>")
    return "".join(parts)


def project_solid(solid_wrapped, view: str = "front", *, segments: int = 16) -> list[Polyline]:
    """Project a TopoDS shape to visible-edge polylines for a named view.

    Requires OCC (OCP). Raises KeyError for an unknown view name.
    """
    from OCP.HLRBRep import HLRBRep_Algo, HLRBRep_HLRToShape
    from OCP.HLRAlgo import HLRAlgo_Projector
    from OCP.gp import gp_Ax2, gp_Pnt, gp_Dir
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopoDS import TopoDS
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.GCPnts import GCPnts_UniformAbscissa

    dx, dy, dz = VIEWS[view]
    algo = HLRBRep_Algo()
    algo.Add(solid_wrapped)
    algo.Projector(HLRAlgo_Projector(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(dx, dy, dz))))
    algo.Update()
    algo.Hide()
    visible = HLRBRep_HLRToShape(algo).VCompound()

    polylines: list[Polyline] = []
    if visible is None or visible.IsNull():
        return polylines

    exp = TopExp_Explorer(visible, TopAbs_EDGE)
    while exp.More():
        edge = TopoDS.Edge_s(exp.Current())
        curve = BRepAdaptor_Curve(edge)
        ua = GCPnts_UniformAbscissa(curve, max(segments, 2), curve.FirstParameter(), curve.LastParameter())
        pts: Polyline = []
        if ua.IsDone():
            for i in range(1, ua.NbPoints() + 1):
                p = curve.Value(ua.Parameter(i))
                pts.append((p.X(), p.Y()))
        if len(pts) >= 2:
            polylines.append(pts)
        exp.Next()
    return polylines


def drawing_svg(solid_wrapped, view: str = "front", *, margin: float = 4.0, segments: int = 16) -> str:
    """Full pipeline: project a solid for a view and serialize to SVG."""
    return polylines_to_svg(project_solid(solid_wrapped, view, segments=segments), margin=margin)
