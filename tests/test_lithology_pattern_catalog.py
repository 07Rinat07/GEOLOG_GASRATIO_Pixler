from __future__ import annotations

from geoworkbench.tablet.lithology_pattern_catalog import (
    resolve_lithology_pattern,
    supported_pattern_keys,
)


def test_headless_pattern_catalog_resolves_legacy_bitmap_alias() -> None:
    descriptor = resolve_lithology_pattern("sandstone_bricks")

    assert descriptor.kind == "bitmap"
    assert descriptor.resolved_key == "constructor:lithology-sandstone"
    assert descriptor.asset_path is not None and descriptor.asset_path.is_file()
    assert descriptor.width_px == 16
    assert descriptor.height_px == 14
    assert len(descriptor.content_sha256 or "") == 64


def test_headless_pattern_catalog_falls_back_without_guessing() -> None:
    descriptor = resolve_lithology_pattern("vendor-unknown-pattern")

    assert descriptor.kind == "hatch"
    assert descriptor.resolved_key == "solid"
    assert "sandstone_bricks" in supported_pattern_keys()
