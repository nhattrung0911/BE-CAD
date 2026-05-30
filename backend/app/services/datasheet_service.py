"""PDF datasheet generation (reportlab, pure-Python — no system libs).

Builds an A4 datasheet for a fastener variant: a title block (product name,
standard, SKU) and the full parameter table (code / description / value / unit).
The 2D drawing has its own endpoint (/drawings/{variant}/2d.svg); embedding it
here would pull in an extra SVG-render dependency, so the datasheet stays
text/table only.
"""

from __future__ import annotations

import io
from typing import Any

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as _canvas

# Unit hints by parameter code (all linear dims and pitch are mm).
_UNIT = {
    "d": "mm", "L": "mm", "P": "mm", "k": "mm", "s": "mm", "b": "mm", "m": "mm",
    "OD": "mm", "ID": "mm", "h": "mm", "d1": "mm", "dk": "mm", "t": "mm",
}


def _fmt_value(v: Any) -> str:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    if f == int(f):
        return str(int(f))
    return f"{f:.3f}".rstrip("0").rstrip(".")


def build_datasheet_pdf(
    *,
    product_name: str,
    standard: str,
    sku: str,
    param_labels: dict[str, str],
    params: dict[str, Any],
) -> bytes:
    """Return a PDF datasheet as bytes.

    `param_labels` maps a parameter code to its human label (from the product's
    ParameterSpec); codes missing a label fall back to the code itself. `params`
    is the variant's resolved values (the synthetic `lod` key is skipped).
    """
    buf = io.BytesIO()
    c = _canvas.Canvas(buf, pagesize=A4)
    width, height = A4

    # Title block
    c.setFont("Helvetica-Bold", 18)
    c.drawString(20 * mm, height - 25 * mm, product_name or "Fastener")
    c.setFont("Helvetica", 11)
    c.drawString(20 * mm, height - 32 * mm, f"Standard: {standard}")
    c.drawString(20 * mm, height - 38 * mm, f"SKU: {sku}")
    c.line(20 * mm, height - 41 * mm, width - 20 * mm, height - 41 * mm)

    # Parameter table header
    c.setFont("Helvetica-Bold", 12)
    y = height - 52 * mm
    c.drawString(20 * mm, y, "Parameters")
    y -= 8 * mm
    c.setFont("Helvetica-Bold", 9)
    c.drawString(20 * mm, y, "Code")
    c.drawString(40 * mm, y, "Description")
    c.drawString(110 * mm, y, "Value")
    c.drawString(135 * mm, y, "Unit")
    y -= 2 * mm
    c.line(20 * mm, y, 155 * mm, y)
    y -= 6 * mm

    # Rows
    c.setFont("Helvetica", 9)
    for code, value in params.items():
        if code == "lod":
            continue
        c.drawString(20 * mm, y, str(code))
        c.drawString(40 * mm, y, param_labels.get(code, code))
        c.drawString(110 * mm, y, _fmt_value(value))
        c.drawString(135 * mm, y, _UNIT.get(code, ""))
        y -= 6 * mm
        if y < 20 * mm:
            c.showPage()
            y = height - 25 * mm
            c.setFont("Helvetica", 9)

    c.showPage()
    c.save()
    return buf.getvalue()
