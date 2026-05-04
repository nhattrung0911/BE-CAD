import base64
import re
from html import unescape
from typing import Any


DIMENSION_LABEL_PATTERN = re.compile(
    r">\s*([A-Za-z][A-Za-z0-9_]*):\s*([0-9.]+)(?:\s*-\s*([0-9.]+))?\s*<"
)


def parse_svg_dimension_labels(html_or_svg: str) -> dict[str, Any]:
    """Parse simple labels such as `h:6.8-7.2`, `d1:12.8-13.2`, `OD:99.8-100.2`."""
    chunks = [html_or_svg]
    for encoded in re.findall(r"data:image/svg\+xml;base64,([A-Za-z0-9+/=]+)", html_or_svg):
        try:
            chunks.append(base64.b64decode(encoded).decode("utf-8", errors="ignore"))
        except Exception:
            continue

    labels: dict[str, Any] = {}
    for chunk in chunks:
        text = unescape(chunk)
        for name, lo, hi in DIMENSION_LABEL_PATTERN.findall(text):
            if hi:
                labels[name] = {"min": float(lo), "max": float(hi)}
            else:
                labels[name] = float(lo)
    return labels


def parse_spec_table_text(html: str) -> dict[str, str]:
    plain = re.sub(r"<[^>]+>", " ", html)
    plain = re.sub(r"\s+", " ", unescape(plain)).strip()
    aliases = {
        "unit": ["unit"],
        "material": ["material"],
        "standard": ["standard"],
        "size": ["size"],
        "name": ["name"],
        "surface": ["surface"],
        "barcode": ["barcode"],
    }
    result = {}
    for canonical, keys in aliases.items():
        pattern = r"(?:%s)\s*([^\s]+)" % "|".join(re.escape(key) for key in keys)
        m = re.search(pattern, plain, flags=re.IGNORECASE)
        if m:
            result[canonical] = m.group(1)
    return result
