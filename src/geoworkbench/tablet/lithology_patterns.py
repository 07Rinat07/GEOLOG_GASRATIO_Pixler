from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPixmap


_PATTERN_STYLES = {
    "solid": Qt.BrushStyle.SolidPattern,
    "dots": Qt.BrushStyle.Dense6Pattern,
    "dense_dots": Qt.BrushStyle.Dense4Pattern,
    "sand_dots": Qt.BrushStyle.Dense6Pattern,
    "sandstone_bricks": Qt.BrushStyle.BDiagPattern,
    "clay_dash": Qt.BrushStyle.HorPattern,
    "silt_dash": Qt.BrushStyle.Dense5Pattern,
    "gravel_circles": Qt.BrushStyle.Dense7Pattern,
    "conglomerate": Qt.BrushStyle.DiagCrossPattern,
    "carbonate": Qt.BrushStyle.CrossPattern,
    "evaporite": Qt.BrushStyle.FDiagPattern,
    "coal": Qt.BrushStyle.Dense1Pattern,
    "metamorphic": Qt.BrushStyle.DiagCrossPattern,
    "volcanic": Qt.BrushStyle.Dense3Pattern,
}


# Historical compact pattern keys are retained in old projects and form templates.
# Resolve them to the exact tiled BMP resources imported from the user's two legacy
# lithotype catalogs instead of falling back to a flat colour.
_LEGACY_BITMAP_PATTERN_ALIASES = {
    "clay_dash": "constructor:lithology-clay",
    "claystone_blocks": "constructor:lithology-claystone",
    "silt_dots": "constructor:lithology-silt",
    "siltstone_lines": "constructor:lithology-siltstone",
    "sand_dots": "constructor:lithology-sand",
    "sandstone_bricks": "constructor:lithology-sandstone",
    "gravel_circles": "constructor:lithology-gravelit",
    "conglomerate_pebbles": "constructor:lithology-conglomerate",
    "limestone_bricks": "constructor:lithology-limestone",
    "marl_ticks": "constructor:lithology-marl",
    "dolomite_rhombs": "constructor:lithology-dolomite",
    "anhydrite_chevrons": "constructor:lithology-anhydrite",
    "gypsum_arrows": "constructor:lithology-gypsum",
    "halite_crosses": "constructor:lithology-rock-salt",
    "coal_bands": "constructor:lithology-coal",
    "metamorphic_mesh": "constructor:lithology-metamorphic-rock",
    "volcanic_angles": "constructor:lithology-volcanic-rock",
}


def supported_pattern_keys() -> tuple[str, ...]:
    keys = list(_PATTERN_STYLES)
    keys.extend(_LEGACY_BITMAP_PATTERN_ALIASES)
    try:
        from geoworkbench.form_constructor.asset_install import (
            CONSTRUCTOR_PATTERN_PREFIX,
            load_factory_constructor_registry,
        )

        keys.extend(
            f"{CONSTRUCTOR_PATTERN_PREFIX}{asset.asset_id}"
            for asset in load_factory_constructor_registry().all(kind="lithology_pattern")
        )
    except (OSError, RuntimeError, ValueError):
        # The compact hatch catalog remains usable even when an installation is
        # missing the optional bitmap resource directory.
        pass
    return tuple(dict.fromkeys(keys))


@lru_cache(maxsize=256)
def _constructor_pattern_pixmap(pattern_key: str) -> QPixmap:
    from geoworkbench.form_constructor.asset_install import resolve_constructor_pattern_asset

    asset = resolve_constructor_pattern_asset(pattern_key)
    if asset is None:
        return QPixmap()
    return QPixmap(str(asset.asset_path))


def lithology_brush(color: str, pattern_key: str) -> QBrush:
    pattern_key = _LEGACY_BITMAP_PATTERN_ALIASES.get(pattern_key, pattern_key)
    parsed_color = QColor(color)
    if not parsed_color.isValid():
        parsed_color = QColor("#b0b0b0")
    if pattern_key.startswith("constructor:"):
        pixmap = _constructor_pattern_pixmap(pattern_key)
        if not pixmap.isNull():
            # QBrush repeats the source bitmap. Smooth scaling is deliberately not
            # applied because geological legacy lithotypes are pixel patterns.
            return QBrush(pixmap)
    style = _PATTERN_STYLES.get(pattern_key, Qt.BrushStyle.SolidPattern)
    return QBrush(parsed_color, style)


def masterlog_lithology_brush(
    painter: QPainter,
    color: str,
    pattern_key: str,
    *,
    reference_dpi: float = 96.0,
) -> QBrush:
    """Return a print/preview brush with a stable physical bitmap tile size.

    Masterlog is painted in millimetres and then scaled to the output device.
    A normal bitmap brush inherits that scale, so a 14x14 legacy BMP would become
    a 14x14 *millimetre* block.  Cancel the active world transform for texture
    coordinates and then reapply a 96-DPI reference scale.  One source pixel is
    therefore always 1/96 inch on screen, image preview, PDF, and printer output,
    while interval geometry remains in millimetres.
    """

    brush = lithology_brush(color, pattern_key)
    if brush.textureImage().isNull():
        return brush

    inverse, invertible = painter.worldTransform().inverted()
    if not invertible:
        return brush

    device = painter.device()
    dpi_x = float(device.logicalDpiX()) if device is not None else reference_dpi
    dpi_y = float(device.logicalDpiY()) if device is not None else reference_dpi
    safe_reference = max(1.0, float(reference_dpi))
    if not (dpi_x > 0.0):
        dpi_x = safe_reference
    if not (dpi_y > 0.0):
        dpi_y = safe_reference

    inverse.scale(dpi_x / safe_reference, dpi_y / safe_reference)
    brush.setTransform(inverse)
    return brush
