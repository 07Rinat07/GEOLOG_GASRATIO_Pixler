from __future__ import annotations

from importlib.resources import files

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap


_LOGO_RESOURCE = "resources/geologist-logo.png"


def logo_pixmap(maximum_size: int | None = None) -> QPixmap:
    if maximum_size is not None and maximum_size < 1:
        raise ValueError("Размер логотипа должен быть положительным")
    raw = files("geoworkbench").joinpath(_LOGO_RESOURCE).read_bytes()
    pixmap = QPixmap()
    if not pixmap.loadFromData(raw):
        raise RuntimeError("Не удалось загрузить логотип приложения")
    if maximum_size is None:
        return pixmap
    return pixmap.scaled(
        maximum_size,
        maximum_size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


def application_icon() -> QIcon:
    return QIcon(logo_pixmap())
