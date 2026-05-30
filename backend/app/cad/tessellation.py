"""LOD-driven tessellation tolerances for mesh (GLB) export.

The cadquery/OCC mesher takes a *linear* deflection (max chordal distance between
the true surface and a triangle edge, in mm) and an *angular* deflection (max
angle between adjacent facet normals, in radians). Smaller = smoother + more
triangles. We make the linear tolerance size-relative so a 6 mm screw and a
100 mm ring tessellate proportionally rather than the small part looking blocky.
"""

from __future__ import annotations

# (linear factor of part size, linear floor in mm, angular tolerance in rad)
_TIERS = {
    "low": (0.020, 0.15, 0.50),     # ~29 deg facets
    "medium": (0.010, 0.05, 0.30),  # ~17 deg
    "high": (0.004, 0.02, 0.15),    # ~8.6 deg
}

DEFAULT_LOD = "medium"


def tessellation_for_lod(lod: str, part_size_mm: float) -> tuple[float, float]:
    """Return (linear_tolerance_mm, angular_tolerance_rad) for an LOD tier.

    `part_size_mm` is the largest bounding-box dimension of the part; the linear
    tolerance scales with it but never drops below a per-tier floor (so tiny
    parts still get a sane absolute smoothness and huge parts don't explode).
    Unknown LODs fall back to medium.
    """
    factor, floor, angular = _TIERS.get(lod, _TIERS[DEFAULT_LOD])
    size = part_size_mm if part_size_mm and part_size_mm > 0 else 1.0
    linear = max(size * factor, floor)
    return linear, angular
