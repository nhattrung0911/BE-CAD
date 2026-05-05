import argparse
import csv
import hashlib
import io
import json
import logging
import os
import sys
import zipfile
from pathlib import Path
from typing import Iterator

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("bulk_import")

GLB_MAGIC = b"glTF"
DEFAULT_API = "http://localhost:8000"


class ImportItem:
    def __init__(
        self,
        filename: str,
        product_id: str,
        data: bytes,
        license_status: str = "pending",
        validation_status: str = "pending",
        variant_id: str | None = None,
    ) -> None:
        self.filename = filename
        self.product_id = product_id
        self.data = data
        self.license_status = license_status
        self.validation_status = validation_status
        self.variant_id = variant_id
        self.sha256 = hashlib.sha256(data).hexdigest()
        self.size_kb = len(data) / 1024

    @property
    def is_valid_glb(self) -> bool:
        return self.data[:4] == GLB_MAGIC


def _iter_glb_paths(source_dir: Path) -> list[Path]:
    # Windows filesystems are case-insensitive, so normalize discovered paths
    # to avoid reading the same file twice when scanning *.glb and *.GLB.
    unique: dict[str, Path] = {}
    for pattern in ("**/*.glb", "**/*.GLB"):
        for path in source_dir.glob(pattern):
            unique.setdefault(str(path.resolve()).lower(), path)
    return sorted(unique.values(), key=lambda item: item.name.lower())


def read_from_dir(source_dir: Path, mapping: dict[str, dict]) -> Iterator[ImportItem]:
    glb_files = _iter_glb_paths(source_dir)
    logger.info("Found %d GLB files in %s", len(glb_files), source_dir)

    for glb_path in glb_files:
        filename = glb_path.name
        meta = mapping.get(filename)
        if meta is None:
            logger.debug("Skip (not in mapping): %s", filename)
            continue
        yield ImportItem(
            filename=filename,
            product_id=meta["product_id"],
            data=glb_path.read_bytes(),
            license_status=meta.get("license_status", "pending"),
            variant_id=meta.get("variant_id"),
        )


def read_from_zip(zip_path: Path, mapping: dict[str, dict]) -> Iterator[ImportItem]:
    with zipfile.ZipFile(zip_path, "r") as archive:
        glb_names = [name for name in archive.namelist() if name.lower().endswith(".glb")]
        logger.info("Found %d GLB files in ZIP", len(glb_names))

        for name in glb_names:
            filename = Path(name).name
            meta = mapping.get(filename)
            if meta is None:
                logger.debug("Skip (not in mapping): %s", filename)
                continue
            yield ImportItem(
                filename=filename,
                product_id=meta["product_id"],
                data=archive.read(name),
                license_status=meta.get("license_status", "pending"),
                variant_id=meta.get("variant_id"),
            )


def auto_map(source_dir: Path) -> Iterator[ImportItem]:
    glb_files = _iter_glb_paths(source_dir)
    logger.info("Auto-mapping %d GLB files by filename", len(glb_files))
    for glb_path in glb_files:
        yield ImportItem(
            filename=glb_path.name,
            product_id=glb_path.stem.lower().replace("_", "-"),
            data=glb_path.read_bytes(),
            license_status="pending",
        )


def load_mapping(csv_path: Path) -> dict[str, dict]:
    mapping: dict[str, dict] = {}
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            filename = row.get("filename", "").strip()
            if not filename:
                continue
            mapping[filename] = {
                "product_id": row.get("product_id", "").strip(),
                "license_status": row.get("license_status", "pending").strip() or "pending",
                "variant_id": (row.get("variant_id", "") or "").strip() or None,
            }
    logger.info("Loaded %d entries from mapping CSV", len(mapping))
    return mapping


def upload_item(
    item: ImportItem,
    api_base: str,
    admin_key: str,
    dry_run: bool = False,
) -> dict:
    if dry_run:
        status = "valid" if item.is_valid_glb else "invalid_magic"
        return {
            "filename": item.filename,
            "product_id": item.product_id,
            "variant_id": item.variant_id,
            "size_kb": round(item.size_kb, 1),
            "sha256": item.sha256[:12] + "...",
            "valid_glb": item.is_valid_glb,
            "status": f"DRY_RUN:{status}",
        }

    if not item.is_valid_glb:
        return {
            "filename": item.filename,
            "product_id": item.product_id,
            "variant_id": item.variant_id,
            "status": "SKIP:invalid_glb_magic",
            "sha256": item.sha256[:12] + "...",
        }

    headers = {"X-Admin-API-Key": admin_key}
    files = {
        "file": (item.filename, io.BytesIO(item.data), "model/gltf-binary"),
    }
    data = {
        "product_id": item.product_id,
        "format": "glb",
        "license_status": item.license_status,
        "validation_status": item.validation_status,
    }
    if item.variant_id:
        data["variant_id"] = item.variant_id

    try:
        response = httpx.post(
            f"{api_base}/api/v1/vendor-assets",
            headers=headers,
            files=files,
            data=data,
            timeout=60.0,
        )
    except httpx.HTTPError as exc:
        logger.error("Upload failed for %s: %s", item.filename, exc)
        return {
            "filename": item.filename,
            "product_id": item.product_id,
            "variant_id": item.variant_id,
            "status": f"EXCEPTION:{type(exc).__name__}",
            "detail": str(exc)[:200],
        }

    if response.status_code == 201:
        payload = response.json()
        return {
            "filename": item.filename,
            "product_id": item.product_id,
            "variant_id": item.variant_id,
            "size_kb": round(item.size_kb, 1),
            "status": "OK",
            "asset_id": payload.get("id"),
            "url": payload.get("url"),
        }
    if response.status_code == 409:
        return {
            "filename": item.filename,
            "product_id": item.product_id,
            "variant_id": item.variant_id,
            "status": "SKIP:duplicate_sha256",
        }
    return {
        "filename": item.filename,
        "product_id": item.product_id,
        "variant_id": item.variant_id,
        "status": f"ERROR:{response.status_code}",
        "detail": response.text[:200],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Bulk import GLB files into the vendor asset API.")
    parser.add_argument("--source-dir", type=Path, help="Folder containing GLB files")
    parser.add_argument("--zip", type=Path, dest="zip_path", help="ZIP file containing GLBs")
    parser.add_argument("--product-map", type=Path, dest="product_map", help="CSV mapping file")
    parser.add_argument("--auto-map", action="store_true", help="Map filename stem to product_id")
    parser.add_argument("--api", default=DEFAULT_API, help=f"API base URL (default: {DEFAULT_API})")
    parser.add_argument("--admin-key", default="", help="X-Admin-API-Key or env ADMIN_API_KEY")
    parser.add_argument("--dry-run", action="store_true", help="Validate files without uploading")
    parser.add_argument("--output", type=Path, help="Write JSON results to file")
    args = parser.parse_args()

    admin_key = args.admin_key or os.getenv("ADMIN_API_KEY", "")
    if not admin_key and not args.dry_run:
        logger.error("ADMIN_API_KEY is required. Use --admin-key or set env ADMIN_API_KEY")
        raise SystemExit(1)
    if not args.source_dir and not args.zip_path:
        parser.error("Must provide --source-dir or --zip")
    if not args.product_map and not args.auto_map:
        parser.error("Must provide --product-map or --auto-map")

    if args.auto_map and args.source_dir:
        items = list(auto_map(args.source_dir))
    else:
        mapping = load_mapping(args.product_map)
        items = list(read_from_zip(args.zip_path, mapping) if args.zip_path else read_from_dir(args.source_dir, mapping))

    if not items:
        logger.warning("No files matched the selected source and mapping.")
        raise SystemExit(0)

    results = []
    ok = skip = error = 0
    for index, item in enumerate(items, start=1):
        result = upload_item(item, args.api, admin_key, dry_run=args.dry_run)
        results.append(result)
        print(f"[{index:3d}/{len(items)}] {result['status']:30s} {item.filename}")
        if result["status"].startswith("OK"):
            ok += 1
        elif result["status"].startswith("SKIP"):
            skip += 1
        else:
            error += 1

    logger.info("OK=%d Skip=%d Error=%d", ok, skip, error)
    if args.output:
        args.output.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("Results saved to %s", args.output)
    raise SystemExit(1 if error > 0 else 0)


if __name__ == "__main__":
    main()
