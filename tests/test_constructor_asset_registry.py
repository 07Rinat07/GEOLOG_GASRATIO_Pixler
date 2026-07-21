from pathlib import Path

import pytest

from geoworkbench.form_constructor.asset_registry import ConstructorAssetRegistry
from geoworkbench.form_constructor.depth_symbol import DepthSymbolPlacement
from geoworkbench.form_constructor.preview_revision import PreviewRevisionGate


ASSET_ROOT = Path(__file__).resolve().parents[1] / "resources" / "constructor_assets"


def test_factory_catalog_is_valid_and_preserves_canonical_assets() -> None:
    registry = ConstructorAssetRegistry.from_root(ASSET_ROOT)
    assert len(registry.all(kind="lithology_pattern")) == 117
    assert len(registry.all(kind="depth_symbol")) == 19
    assert not registry.validate_files()


def test_symbol_search_uses_corrected_name_and_alias() -> None:
    registry = ConstructorAssetRegistry.from_root(ASSET_ROOT)
    assert registry.search("газ фоновый", kind="depth_symbol")[0].asset_id == "symbol-background-gas"
    assert registry.search("Остаточноя", kind="depth_symbol")[0].asset_id == "symbol-residual-oil-saturation"


def test_lithology_aliases_are_kept_after_image_deduplication() -> None:
    registry = ConstructorAssetRegistry.from_root(ASSET_ROOT)
    matches = registry.search("Anhydrite", kind="lithology_pattern", language="en")
    assert matches
    assert "Anhydrites" in matches[0].aliases


def test_registry_detects_asset_checksum_mismatch(tmp_path: Path) -> None:
    registry = ConstructorAssetRegistry.from_root(ASSET_ROOT)
    original = registry.get("symbol-background-gas")
    corrupted = tmp_path / "symbol.bmp"
    corrupted.write_bytes(original.asset_path.read_bytes() + b"corruption")
    from dataclasses import replace

    isolated = ConstructorAssetRegistry([replace(original, asset_path=corrupted)])
    errors = isolated.validate_files()
    assert len(errors) == 1
    assert "checksum mismatch" in errors[0]


def test_depth_symbol_stays_depth_anchored_with_manual_offset() -> None:
    placement = DepthSymbolPlacement(symbol_id="symbol-background-gas", depth=1010.0)
    moved = placement.with_manual_offset(2.0, -0.5)
    assert moved.page_y_mm(page_top_depth=1000.0, millimetres_per_depth_unit=2.0) == pytest.approx(19.5)
    assert moved.depth == 1010.0


def test_interval_symbol_rejects_reversed_depths() -> None:
    with pytest.raises(ValueError):
        DepthSymbolPlacement(symbol_id="symbol-loss", depth=1010.0, bottom_depth=1009.0)


def test_preview_revision_rejects_stale_results() -> None:
    gate = PreviewRevisionGate()
    old = gate.request()
    current = gate.request()
    assert not gate.accepts(old)
    assert gate.accepts(current)
