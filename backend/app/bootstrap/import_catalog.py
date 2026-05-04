"""CSV bulk catalog importer for non-technical operators.

CSV schema (headers required, one row = one variant):

    product_id,family,standard,name,variant_id,sku,label,diameter_label,material,params

Where `params` is a JSON object (single column) like `{"d":8,"L":30,"P":1.25,...}`.

The importer groups rows by `product_id`, builds Product + variants list, then
calls `CatalogRepository.replace_product_catalog`. ParameterSpec is auto-derived
from the union of param keys present in the variants.

Usage:

    python -m app.bootstrap.import_catalog --csv path/to/catalog.csv --dry-run
    python -m app.bootstrap.import_catalog --csv path/to/catalog.csv

Operator-friendly contract: errors print row number + column name, no stack
traces unless `--debug` is passed.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

from app.bootstrap.database import ensure_database_schema_current
from app.core.database import SessionLocal
from app.repositories.catalog import CatalogRepository
from app.schemas.product import ParameterSpec, Product

REQUIRED_COLUMNS = {
    "product_id",
    "family",
    "standard",
    "name",
    "variant_id",
    "sku",
    "label",
    "diameter_label",
    "material",
    "params",
}

_PRODUCT_ID_RE = re.compile(r"[a-z0-9][a-z0-9._-]*")


@dataclass
class RowError:
    row_number: int
    column: str
    message: str

    def __str__(self) -> str:
        return f"row {self.row_number} [{self.column}]: {self.message}"


def _validate_headers(fieldnames: list[str] | None) -> list[str]:
    if not fieldnames:
        return ["CSV has no header row"]
    missing = REQUIRED_COLUMNS - set(fieldnames)
    if missing:
        return [f"missing required columns: {sorted(missing)}"]
    return []


def _parse_row(row_number: int, row: dict[str, str]) -> tuple[dict, list[RowError]]:
    errors: list[RowError] = []
    cleaned: dict = {}
    for col in REQUIRED_COLUMNS:
        value = (row.get(col) or "").strip()
        if not value:
            errors.append(RowError(row_number, col, "empty value"))
            continue
        cleaned[col] = value

    if "product_id" in cleaned and not _PRODUCT_ID_RE.fullmatch(cleaned["product_id"]):
        errors.append(RowError(row_number, "product_id", "must match [a-z0-9][a-z0-9._-]*"))
    if "variant_id" in cleaned and not _PRODUCT_ID_RE.fullmatch(cleaned["variant_id"]):
        errors.append(RowError(row_number, "variant_id", "must match [a-z0-9][a-z0-9._-]*"))

    if "params" in cleaned:
        try:
            params = json.loads(cleaned["params"])
        except json.JSONDecodeError as exc:
            errors.append(RowError(row_number, "params", f"not valid JSON: {exc}"))
        else:
            if not isinstance(params, dict) or not params:
                errors.append(RowError(row_number, "params", "must be a non-empty JSON object"))
            else:
                for k, v in params.items():
                    if not isinstance(v, (int, float)):
                        errors.append(
                            RowError(row_number, "params", f"value for {k!r} must be numeric, got {type(v).__name__}")
                        )
                cleaned["params_dict"] = params

    return cleaned, errors


def _build_products(rows: list[dict]) -> tuple[OrderedDict[str, Product], dict[str, list[dict]]]:
    products: OrderedDict[str, Product] = OrderedDict()
    variants: dict[str, list[dict]] = {}
    for row in rows:
        product_id = row["product_id"]
        if product_id not in products:
            products[product_id] = Product(
                product_id=product_id,
                family=row["family"],
                standard=row["standard"],
                name=row["name"],
                parameters=[],
            )
            variants[product_id] = []
        variants[product_id].append(
            {
                "variant_id": row["variant_id"],
                "sku": row["sku"],
                "label": row["label"],
                "diameter_label": row["diameter_label"],
                "material": row["material"],
                "params": row["params_dict"],
            }
        )

    # Derive ParameterSpec list from the union of param keys in variants.
    for product_id, product in products.items():
        keys: list[str] = []
        seen: set[str] = set()
        for variant in variants[product_id]:
            for k in variant["params"].keys():
                if k not in seen:
                    seen.add(k)
                    keys.append(k)
        products[product_id] = product.model_copy(
            update={"parameters": [ParameterSpec(name=k, label=k) for k in keys]}
        )

    return products, variants


def import_catalog_csv(csv_path: Path, *, dry_run: bool) -> tuple[int, int, list[str]]:
    """Returns (products_imported, variants_imported, error_messages)."""
    with csv_path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        header_errors = _validate_headers(reader.fieldnames)
        if header_errors:
            return 0, 0, header_errors

        rows: list[dict] = []
        all_errors: list[RowError] = []
        for row_number, raw in enumerate(reader, start=2):  # 1-indexed including header
            cleaned, errors = _parse_row(row_number, raw)
            if errors:
                all_errors.extend(errors)
                continue
            rows.append(cleaned)

    if all_errors:
        return 0, 0, [str(e) for e in all_errors]

    products, variants = _build_products(rows)
    variant_count = sum(len(v) for v in variants.values())

    if dry_run:
        return len(products), variant_count, []

    ensure_database_schema_current()
    with SessionLocal() as session:
        repo = CatalogRepository(session)
        for product_id, product in products.items():
            repo.replace_product_catalog(product=product, variants=variants[product_id])
        session.commit()
    return len(products), variant_count, []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--csv", required=True, type=Path, help="Path to catalog CSV file")
    parser.add_argument("--dry-run", action="store_true", help="Validate without writing to DB")
    parser.add_argument("--debug", action="store_true", help="Show full tracebacks on error")
    args = parser.parse_args()

    if not args.csv.exists():
        print(f"ERROR: CSV file not found: {args.csv}", file=sys.stderr)
        return 2

    try:
        products, variants, errors = import_catalog_csv(args.csv, dry_run=args.dry_run)
    except Exception as exc:
        if args.debug:
            raise
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    if errors:
        print("Validation failed:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    label = "Would import" if args.dry_run else "Imported"
    print(f"{label} {products} products, {variants} variants from {args.csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
