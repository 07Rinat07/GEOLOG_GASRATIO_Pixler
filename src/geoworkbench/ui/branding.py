from __future__ import annotations

from importlib.resources import files

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer


_LOGO_RESOURCE = "resources/digital-geolog-logo.svg"
_HOME_BACKGROUND_RESOURCE = "resources/home-geology-background.svg"


def _svg_pixmap(resource_name: str, width: int, height: int) -> QPixmap:
    if width < 1 or height < 1:
        raise ValueError("Размер изображения должен быть положительным")
    raw = files("geoworkbench").joinpath(resource_name).read_bytes()
    renderer = QSvgRenderer(raw)
    if not renderer.isValid():
        raise RuntimeError(f"Не удалось загрузить SVG-ресурс {resource_name}")
    pixmap = QPixmap(width, height)
    pixmap.fill(QColor(Qt.GlobalColor.transparent))
    painter = QPainter(pixmap)
    try:
        renderer.render(painter)
    finally:
        painter.end()
    return pixmap


def logo_pixmap(maximum_size: int | None = None) -> QPixmap:
    if maximum_size is not None and maximum_size < 1:
        raise ValueError("Размер логотипа должен быть положительным")
    target = 1254 if maximum_size is None else maximum_size
    return _svg_pixmap(_LOGO_RESOURCE, target, target)


def about_program_logo_pixmap(width: int, height: int) -> QPixmap:
    if width < 1 or height < 1:
        raise ValueError("Размер изображения должен быть положительным")
    side = min(width, height)
    return _svg_pixmap(_LOGO_RESOURCE, side, side)


def home_background_pixmap(width: int, height: int) -> QPixmap:
    """Render the owner-provided geology artwork for the decorative Home margin."""

    return _svg_pixmap(_HOME_BACKGROUND_RESOURCE, width, height)


def application_icon() -> QIcon:
    return QIcon(logo_pixmap())
