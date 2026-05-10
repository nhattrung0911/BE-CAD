from app.services.annotation_service import compute_annotations


def test_compute_annotations_returns_expected_hex_bolt_dimensions():
    annotations = compute_annotations(
        "hex_bolt",
        {"d": 8, "L": 30, "k": 5.3, "s": 13, "b": 22},
    )

    # Order: across-X dims first (d, s) then along-Z dims (L, k, b).
    # All anchored at the world origin — d-line lives at z=-1.5 (slot 0 of
    # the X-stack), s-line at z=-3.0 (slot 1).
    assert [annotation.key for annotation in annotations] == ["d", "s", "L", "k", "b"]
    d_dim = annotations[0]
    assert d_dim.from_point == [-4.0, 0.0, -1.5]
    assert d_dim.to_point == [4.0, 0.0, -1.5]
    assert d_dim.axis == "x"
    assert d_dim.plane == "XZ"

    # Length dim is along Z, anchored at radial offset = max(s/2, d/2)+pad,
    # spans the full L from origin upward — never stuck on a face.
    l_dim = annotations[2]
    assert l_dim.key == "L"
    assert l_dim.from_point[2] == 0.0
    assert l_dim.to_point[2] == 30.0
    assert l_dim.from_point[0] == l_dim.to_point[0]
    assert l_dim.from_point[0] > 13 / 2  # outside the hex flats


def test_compute_annotations_returns_empty_for_unsupported_or_invalid_input():
    assert compute_annotations("button_head", {"d": 8}) == []
    assert compute_annotations("hex_bolt", {"d": 8}) == []
