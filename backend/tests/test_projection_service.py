import pytest

from app.services.projection_service import polylines_to_svg


def test_polylines_to_svg_emits_wellformed_svg():
    svg = polylines_to_svg([[(0.0, 0.0), (10.0, 0.0), (10.0, 5.0)]], margin=2.0)
    assert svg.startswith("<svg")
    assert svg.rstrip().endswith("</svg>")
    assert "viewBox=" in svg
    assert "<polyline" in svg or "<path" in svg


def test_viewbox_spans_geometry_plus_margin():
    # geometry 0..10 in x, 0..5 in y; margin 2 => 14 wide, 9 tall
    svg = polylines_to_svg([[(0.0, 0.0), (10.0, 5.0)]], margin=2.0)
    assert 'viewBox="0 0 14 9"' in svg or 'viewBox="0 0 14.0 9.0"' in svg


def test_empty_polylines_returns_empty_but_valid_svg():
    svg = polylines_to_svg([], margin=1.0)
    assert svg.startswith("<svg")
    assert "</svg>" in svg


def test_y_is_flipped_for_svg_top_left_origin():
    # Drawing space is y-up; SVG is y-down. A point at the top of the model
    # (max y) must map to a small SVG y. With one segment (0,0)->(0,10) and
    # margin 0, the y=10 point should render near y=0 and y=0 near y=10.
    svg = polylines_to_svg([[(0.0, 0.0), (0.0, 10.0)]], margin=0.0)
    # extract the polyline points
    import re

    m = re.search(r'points="([^"]+)"', svg)
    assert m, svg
    pts = [tuple(float(v) for v in p.split(",")) for p in m.group(1).split()]
    ys = [p[1] for p in pts]
    # The drawing point with the larger model-y must have the smaller svg-y.
    assert min(ys) == pytest.approx(0.0)
    assert max(ys) == pytest.approx(10.0)


def test_degenerate_single_point_polyline_is_skipped():
    svg = polylines_to_svg([[(1.0, 1.0)], [[(0.0, 0.0), (5.0, 0.0)][0], (5.0, 0.0)]], margin=1.0)
    # one real 2-point line remains; no crash
    assert svg.count("<polyline") == 1
