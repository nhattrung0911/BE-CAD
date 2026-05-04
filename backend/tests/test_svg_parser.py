from app.ingestion.svg_parser import parse_svg_dimension_labels


def test_parse_svg_dimension_labels():
    html = "<text>h:6.8-7.2</text><text>d1:12.8-13.2</text><text>OD:99.8-100.2</text>"
    labels = parse_svg_dimension_labels(html)
    assert labels["h"]["min"] == 6.8
    assert labels["d1"]["max"] == 13.2
    assert labels["OD"]["min"] == 99.8
