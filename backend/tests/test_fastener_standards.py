"""Dimensional accuracy guard for the seeded fastener catalog.

Every seeded variant must match the published ISO/DIN reference dimensions.
These are engineering drawings — values must be exactly standard-correct.

Sources (verified):
- ISO 4014:2011 hex bolt  — width across flats s, head height k
- ISO 4032:2012 hex nut   — width across flats s, nut height m
- DIN 6330 high nut (1.5d) — width across flats s, nut height m
- ISO 7380-1 button head  — head dia dk, head height k, socket s, socket depth t
- ISO 7089 / DIN 125 washer, GB 891 retaining ring

Across-flats use current ISO values (M10=16, M12=18, M14=21), NOT the legacy
pre-harmonization DIN values (17/19/22).
"""

import pytest

from app.services.demo_catalog import DemoCatalogSource

source = DemoCatalogSource()


def _params(variant_id: str) -> dict:
    return dict(source.get_variant(variant_id).params)


# (variant_id, {param: expected_value}) — only the standard-defined dims.
ISO4014_HEX_BOLT = [
    ("hex-bolt-iso4014-m8x30", {"d": 8, "s": 13, "k": 5.3, "b": 22}),
    ("hex-bolt-iso4014-m8x40", {"d": 8, "s": 13, "k": 5.3, "b": 22}),
    ("hex-bolt-iso4014-m10x40", {"d": 10, "s": 16, "k": 6.4, "b": 26}),
    ("hex-bolt-iso4014-m12x50", {"d": 12, "s": 18, "k": 7.5, "b": 30}),
]

DIN931_HEX_BOLT = [
    ("hex-bolt-din931-m8x35", {"d": 8, "s": 13, "k": 5.3}),
    ("hex-bolt-din931-m10x45", {"d": 10, "s": 16, "k": 6.4}),
]

DIN933_HEX_BOLT = [
    ("hex-bolt-din933-m1_6x2", {"d": 1.6, "s": 3.2, "k": 1.1}),
    ("hex-bolt-din933-m6x16", {"d": 6, "s": 10, "k": 4.0}),
    ("hex-bolt-din933-m8x20", {"d": 8, "s": 13, "k": 5.3}),
]

ISO4032_HEX_NUT = [
    ("hex-nut-iso4032-m6", {"d": 6, "s": 10.0, "m": 5.2}),
    ("hex-nut-iso4032-m8", {"d": 8, "s": 13.0, "m": 6.8}),
    ("hex-nut-iso4032-m10", {"d": 10, "s": 16.0, "m": 8.4}),
    ("hex-nut-iso4032-m12", {"d": 12, "s": 18.0, "m": 10.8}),
    ("hex-nut-iso4032-m14", {"d": 14, "s": 21.0, "m": 12.8}),
    ("hex-nut-iso4032-m16", {"d": 16, "s": 24.0, "m": 14.8}),
    ("hex-nut-iso4032-m20", {"d": 20, "s": 30.0, "m": 18.0}),
    ("hex-nut-iso4032-m24", {"d": 24, "s": 36.0, "m": 21.5}),
]

# DIN 6330 hexagon nut, height = 1.5d. No M5 exists in the standard.
DIN6330_HIGH_NUT = [
    ("hex-nut-din6330-m8", {"d": 8, "s": 13.0, "m": 12.0}),
    ("hex-nut-din6330-m10", {"d": 10, "s": 16.0, "m": 15.0}),
    ("hex-nut-din6330-m12", {"d": 12, "s": 18.0, "m": 18.0}),
]

ISO7380_BUTTON_HEAD = [
    ("button-head-iso7380-m3x6", {"d": 3, "dk": 5.7, "k": 1.65, "s": 2.0, "t": 1.04}),
    ("button-head-iso7380-m5x10", {"d": 5, "dk": 9.5, "k": 2.75, "s": 3.0, "t": 1.56}),
    ("button-head-iso7380-m8x16", {"d": 8, "dk": 14.0, "k": 4.4, "s": 5.0, "t": 2.6}),
]

ISO7089_WASHER = [
    ("washer-iso7089-m8", {"OD": 16, "ID": 8.4, "h": 1.6}),
    ("washer-iso7089-m10", {"OD": 20, "ID": 10.5, "h": 2.0}),
]

GB891_RETAINING_RING = [
    ("retaining-ring-gb891-100", {"OD": 100, "d1": 74, "h": 3.0}),
]

ALL_CASES = (
    ISO4014_HEX_BOLT
    + DIN931_HEX_BOLT
    + DIN933_HEX_BOLT
    + ISO4032_HEX_NUT
    + DIN6330_HIGH_NUT
    + ISO7380_BUTTON_HEAD
    + ISO7089_WASHER
    + GB891_RETAINING_RING
)


@pytest.mark.parametrize("variant_id,expected", ALL_CASES)
def test_seeded_variant_matches_published_standard(variant_id, expected):
    actual = _params(variant_id)
    for key, want in expected.items():
        assert key in actual, f"{variant_id} missing param {key!r}"
        assert actual[key] == pytest.approx(want), (
            f"{variant_id}: {key}={actual[key]} but standard requires {want}"
        )


def test_din6330_has_no_m5_variant():
    """DIN 6330 does not define M5 — the old ISO4033 M5 must be gone."""
    with pytest.raises(KeyError):
        source.get_variant("hex-nut-din6330-m5")
    with pytest.raises(KeyError):
        source.get_variant("hex-nut-iso4033-m5")
