from __future__ import annotations

from PySide6.QtCore import QRectF

from geoworkbench.printing.hydrocarbon_interpretation_pdf_text import (
    _draw_document_paginated,
)


class _PainterWithoutScale:
    def __init__(self) -> None:
        self.translations: list[tuple[float, float]] = []

    def save(self) -> None:
        return None

    def restore(self) -> None:
        return None

    def translate(self, x: float, y: float) -> None:
        self.translations.append((float(x), float(y)))


class _DocumentProbe:
    def __init__(self) -> None:
        self.clips: list[QRectF] = []

    def drawContents(self, painter: object, clip: QRectF) -> None:  # noqa: N802 - Qt API
        del painter
        self.clips.append(QRectF(clip))


class _CanvasProbe:
    def __init__(self) -> None:
        self.content_rect = QRectF(0.0, 0.0, 100.0, 50.0)
        self.y = self.content_rect.top()
        self.painter = _PainterWithoutScale()
        self.page_count = 1

    @property
    def remaining_height(self) -> float:
        return max(0.0, self.content_rect.bottom() - self.y)

    def new_page(self) -> None:
        self.page_count += 1
        self.y = self.content_rect.top()

    def advance(self, height: float, spacing: float = 5.0) -> None:
        self.y += height + spacing


def test_oversized_document_is_vertically_paginated_without_width_scaling() -> None:
    canvas = _CanvasProbe()
    document = _DocumentProbe()

    _draw_document_paginated(canvas, document, 120.0)  # type: ignore[arg-type]

    assert canvas.page_count == 3
    assert len(document.clips) == 3
    assert [clip.width() for clip in document.clips] == [100.0, 100.0, 100.0]
    assert [clip.y() for clip in document.clips] == [0.0, 50.0, 100.0]
    assert [clip.height() for clip in document.clips] == [50.0, 50.0, 20.0]
    # The painter probe intentionally has no scale() method. Any regression to
    # uniform X/Y shrinking fails this test with AttributeError before asserts.
