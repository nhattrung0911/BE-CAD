import io

import pypdf

from app.services.datasheet_service import build_datasheet_pdf


def _extract_text(data: bytes) -> str:
    reader = pypdf.PdfReader(io.BytesIO(data))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _pdf():
    return build_datasheet_pdf(
        product_name="Hex bolt ISO 4014",
        standard="ISO4014",
        sku="HEX-BOLT-ISO4014-M8X30",
        param_labels={"d": "Nominal diameter", "L": "Total length", "s": "Across flats"},
        params={"d": 8, "L": 30, "s": 13, "lod": "medium"},
    )


def test_returns_pdf_bytes():
    data = _pdf()
    assert isinstance(data, bytes)
    assert data[:5] == b"%PDF-"
    assert len(data) > 500


def test_pdf_contains_title_standard_sku_and_params():
    text = _extract_text(_pdf())
    assert "Hex bolt ISO 4014" in text
    assert "ISO4014" in text
    assert "HEX-BOLT-ISO4014-M8X30" in text
    assert "Nominal diameter" in text
    assert "13" in text  # across-flats value rendered


def test_lod_key_is_not_rendered_as_a_parameter_row():
    text = _extract_text(
        build_datasheet_pdf(
            product_name="X",
            standard="S",
            sku="SKU",
            param_labels={},
            params={"d": 8, "lod": "high"},
        )
    )
    assert "high" not in text


def test_value_formatting_drops_trailing_zeros():
    text = _extract_text(
        build_datasheet_pdf(
            product_name="X", standard="S", sku="K",
            param_labels={}, params={"m": 6.80},
        )
    )
    assert "6.8" in text
    assert "6.800" not in text
