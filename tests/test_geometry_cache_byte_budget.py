from __future__ import annotations

import numpy as np
import pytest

from geoworkbench.tablet.geometry_cache import CurveGeometryCache, CurveGeometryKey


def _key(
    *,
    curve_id: str = "GR",
    values_revision: int = 1,
    axis_revision: int = 1,
    top: float = 0.0,
    bottom: float = 3.0,
) -> CurveGeometryKey:
    return CurveGeometryKey(
        curve_id=curve_id,
        axis_id="depth",
        values_revision=values_revision,
        axis_revision=axis_revision,
        top=top,
        bottom=bottom,
        max_points=64,
        positive_values_only=False,
    )


def _arrays(offset: float = 0.0) -> tuple[np.ndarray, np.ndarray]:
    axis = np.arange(4, dtype=np.float64)
    values = np.arange(4, dtype=np.float64) + offset
    return axis, values


def test_geometry_cache_accounts_numpy_payload_bytes() -> None:
    cache = CurveGeometryCache(max_entries=8, max_bytes=1024)
    axis, values = _arrays()

    cached_values, cached_axis = cache.get_or_build(_key(), axis, values)

    assert cache.entry_count == 1
    assert cache.current_bytes == cached_values.nbytes + cached_axis.nbytes == 64
    assert cache.max_bytes == 1024
    assert cache.max_entries == 8
    assert not cached_values.flags.writeable
    assert not cached_axis.flags.writeable


def test_geometry_cache_evicts_lru_entry_to_respect_byte_budget() -> None:
    cache = CurveGeometryCache(max_entries=8, max_bytes=64)
    axis, values = _arrays()

    cache.get_or_build(_key(curve_id="GR"), axis, values)
    cache.get_or_build(_key(curve_id="RHOB"), axis, values + 10.0)

    assert cache.entry_count == 1
    assert cache.current_bytes == 64
    assert cache.stats().evictions == 1

    cache.get_or_build(_key(curve_id="GR"), axis, values)
    assert cache.stats().misses == 3


def test_geometry_cache_hit_promotes_entry_before_byte_eviction() -> None:
    cache = CurveGeometryCache(max_entries=8, max_bytes=128)
    axis, values = _arrays()
    gr = _key(curve_id="GR")
    rhob = _key(curve_id="RHOB")
    nphi = _key(curve_id="NPHI")

    first_gr = cache.get_or_build(gr, axis, values)
    cache.get_or_build(rhob, axis, values + 10.0)
    second_gr = cache.get_or_build(gr, axis, values)
    cache.get_or_build(nphi, axis, values + 20.0)

    assert second_gr is first_gr
    assert cache.entry_count == 2
    assert cache.current_bytes == 128
    assert cache.stats().hits == 1
    assert cache.stats().evictions == 1

    # GR was promoted on hit and remains cached; RHOB was the least-recently used entry.
    assert cache.get_or_build(gr, axis, values) is first_gr
    cache.get_or_build(rhob, axis, values + 10.0)
    assert cache.stats().hits == 2
    assert cache.stats().misses == 4


def test_geometry_cache_does_not_retain_single_entry_larger_than_budget() -> None:
    cache = CurveGeometryCache(max_entries=8, max_bytes=32)
    axis, values = _arrays()
    key = _key()

    first = cache.get_or_build(key, axis, values)
    second = cache.get_or_build(key, axis, values)

    assert first is not second
    assert cache.entry_count == 0
    assert cache.current_bytes == 0
    assert cache.stats().misses == 2
    assert cache.stats().evictions == 0


def test_geometry_cache_clear_and_invalidate_release_accounted_bytes() -> None:
    cache = CurveGeometryCache(max_entries=8, max_bytes=1024)
    axis, values = _arrays()

    cache.get_or_build(_key(curve_id="GR"), axis, values)
    cache.get_or_build(_key(curve_id="RHOB"), axis, values + 10.0)
    assert cache.current_bytes == 128

    assert cache.invalidate_curve("GR") == 1
    assert cache.entry_count == 1
    assert cache.current_bytes == 64
    assert cache.stats().evictions == 0

    cache.clear()
    assert cache.entry_count == 0
    assert cache.current_bytes == 0


def test_geometry_cache_keeps_count_limit_independent_from_byte_budget() -> None:
    cache = CurveGeometryCache(max_entries=1, max_bytes=1024)
    axis, values = _arrays()

    cache.get_or_build(_key(curve_id="GR"), axis, values)
    cache.get_or_build(_key(curve_id="RHOB"), axis, values + 10.0)

    assert cache.entry_count == 1
    assert cache.current_bytes == 64
    assert cache.stats().evictions == 1


def test_geometry_cache_revision_changes_are_cache_misses() -> None:
    cache = CurveGeometryCache(max_entries=8, max_bytes=1024)
    axis, values = _arrays()

    cache.get_or_build(_key(values_revision=1, axis_revision=1), axis, values)
    cache.get_or_build(_key(values_revision=2, axis_revision=1), axis, values)
    cache.get_or_build(_key(values_revision=2, axis_revision=2), axis, values)

    assert cache.stats().hits == 0
    assert cache.stats().misses == 3
    assert cache.entry_count == 3


def test_geometry_cache_rejects_non_positive_limits() -> None:
    with pytest.raises(ValueError, match="Размер кэша геометрии"):
        CurveGeometryCache(max_entries=0)
    with pytest.raises(ValueError, match="Бюджет кэша геометрии"):
        CurveGeometryCache(max_bytes=0)
