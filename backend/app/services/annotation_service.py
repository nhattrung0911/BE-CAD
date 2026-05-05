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

    radius = diameter / 2
    dim_offset_x = radius + 4.0
    dim_offset_s = width_across_flats / 2 + 3.0
    grip_mid_z = head_height + (length - thread_length) / 2

    annotations = [
        DimensionAnnotation(
            key="d",
            label=LABEL_MAP["d"],
            value_mm=diameter,
            from_point=[-radius, 0.0, grip_mid_z],
            to_point=[radius, 0.0, grip_mid_z],
            axis="x",
            color_hex=COLOR_MAP["d"],
            plane="XZ",
        ),
        DimensionAnnotation(
            key="L",
            label=LABEL_MAP["L"],
            value_mm=length,
            from_point=[dim_offset_x + 2, 0.0, head_height],
            to_point=[dim_offset_x + 2, 0.0, head_height + length],
            axis="z",
            color_hex=COLOR_MAP["L"],
            plane="XZ",
        ),
        DimensionAnnotation(
            key="k",
            label=LABEL_MAP["k"],
            value_mm=head_height,
            from_point=[dim_offset_s + 2, 0.0, 0.0],
            to_point=[dim_offset_s + 2, 0.0, head_height],
            axis="z",
            color_hex=COLOR_MAP["k"],
            plane="XZ",
        ),
        DimensionAnnotation(
            key="s",
            label=LABEL_MAP["s"],
            value_mm=width_across_flats,
            from_point=[-width_across_flats / 2, width_across_flats / 2 + 2, head_height / 2],
            to_point=[width_across_flats / 2, width_across_flats / 2 + 2, head_height / 2],
            axis="x",
            color_hex=COLOR_MAP["s"],
            plane="XY",
        ),
    ]
    if thread_length > 0:
        annotations.append(
            DimensionAnnotation(
                key="b",
                label=LABEL_MAP["b"],
                value_mm=thread_length,
                from_point=[-(dim_offset_x + 2), 0.0, head_height + length - thread_length],
                to_point=[-(dim_offset_x + 2), 0.0, head_height + length],
                axis="z",
                color_hex=COLOR_MAP["b"],
                plane="XZ",
            )
        )
    return annotations


def _hex_nut_annotations(params: dict[str, Any]) -> list[DimensionAnnotation]:
    diameter = float(params["d"])
    width_across_flats = float(params["s"])
    nut_height = float(params["m"])
    bore_radius = diameter / 2
    dim_offset = width_across_flats / 2 + 4.0

    return [
        DimensionAnnotation(
            key="d",
            label=LABEL_MAP["d"],
            value_mm=diameter,
            from_point=[-bore_radius, 0.0, nut_height / 2],
            to_point=[bore_radius, 0.0, nut_height / 2],
            axis="x",
            color_hex=COLOR_MAP["d"],
            plane="XZ",
        ),
        DimensionAnnotation(
            key="s",
            label=LABEL_MAP["s"],
            value_mm=width_across_flats,
            from_point=[-width_across_flats / 2, width_across_flats / 2 + 2, nut_height / 2],
            to_point=[width_across_flats / 2, width_across_flats / 2 + 2, nut_height / 2],
            axis="x",
            color_hex=COLOR_MAP["s"],
            plane="XY",
        ),
        DimensionAnnotation(
            key="m",
            label=LABEL_MAP["m"],
            value_mm=nut_height,
            from_point=[dim_offset, 0.0, 0.0],
            to_point=[dim_offset, 0.0, nut_height],
            axis="z",
            color_hex=COLOR_MAP["m"],
            plane="XZ",
        ),
    ]


def _washer_annotations(params: dict[str, Any]) -> list[DimensionAnnotation]:
    outer_diameter = float(params["OD"])
    inner_diameter = float(params["ID"])
    thickness = float(params["h"])
    dim_z = thickness + 2.0

    return [
        DimensionAnnotation(
            key="OD",
            label=LABEL_MAP["OD"],
            value_mm=outer_diameter,
            from_point=[-outer_diameter / 2, 0.0, dim_z],
            to_point=[outer_diameter / 2, 0.0, dim_z],
            axis="x",
            color_hex=COLOR_MAP["OD"],
            plane="XZ",
        ),
        DimensionAnnotation(
            key="ID",
            label=LABEL_MAP["ID"],
            value_mm=inner_diameter,
            from_point=[-inner_diameter / 2, 0.0, thickness / 2],
            to_point=[inner_diameter / 2, 0.0, thickness / 2],
            axis="x",
            color_hex=COLOR_MAP["ID"],
            plane="XZ",
        ),
        DimensionAnnotation(
            key="h",
            label=LABEL_MAP["h"],
            value_mm=thickness,
            from_point=[outer_diameter / 2 + 3, 0.0, 0.0],
            to_point=[outer_diameter / 2 + 3, 0.0, thickness],
            axis="z",
            color_hex=COLOR_MAP["h"],
            plane="XZ",
        ),
    ]


def _retaining_ring_annotations(params: dict[str, Any]) -> list[DimensionAnnotation]:
    outer_diameter = float(params["OD"])
    hole_diameter = float(params["d1"])
    thickness = float(params["h"])

    return [
        DimensionAnnotation(
            key="OD",
            label=LABEL_MAP["OD"],
            value_mm=outer_diameter,
            from_point=[-outer_diameter / 2, 0.0, thickness + 2],
            to_point=[outer_diameter / 2, 0.0, thickness + 2],
            axis="x",
            color_hex=COLOR_MAP["OD"],
            plane="XZ",
        ),
        DimensionAnnotation(
            key="d1",
            label=LABEL_MAP["d1"],
            value_mm=hole_diameter,
            from_point=[-hole_diameter / 2, 0.0, thickness / 2],
            to_point=[hole_diameter / 2, 0.0, thickness / 2],
            axis="x",
            color_hex=COLOR_MAP["d1"],
            plane="XZ",
        ),
        DimensionAnnotation(
            key="h",
            label=LABEL_MAP["h"],
            value_mm=thickness,
            from_point=[outer_diameter / 2 + 3, 0.0, 0.0],
            to_point=[outer_diameter / 2 + 3, 0.0, thickness],
            axis="z",
            color_hex=COLOR_MAP["h"],
            plane="XZ",
        ),
    ]
