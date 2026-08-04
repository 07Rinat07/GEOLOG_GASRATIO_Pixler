from __future__ import annotations

from PySide6.QtCore import qInstallMessageHandler
from PySide6.QtGui import QFont

from geoworkbench.printing.unicode_support import configure_application_unicode_fonts


def test_unicode_font_configuration_normalizes_pixel_size_sentinel(qapp) -> None:
    original = QFont(qapp.font())
    messages: list[str] = []

    def handler(_kind, _context, message: str) -> None:
        messages.append(message)

    previous = qInstallMessageHandler(handler)
    try:
        pixel_font = QFont(original)
        pixel_font.setPixelSize(13)
        qapp.setFont(pixel_font)
        assert qapp.font().pointSizeF() == -1.0

        configure_application_unicode_fonts(qapp)

        configured = qapp.font()
        assert configured.pointSizeF() > 0.0
        assert configured.pointSize() > 0
        assert configured.pixelSize() == -1

        # Model a downstream/native Qt path that copies the global point size
        # into another font. This emitted the diagnostics warning while the
        # application font still carried Qt's -1 sentinel.
        copied = QFont(configured)
        copied.setPointSize(configured.pointSize())
    finally:
        qInstallMessageHandler(previous)
        qapp.setFont(original)

    assert not any("QFont::setPointSize" in message for message in messages)
