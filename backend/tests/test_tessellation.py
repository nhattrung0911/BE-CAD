import math

import pytest

from app.cad.tessellation import tessellation_for_lod, DEFAULT_LOD


SIZE = 30.0  # an M8 bolt-ish part


def test_returns_linear_and_angular_pair():
    lin, ang = tessellation_for_lod("medium", SIZE)
    assert lin > 0
    assert 0 < ang < math.pi


def test_higher_lod_is_finer_than_lower():
    lin_low, ang_low = tessellation_for_lod("low", SIZE)
    lin_med, ang_med = tessellation_for_lod("medium", SIZE)
    lin_high, ang_high = tessellation_for_lod("high", SIZE)

    # Finer LOD => smaller tolerances (both linear and angular).
    assert lin_low > lin_med > lin_high
    assert ang_low > ang_med > ang_high


def test_linear_tolerance_scales_with_part_size():
    small = tessellation_for_lod("high", 6.0)[0]
    large = tessellation_for_lod("high", 100.0)[0]
    assert large > small


def test_linear_floor_applies_to_tiny_parts():
    # A sub-millimetre part must not get an absurdly tiny (expensive) tolerance;
    # the per-tier floor caps it.
    lin = tessellation_for_lod("high", 0.1)[0]
    assert lin == pytest.approx(0.02)


def test_unknown_lod_falls_back_to_default():
    assert tessellation_for_lod("garbage", SIZE) == tessellation_for_lod(DEFAULT_LOD, SIZE)


def test_zero_or_missing_size_is_safe():
    lin, ang = tessellation_for_lod("medium", 0)
    assert lin > 0 and ang > 0
