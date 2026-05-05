from pathlib import Path
import shutil

from scripts import bulk_import_glb


def test_read_from_dir_deduplicates_case_insensitive_glb_matches():
    tmp_path = Path(__file__).resolve().parents[1] / "pytest_tmp_root" / "bulk_import_glb"
    if tmp_path.exists():
        shutil.rmtree(tmp_path)
    tmp_path.mkdir(parents=True, exist_ok=True)

    good = tmp_path / "hex-special-m8.glb"
    bad = tmp_path / "bad.GLB"
    good.write_bytes(b"glTF" + b"12345678")
    bad.write_bytes(b"NOPE" + b"1234")

    mapping_csv = tmp_path / "mapping.csv"
    mapping_csv.write_text(
        "filename,product_id,license_status\n"
        "hex-special-m8.glb,hex-special-m8-iso,approved\n"
        "bad.GLB,bad-product,pending\n",
        encoding="utf-8",
    )

    mapping = bulk_import_glb.load_mapping(mapping_csv)

    items = list(bulk_import_glb.read_from_dir(tmp_path, mapping))
    filenames = [item.filename for item in items]

    assert filenames == ["bad.GLB", "hex-special-m8.glb"]


def test_upload_item_dry_run_reports_glb_magic_validation():
    valid = bulk_import_glb.ImportItem(
        filename="valid.glb",
        product_id="hex-special-m8-iso",
        data=b"glTF" + b"1234",
        license_status="approved",
    )
    invalid = bulk_import_glb.ImportItem(
        filename="invalid.glb",
        product_id="bad-product",
        data=b"NOPE" + b"1234",
    )

    valid_result = bulk_import_glb.upload_item(valid, "http://localhost:8000", "", dry_run=True)
    invalid_result = bulk_import_glb.upload_item(invalid, "http://localhost:8000", "", dry_run=True)

    assert valid_result["status"] == "DRY_RUN:valid"
    assert valid_result["valid_glb"] is True
    assert invalid_result["status"] == "DRY_RUN:invalid_magic"
    assert invalid_result["valid_glb"] is False
