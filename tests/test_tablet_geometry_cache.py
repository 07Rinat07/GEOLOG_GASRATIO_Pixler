from __future__ import annotations

import numpy as np

from geoworkbench.tablet.geometry_cache import CurveGeometryCache, CurveGeometryKey


def _key(curve: str, top: float = 0.0, bottom: float = 999.0) -> CurveGeometryKey:
    return CurveGeometryKey(
        curve_id=curve,
        axis_id="md",
        values_revision=(curve, 1000),
        axis_revision=("md", 1000),
        top=top,
        bottom=bottom,
        max_points=100,
        positive_values_only=False,
    )


def test_geometry_cache_reuses_sampled_arrays() -> None:
    axis = np.arange(1000, dtype=np.float64)
    values = np.sin(axis)
    cache = CurveGeometryCache(max_entries=4)

    first = cache.get_or_build(_key("TG"), axis, values)
    second = cache.get_or_build(_key("TG"), axis, values)

    assert first[0] is second[0]
    assert first[1] is second[1]
    stats = cache.stats()
    assert stats.misses == 1
    assert stats.hits == 1
    assert stats.hit_ratio == 0.5


def test_geometry_cache_preserves_narrow_peak() -> None:
    axis = np.arange(100_000, dtype=np.float64)
    values = np.zeros_like(axis)
    values[54_321] = 2500.0
    cache = CurveGeometryCache(max_entries=4)

    sampled_values, sampled_axis = cache.get_or_build(
        CurveGeometryKey(
            curve_id="TG",
            axis_id="md",
            values_revision=("TG", values.size),
            axis_revision=("md", axis.size),
            top=0.0,
            bottom=99_999.0,
            max_points=1000,
            positive_values_only=False,
        ),
        axis,
        values,
    )

    assert float(np.max(sampled_values)) == 2500.0
    assert 54_321.0 in sampled_axis


def test_geometry_cache_is_lru_bounded_and_invalidatable() -> None:
    axis = np.arange(1000, dtype=np.float64)
    values = axis.copy()
    cache = CurveGeometryCache(max_entries=2)

    cache.get_or_build(_key("A"), axis, values)
    cache.get_or_build(_key("B"), axis, values)
    cache.get_or_build(_key("C"), axis, values)

    assert cache.stats().entries == 2
    assert cache.stats().evictions == 1
    assert cache.invalidate_curve("B") == 1
    assert cache.stats().entries == 1
