from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QComboBox, QCompleter

from geoworkbench.project.lithotype_catalog_controller import CatalogLithotype
from geoworkbench.tablet.lithology_patterns import lithology_brush


def lithotype_pixmap(
    lithotype: CatalogLithotype,
    size: QSize = QSize(42, 24),
) -> QPixmap:
    """Return a sharp tiled preview of one lithotype.

    The supplied legacy bitmaps are small repeatable geological patterns.  The
    preview therefore uses the same ``lithology_brush`` as the tablet and print
    renderer instead of reducing the choice to a flat colour chip.
    """

    return pattern_pixmap(lithotype.color, lithotype.pattern_key, size)


def pattern_pixmap(
    color: str,
    pattern_key: str,
    size: QSize = QSize(42, 24),
) -> QPixmap:
    """Render any hatch or packaged bitmap pattern into a bordered swatch."""

    width = max(8, int(size.width()))
    height = max(8, int(size.height()))
    pixmap = QPixmap(width, height)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    try:
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        rect = pixmap.rect().adjusted(1, 1, -2, -2)
        painter.fillRect(rect, lithology_brush(color, pattern_key))
        painter.setPen(QPen(QColor("#334155"), 1))
        painter.drawRect(rect)
    finally:
        painter.end()
    return pixmap


def lithotype_icon(
    lithotype: CatalogLithotype,
    size: QSize = QSize(42, 24),
) -> QIcon:
    return QIcon(lithotype_pixmap(lithotype, size))


def pattern_icon(
    color: str,
    pattern_key: str,
    size: QSize = QSize(42, 24),
) -> QIcon:
    return QIcon(pattern_pixmap(color, pattern_key, size))


def configure_lithotype_combo(combo: QComboBox, *, searchable: bool = True) -> None:
    """Configure a large lithotype selector with sharp icons.

    ``searchable=False`` preserves the compact quick-interval editor contract: the
    combo remains non-editable, while Qt still supports keyboard prefix selection.
    Full catalog and cuttings editors use the searchable completion popup.
    """

    combo.setEditable(searchable)
    combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
    combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
    combo.setMinimumContentsLength(18)
    combo.setMaxVisibleItems(28)
    completer = combo.completer() if searchable else None
    if completer is not None:
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
