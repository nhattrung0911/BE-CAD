"""Ingest the 5 vendor STEP files from storage/research-samples/ into vendor_assets.

LOCAL RESEARCH ONLY. Defaults to license_status=approved + validation_status=valid
so the resolver returns the vendor file when the matching variant is selected.
Do NOT run this against a production database — the underlying files are not
licensed for redistribution.

Usage:

    python scripts/ingest_research_samples.py [--dry-run]

The script reads filenames, maps each to (product_id, variant_id) using the
same heuristic as `analyze_samples.py`, copies the file into the raw-asset
storage, and inserts a vendor_assets row.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLES_DIR = ROOT / "storage" / "research-samples"

STANDARD_TO_PRODUCT = {
    "ISO4014": "hex-bolt-iso4014",
    "ISO4032": "hex-nut-iso4032",
    "DIN6330": "hex-nut-din6330",
    "ISO7089": "washer-iso7089",
    "ISO7380": "button-head-iso7380",
    "DIN125": "washer-din125",
    "DIN931": "hex-bolt-din931",
    "DIN933": "hex-bolt-din933",
    "GB891": "retaining-ring-gb891",
}

# Heuristic mapping from filename → expected variant_id in seeded catalog.
# These match the variants in app/services/demo_catalog.py.
FILENAME_TO_VARIANT = {
    "din 933_m1.6x2.stp": "hex-bolt-din933-m1_6x2",
    "din931-2_m68x200.stp": None,  # M68x200 not in catalog seed; product-level
    "iso 7089_Φ1.6.stp": None,  # Φ1.6 not in catalog seed; product-level
    "iso4033_m5.stp": None,  # catalog dropped ISO 4033; DIN 6330 has no M5
    "iso7380-1_m3x6.stp": "button-head-iso7380-m3x6",
}

_STANDARD_RE = re.compile(r"\b(ISO|DIN|GB)\s*([0-9]{3,5})(?=\D|$)", re.IGNORECASE)


def _safe_print(*args, **kwargs):
    """Print without crashing on Windows cp1252 console for unicode filenames."""
    text = " ".join(str(a) for a in args)
    try:
        print(text, **kwargs)
    except UnicodeEncodeError:
        try:
            enc = sys.stdout.encoding or "ascii"
        except Exception:
            enc = "ascii"
        sys.stdout.write(text.encode(enc, errors="replace").decode(enc, errors="replace") + "\n")


def parse_product_id(filename: str) -> str | None:
    m = _STANDARD_RE.search(filename)
    if not m:
        return None
    key = (m.group(1) + m.group(2)).upper()
    return STANDARD_TO_PRODUCT.get(key)


def parse_variant_id(filename: str) -> str | None:
    return FILENAME_TO_VARIANT.get(filename.lower())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Print plan, do not write to DB / storage")
    args = parser.parse_args()

    if not SAMPLES_DIR.exists():
        print(f"ERROR: samples dir missing: {SAMPLES_DIR}", file=sys.stderr)
        return 2

    files = sorted(
        p for p in SAMPLES_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in {".step", ".stp", ".glb"}
    )
    if not files:
        print(f"No samples found in {SAMPLES_DIR}.")
        return 0

    plan: list[tuple[Path, str, str | None, str]] = []
    for f in files:
        product_id = parse_product_id(f.name)
        if not product_id:
            _safe_print(f"  - SKIP {f.name}: cannot resolve product_id from filename")
            continue
        variant_id = parse_variant_id(f.name)
        ext = f.suffix.lower().lstrip(".")
        fmt = "step" if ext in {"step", "stp"} else "glb"
        plan.append((f, product_id, variant_id, fmt))

    print(f"Plan ({len(plan)} files):")
    for f, pid, vid, fmt in plan:
        scope = f"variant={vid}" if vid else "product-level"
        _safe_print(f"  {f.name}  ->  {pid}  [{scope}]  format={fmt}")

    if args.dry_run:
        print("\n--dry-run: nothing written.")
        return 0

    # Real writes — import lazily so dry-run doesn't need DB up.
    from app.bootstrap.database import ensure_database_schema_current
    from app.core.database import SessionLocal
    from app.repositories.vendor_assets import VendorAssetRepository
    from app.services.storage import make_raw_asset_storage, safe_storage_segment

    ensure_database_schema_current()
    storage = make_raw_asset_storage()

    inserted = 0
    skipped = 0
    with SessionLocal() as session:
        repo = VendorAssetRepository(session)
        for f, pid, vid, fmt in plan:
            data = f.read_bytes()
            try:
                safe_pid = safe_storage_segment(pid)
                safe_fmt = safe_storage_segment(fmt)
                # Filename: keep extension, sanitize stem
                stem = re.sub(r"[^A-Za-z0-9._-]", "_", f.stem)
                safe_filename = f"{stem}.{fmt}"
                if vid:
                    safe_vid = safe_storage_segment(vid)
                    key = f"{safe_pid}/{safe_fmt}/{safe_vid}/{safe_filename}"
                else:
                    key = f"{safe_pid}/{safe_fmt}/{safe_filename}"
            except ValueError as exc:
                _safe_print(f"  SKIP {f.name}: storage segment unsafe: {exc}")
                skipped += 1
                continue

            stored = storage.put_bytes(key, data, content_type="application/step")
            existing = None
            for a in repo.list_by_product(pid):
                if a.storage_key == stored["storage_key"]:
                    existing = a
                    break
            if existing:
                repo.update_status(
                    existing,
                    license_status="approved",
                    validation_status="valid",
                )
                action = "updated"
            else:
                repo.create(
                    product_id=pid,
                    variant_id=vid,
                    fmt=fmt,
                    filename=safe_filename,
                    storage_key=stored["storage_key"],
                    sha256=stored["sha256"],
                    file_size=stored["file_size"],
                    license_status="approved",
                    validation_status="valid",
                )
                action = "inserted"
            inserted += 1
            scope = f"variant={vid}" if vid else "product-level"
            _safe_print(f"  {action} {f.name} ({pid}, {scope}) sha={stored['sha256'][:12]}")
        session.commit()

    print(f"\nDone. {inserted} ingested, {skipped} skipped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
