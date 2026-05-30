"""Analyze vendor reference 3D files for parametric template validation.

Reads files from `backend/storage/research-samples/`, extracts geometry stats
(bounding box, volume, surface area, vertex count, file sha256), and writes a
markdown + JSON report. Optionally compares against the running parametric
backend's output for the same product/variant.

Usage:
    python scripts/analyze_samples.py
    python scripts/analyze_samples.py --compare --api http://127.0.0.1:8000

Inputs/outputs are LOCAL ONLY. Results live under `docs/research/` which is
gitignored. Do not commit vendor reference geometry or analyzer output.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SAMPLES_DIR = ROOT / "storage" / "research-samples"
REPORT_DIR = ROOT.parent / "docs" / "research"
REPORT_MD = REPORT_DIR / "sample-analysis.md"
REPORT_JSON = SAMPLES_DIR / "_analysis.json"

SUPPORTED_EXTS = {"step", "stp", "glb"}

STANDARD_TO_PRODUCT = {
    "ISO4014": "hex-bolt-iso4014",
    "ISO4017": "hex-bolt-iso4017",
    "ISO4032": "hex-nut-iso4032",
    "DIN6330": "hex-nut-din6330",
    "ISO7089": "washer-iso7089",
    "ISO7380": "hex-bolt-iso7380",
    "DIN125": "washer-din125",
    "DIN931": "hex-bolt-din931",
    "DIN933": "hex-bolt-din933",
    "GB891": "retaining-ring-gb891",
}

_STANDARD_RE = re.compile(r"\b(ISO|DIN|GB)\s*([0-9]{3,5})\b", re.IGNORECASE)
_VARIANT_RE = re.compile(r"M\s*([0-9]+(?:\.[0-9]+)?)\s*(?:[xX]\s*([0-9]+(?:\.[0-9]+)?))?", re.IGNORECASE)
_DIAMETER_RE = re.compile(r"[ΦØd]\s*([0-9]+(?:\.[0-9]+)?)", re.IGNORECASE)


def parse_filename(name: str) -> tuple[str | None, str | None, str]:
    base, _, ext = name.rpartition(".")
    ext = ext.lower()
    s = _STANDARD_RE.search(base)
    product_id = None
    if s:
        key = (s.group(1) + s.group(2)).upper()
        product_id = STANDARD_TO_PRODUCT.get(key)

    variant = None
    m = _VARIANT_RE.search(base)
    if m:
        d = m.group(1)
        L = m.group(2)
        variant = f"m{d}x{L}".replace(".", "_") if L else f"m{d}".replace(".", "_")
    else:
        d = _DIAMETER_RE.search(base)
        if d:
            variant = f"d{d.group(1)}".replace(".", "_")
    return product_id, variant, ext


@dataclass
class SampleStats:
    filename: str
    product_id: str | None
    variant_suffix: str | None
    format: str
    file_size: int
    sha256: str
    bbox: dict[str, float] | None = None
    volume_mm3: float | None = None
    surface_area_mm2: float | None = None
    vertex_count: int | None = None
    triangle_count: int | None = None
    notes: list[str] = field(default_factory=list)
    error: str | None = None


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def analyze_glb(path: Path, stats: SampleStats) -> None:
    with path.open("rb") as fh:
        header = fh.read(12)
        if len(header) < 12 or header[:4] != b"glTF":
            stats.error = "Not a valid GLB (missing glTF magic)"
            return
        version, length = struct.unpack("<II", header[4:12])
        stats.notes.append(f"glb_version={version} declared_length={length}")
        chunk_header = fh.read(8)
        if len(chunk_header) < 8:
            stats.error = "Truncated GLB chunk header"
            return
        chunk_len, chunk_type = struct.unpack("<II", chunk_header)
        if chunk_type != 0x4E4F534A:  # 'JSON'
            stats.error = f"Unexpected first chunk type 0x{chunk_type:08x}"
            return
        json_bytes = fh.read(chunk_len).rstrip(b" \x00")
    try:
        gltf = json.loads(json_bytes)
    except json.JSONDecodeError as exc:
        stats.error = f"GLB JSON parse failed: {exc}"
        return

    vertex_count = 0
    triangle_count = 0
    accessors = gltf.get("accessors", [])
    for mesh in gltf.get("meshes", []):
        for primitive in mesh.get("primitives", []):
            attrs = primitive.get("attributes", {})
            pos_idx = attrs.get("POSITION")
            if pos_idx is not None and pos_idx < len(accessors):
                vertex_count += int(accessors[pos_idx].get("count", 0))
            indices_idx = primitive.get("indices")
            if indices_idx is not None and indices_idx < len(accessors):
                triangle_count += int(accessors[indices_idx].get("count", 0)) // 3

    bbox_min = [float("inf")] * 3
    bbox_max = [float("-inf")] * 3
    for accessor in accessors:
        if accessor.get("type") == "VEC3" and accessor.get("min") and accessor.get("max"):
            mn = accessor["min"]
            mx = accessor["max"]
            for i in range(3):
                bbox_min[i] = min(bbox_min[i], float(mn[i]))
                bbox_max[i] = max(bbox_max[i], float(mx[i]))

    stats.vertex_count = vertex_count or None
    stats.triangle_count = triangle_count or None
    if all(v != float("inf") for v in bbox_min):
        stats.bbox = {
            "min_x": bbox_min[0], "min_y": bbox_min[1], "min_z": bbox_min[2],
            "max_x": bbox_max[0], "max_y": bbox_max[1], "max_z": bbox_max[2],
            "size_x": bbox_max[0] - bbox_min[0],
            "size_y": bbox_max[1] - bbox_min[1],
            "size_z": bbox_max[2] - bbox_min[2],
        }


def analyze_step(path: Path, stats: SampleStats) -> None:
    try:
        import cadquery as cq  # type: ignore
    except ImportError:
        stats.error = "cadquery not installed; cannot read STEP"
        return
    try:
        wp = cq.importers.importStep(str(path))
    except Exception as exc:
        stats.error = f"STEP import failed: {exc}"
        return
    try:
        compound = wp.val()
        bb = compound.BoundingBox()
        stats.bbox = {
            "min_x": bb.xmin, "min_y": bb.ymin, "min_z": bb.zmin,
            "max_x": bb.xmax, "max_y": bb.ymax, "max_z": bb.zmax,
            "size_x": bb.xmax - bb.xmin,
            "size_y": bb.ymax - bb.ymin,
            "size_z": bb.zmax - bb.zmin,
        }
        try:
            stats.volume_mm3 = float(compound.Volume())
        except Exception:
            pass
        try:
            stats.surface_area_mm2 = float(compound.Area())
        except Exception:
            pass
    except Exception as exc:
        stats.error = f"STEP analysis failed: {exc}"


def analyze_file(path: Path) -> SampleStats:
    product, variant, ext = parse_filename(path.name)
    stats = SampleStats(
        filename=path.name,
        product_id=product,
        variant_suffix=variant,
        format=ext,
        file_size=path.stat().st_size,
        sha256=sha256_file(path),
    )
    if ext == "glb":
        analyze_glb(path, stats)
    elif ext in {"step", "stp"}:
        analyze_step(path, stats)
    else:
        stats.error = f"Unsupported extension: {ext}"
    return stats


def fetch_parametric(api: str, product_id: str, variant_id: str | None) -> dict[str, Any] | None:
    import urllib.request

    if not variant_id:
        return None
    url = f"{api.rstrip('/')}/api/v1/geometry/variant/{product_id}-{variant_id}?lod=high"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def render_markdown(samples: list[SampleStats], compare: list[dict[str, Any]] | None) -> str:
    lines: list[str] = ["# Sample Analysis", "", "_Local research only. Do not commit._", ""]
    if not samples:
        lines.append("No samples found in `backend/storage/research-samples/`.")
        return "\n".join(lines)

    lines.append(f"Found **{len(samples)}** sample(s).")
    lines.append("")
    lines.append("| File | Format | Size (KB) | BBox X×Y×Z (mm) | Volume (mm³) | Verts | Tris | SHA256 (8) |")
    lines.append("|---|---|---:|---|---:|---:|---:|---|")
    for s in samples:
        bb = s.bbox
        bbox_str = (
            f"{bb['size_x']:.2f} × {bb['size_y']:.2f} × {bb['size_z']:.2f}"
            if bb else "-"
        )
        vol = f"{s.volume_mm3:.1f}" if s.volume_mm3 else "-"
        vc = str(s.vertex_count) if s.vertex_count else "-"
        tc = str(s.triangle_count) if s.triangle_count else "-"
        size_kb = s.file_size / 1024
        lines.append(
            f"| `{s.filename}` | {s.format} | {size_kb:.1f} | {bbox_str} | {vol} | {vc} | {tc} | `{s.sha256[:8]}` |"
        )
        if s.error:
            lines.append(f"|   |   |   | ⚠ {s.error} |   |   |   |   |")

    if compare:
        lines.append("")
        lines.append("## Vendor vs Parametric")
        lines.append("")
        lines.append("| Sample | Vendor BBox | Parametric BBox | Δ size_x | Δ size_y | Δ size_z |")
        lines.append("|---|---|---|---:|---:|---:|")
        for row in compare:
            lines.append(
                "| {file} | {v} | {p} | {dx} | {dy} | {dz} |".format(**row)
            )

    lines.append("")
    lines.append("_See `_analysis.json` for full structured output._")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--compare", action="store_true", help="Compare with parametric backend")
    parser.add_argument("--api", default="http://127.0.0.1:8000", help="Parametric backend base URL")
    args = parser.parse_args()

    if not SAMPLES_DIR.exists():
        SAMPLES_DIR.mkdir(parents=True, exist_ok=True)

    files = sorted(
        p for p in SAMPLES_DIR.iterdir()
        if p.is_file() and p.suffix.lower().lstrip(".") in SUPPORTED_EXTS
    )
    if not files:
        print(f"No samples found in {SAMPLES_DIR}. Drop .step/.stp/.glb files there.")
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        REPORT_MD.write_text(render_markdown([], None), encoding="utf-8")
        REPORT_JSON.write_text("[]", encoding="utf-8")
        return 0

    samples = [analyze_file(p) for p in files]
    compare_rows: list[dict[str, Any]] | None = None

    if args.compare:
        compare_rows = []
        for s in samples:
            if not s.product_id or not s.bbox:
                continue
            param = fetch_parametric(args.api, s.product_id, s.variant_suffix)
            if not param or "error" in param:
                compare_rows.append({
                    "file": s.filename,
                    "v": "-", "p": param.get("error", "n/a") if param else "n/a",
                    "dx": "-", "dy": "-", "dz": "-",
                })
                continue
            v_bbox = s.bbox
            p_bbox = (param.get("artifact") or {}).get("bbox") or {}
            if p_bbox:
                row = {
                    "file": s.filename,
                    "v": f"{v_bbox['size_x']:.2f}×{v_bbox['size_y']:.2f}×{v_bbox['size_z']:.2f}",
                    "p": f"{p_bbox.get('size_x', 0):.2f}×{p_bbox.get('size_y', 0):.2f}×{p_bbox.get('size_z', 0):.2f}",
                    "dx": f"{v_bbox['size_x'] - p_bbox.get('size_x', 0):+.2f}",
                    "dy": f"{v_bbox['size_y'] - p_bbox.get('size_y', 0):+.2f}",
                    "dz": f"{v_bbox['size_z'] - p_bbox.get('size_z', 0):+.2f}",
                }
            else:
                row = {
                    "file": s.filename,
                    "v": f"{v_bbox['size_x']:.2f}×{v_bbox['size_y']:.2f}×{v_bbox['size_z']:.2f}",
                    "p": f"status={param.get('status')} (no bbox in artifact)",
                    "dx": "-", "dy": "-", "dz": "-",
                }
            compare_rows.append(row)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text(render_markdown(samples, compare_rows), encoding="utf-8")
    REPORT_JSON.write_text(
        json.dumps([asdict(s) for s in samples], indent=2),
        encoding="utf-8",
    )

    print(f"Analyzed {len(samples)} file(s).")
    print(f"  Markdown: {REPORT_MD}")
    print(f"  JSON:     {REPORT_JSON}")
    if any(s.error for s in samples):
        print("  Errors detected — see report.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
