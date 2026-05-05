from app.services.annotation_service import compute_annotations


def test_compute_annotations_returns_expected_hex_bolt_dimensions():
    annotations = compute_annotations(
        "hex_bolt",
        {"d": 8, "L": 30, "k": 5.3, "s": 13, "b": 22},
    )

    assert [annotation.key for annotation in annotations] == ["d", "L", "k", "s", "b"]
    assert annotations[0].from_point == [-4.0, 0.0, 9.3]
    assert annotations[0].to_point == [4.0, 0.0, 9.3]
    assert annotations[0].plane == "XZ"


def test_compute_annotations_returns_empty_for_unsupported_or_invalid_input():
    assert compute_annotations("button_head", {"d": 8}) == []
    assert compute_annotations("hex_bolt", {"d": 8}) == []
