import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QImage, QPainter

from geoworkbench.domain.annotation_style import AnnotationStyle
from geoworkbench.printing.report_author_symbols import (
    AUTHOR_SYMBOLS,
    AuthorSymbolId,
    paint_author_symbol,
)
from geoworkbench.services.localization import AppLanguage


@pytest.mark.parametrize("symbol", list(AuthorSymbolId))
def test_author_symbols_are_distinct_vector_shapes_and_preserve_painter(qapp, symbol):
    image = QImage(60, 60, QImage.Format.Format_ARGB32)
    image.fill(QColor("white"))
    painter = QPainter(image)
    painter.setPen(QColor("red"))
    original = painter.pen()
    try:
        paint_author_symbol(
            painter,
            QRectF(10, 10, 40, 40),
            symbol,
            AnnotationStyle(border_color="#000000", fill_color="#ffffff"),
        )
        assert painter.pen() == original
    finally:
        painter.end()
    dark = {(x, y) for x in range(60) for y in range(60) if image.pixelColor(x, y).value() < 128}
    assert dark
    assert all(10 <= x <= 50 and 10 <= y <= 50 for x, y in dark)
    if symbol is AuthorSymbolId.CIRCLE:
        assert (30, 10) in dark and (10, 10) not in dark
    elif symbol is AuthorSymbolId.SQUARE:
        assert (10, 10) in dark and (30, 10) in dark
    elif symbol is AuthorSymbolId.DIAMOND:
        assert (30, 10) in dark and (10, 30) in dark and (10, 10) not in dark
    elif symbol is AuthorSymbolId.TRIANGLE:
        assert (30, 10) in dark and (30, 49) in dark and (10, 10) not in dark
    else:
        assert (30, 30) in dark and (30, 10) not in dark


def test_author_symbol_catalog_has_unique_ids_and_three_language_labels():
    assert len({item.symbol_id for item in AUTHOR_SYMBOLS}) == len(AuthorSymbolId)
    for item in AUTHOR_SYMBOLS:
        for language in AppLanguage:
            assert item.label(language)


@pytest.mark.parametrize("symbol", list(AuthorSymbolId))
@pytest.mark.parametrize("dpi", [72, 300])
def test_author_symbol_pdf_is_vector_and_has_stable_physical_bounds(qapp, tmp_path, symbol, dpi):
    import fitz
    from PySide6.QtGui import QPdfWriter

    target = tmp_path / "symbol.pdf"
    writer = QPdfWriter(str(target))
    writer.setResolution(dpi)
    painter = QPainter(writer)
    try:
        painter.scale(dpi / 72.0, dpi / 72.0)
        paint_author_symbol(
            painter, QRectF(10, 10, 40, 40), symbol, AnnotationStyle(border_color="#000000")
        )
    finally:
        painter.end()
    with fitz.open(target) as pdf:
        page = pdf[0]
        assert page.get_images() == []
        paths = page.get_drawings()
        assert paths
        bounds = fitz.Rect(paths[0]["rect"])
        for path in paths[1:]:
            bounds |= path["rect"]
        assert bounds.width == pytest.approx(40.0, abs=0.1)
        assert bounds.height == pytest.approx(40.0, abs=0.1)


def test_author_symbol_intersects_caller_clip_and_restores_it(qapp):
    image = QImage(60, 60, QImage.Format.Format_ARGB32)
    image.fill(QColor("white"))
    painter = QPainter(image)
    painter.setClipRect(QRectF(0, 0, 30, 30))
    clip = painter.clipBoundingRect()
    try:
        paint_author_symbol(
            painter,
            QRectF(10, 10, 40, 40),
            AuthorSymbolId.CROSS,
            AnnotationStyle(border_color="#000000"),
        )
        assert painter.clipBoundingRect() == clip
    finally:
        painter.end()
    assert image.pixelColor(20, 20).value() < 128
    assert image.pixelColor(40, 40) == QColor("white")
