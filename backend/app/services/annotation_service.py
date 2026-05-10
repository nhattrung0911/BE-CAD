from __future__ import annotations

from dataclasses import dataclass
from typing import Any

LABEL_MAP = {
    "d": "Diameter (d)",
    "L": "Length (L)",
    "P": "Thread pitch (P)",
    "k": "Head height (k)",
    "s": "Width across flats (s)",
    "b": "Thread length (b)",
    "m": "Nut height (m)",
    "OD": "Outer diameter",
    "ID": "Inner diameter",
    "h": "Thickness (h)",
    "d1": "Hole diameter",
}

COLOR_MAP = {
    "d": "#4FC3F7",
    "L": "#A5D6A7",
    "s": "#FFB74D",
    "k": "#CE93D8",
    "P": "#80DEEA",
    "b": "#FFCC02",
    "m": "#CE93D8",
    "OD": "#4FC3F7",
    "ID": "#EF9A9A",
    "h": "#A5D6A7",
    "d1": "#4FC3F7",
}


@dataclass
class DimensionAnnotation:
    key: str
    label: str
    value_mm: float
    from_point: list[float]
    to_point: list[float]
    axis: str
    color_hex: str
    plane: str = "XZ"


# Dimension placement contract:
#   - All dimension lines are anchored at the world coordinate origin and
#     extend along a principal axis (X or Z). They are NEVER stuck to a part
#     face whose position changes with parameters (e.g., "+Y face at y=s/2+2"),
#     because that makes the dim drift relative to the model and confuses the
#     viewer auto-fit.
#   - Length-style dims (along Z): a vertical line at (radial_offset, 0, *)
#     spanning [0, value]. Multiple Z dims stack at increasing radial offsets
#     so they don't overlap.
#   - Diameter-style dims (across X at z=0): a horizontal line through the
#     origin in the XZ plane spanning [-value/2, +value/2]. Multiple X dims at
#     z=0 stack along Z just above origin.
# This keeps annotations co-located with the model bbox and stable as the
# user edits parameters.

_RADIAL_PAD = 4.0   # gap between part outer surface and first vertical dim line
_RADIAL_STEP = 4.0  # additional offset per stacked vertical dim
_X_DIM_Z_BASE = 0.0 # all "across X" dims sit at z=0 by default
_X_DIM_Z_STEP = 1.5 # if multiple X dims at origin, stack along Z


def _z_dim(key: str, value: float, slot: int, radial_anchor: float, color: str) -> DimensionAnnotation:
    """Vertical (along Z) dimension: line at (radial_anchor + slot*step, 0, *)
    spanning [0, value]."""
    x = radial_anchor + _RADIAL_PAD + slot * _RADIAL_STEP
    return DimensionAnnotation(
        key=key,
        label=LABEL_MAP.get(key, key),
        value_mm=value,
        from_point=[x, 0.0, 0.0],
        to_point=[x, 0.0, value],
        axis="z",
        color_hex=color,
        plane="XZ",
    )


def _x_dim(key: str, value: float, slot: int, color: str) -> DimensionAnnotation:
    """Horizontal (across X) dimension at the origin plane: line at z = slot*step
    spanning [-value/2, +value/2]."""
    z = _X_DIM_Z_BASE - (slot + 1) * _X_DIM_Z_STEP
    return DimensionAnnotation(
        key=key,
        label=LABEL_MAP.get(key, key),
        value_mm=value,
        from_point=[-value / 2, 0.0, z],
        to_point=[value / 2, 0.0, z],
        axis="x",
        color_hex=color,
        plane="XZ",
    )


def compute_annotations(
    family: str,
    params: dict[str, Any],
) -> list[DimensionAnnotation]:
    handlers = {
        "hex_bolt": _hex_bolt_annotations,
        "hex_nut": _hex_nut_annotations,
        "washer": _washer_annotations,
        "retaining_ring": _retaining_ring_annotations,
    }
    handler = handlers.get(family)
    if handler is None:
        return []
    try:
        return handler(params)
    except (KeyError, TypeError, ValueError):
        return []


def _hex_bolt_annotations(params: dict[str, Any]) -> list[DimensionAnnotation]:
    diameter = float(params["d"])
    length = float(params["L"])
    head_height = float(params["k"])
    width_across_flats = float(params["s"])
    thread_length = float(params.get("b", length * 0.6))

    # Radial anchor = outer extent of the part in the XY plane (head flats win).
    radial_anchor = max(width_across_flats / 2, diameter / 2)

    annotations: list[DimensionAnnotation] = []
    # Across-X dims at origin plane, stacked downward in Z.
    annotations.append(_x_dim("d", diameter, slot=0, color=COLOR_MAP["d"]))
    annotations.append(_x_dim("s", width_across_flats, slot=1, color=COLOR_MAP["s"]))
    # Along-Z dims, stacked outward in X.
    annotations.append(_z_dim("L", length, slot=0, radial_anchor=radial_anchor, color=COLOR_MAP["L"]))
    annotations.append(_z_dim("k", head_height, slot=1, radial_anchor=radial_anchor, color=COLOR_MAP["k"]))
    if thread_length > 0:
        annotations.append(_z_dim("b", thread_length, slot=2, radial_anchor=radial_anchor, color=COLOR_MAP["b"]))
    return annotations


def _hex_nut_annotations(params: dict[str, Any]) -> list[DimensionAnnotation]:
    diameter = float(params["d"])
    width_across_flats = float(params["s"])
    nut_height = float(params["m"])
    radial_anchor = width_across_flats / 2

    return [
        _x_dim("d", diameter, slot=0, color=COLOR_MAP["d"]),
        _x_dim("s", width_across_flats, slot=1, color=COLOR_MAP["s"]),
        _z_dim("m", nut_height, slot=0, radial_anchor=radial_anchor, color=COLOR_MAP["m"]),
    ]


def _washer_annotations(params: dict[str, Any]) -> list[DimensionAnnotation]:
    outer_diameter = float(params["OD"])
    inner_diameter = float(params["ID"])
    thickness = float(params["h"])
    radial_anchor = outer_diameter / 2

    return [
        _x_dim("OD", outer_diameter, slot=0, color=COLOR_MAP["OD"]),
        _x_dim("ID", inner_diameter, slot=1, color=COLOR_MAP["ID"]),
        _z_dim("h", thickness, slot=0, radial_anchor=radial_anchor, color=COLOR_MAP["h"]),
    ]


def _retaining_ring_annotations(params: dict[str, Any]) -> list[DimensionAnnotation]:
    outer_diameter = float(params["OD"])
    hole_diameter = float(params["d1"])
    thickness = float(params["h"])
    radial_anchor = outer_diameter / 2

    return [
        _x_dim("OD", outer_diameter, slot=0, color=COLOR_MAP["OD"]),
        _x_dim("d1", hole_diameter, slot=1, color=COLOR_MAP["d1"]),
        _z_dim("h", thickness, slot=0, radial_anchor=radial_anchor, color=COLOR_MAP["h"]),
    ]
