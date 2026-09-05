from __future__ import annotations

from PySide6.QtCore import QRectF
import pytest

from geoworkbench.printing import hydrocarbon_interpretation_pdf_text as pdf_text

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


def test_tiny_final_fragment_is_rebalanced_with_previous_page() -> None:
    canvas = _CanvasProbe()
    document = _DocumentProbe()

    _draw_document_paginated(canvas, document, 105.0)  # type: ignore[arg-type]

    assert canvas.page_count == 3
    assert [clip.width() for clip in document.clips] == [100.0, 100.0, 100.0]
    assert [clip.y() for clip in document.clips] == [0.0, 50.0, 90.0]
    assert [clip.height() for clip in document.clips] == [50.0, 40.0, 15.0]
    # Without rebalancing the last page would contain only 5/50 px (10%) of
    # report content, reproducing the almost-empty pages seen in the field PDF.


@pytest.mark.parametrize("title", ["Интервал", "Аралық", "Interval"])
def test_opus_interval_heading_stays_with_basis(monkeypatch, title: str) -> None:
    heading = f"<div class='candidate-detail-heading'><b>{title}</b></div>"
    basis = "<div class='candidate-detail-basis'><p>Basis</p></div>"
    fragments: list[str] = []
    monkeypatch.setattr(
        pdf_text, "_render_atomic_html",
        lambda canvas, style, fragment: fragments.append(fragment),
    )

    pdf_text._render_html_blocks(_CanvasProbe(), "", (heading, basis))  # type: ignore[arg-type]

    assert fragments == [heading + basis]

    fragments.clear()
    section = "<h2>Details</h2>"
    pdf_text._render_html_blocks(_CanvasProbe(), "", (section, heading, basis))  # type: ignore[arg-type]
    assert fragments == [section + heading + basis]


def test_table_colgroup_widths_reach_qt_header_cells(qapp) -> None:
    from PySide6.QtGui import QTextTable, QTextLength

    parts = pdf_text._table_parts(
        '<table><colgroup><col style="width:25%"><col style="width:75%"></colgroup>'
        '<thead><tr><th>A</th><th>B</th></tr></thead>'
        '<tbody><tr><td>1</td><td>2</td></tr></tbody></table>'
    )
    document, _ = pdf_text._html_document(
        "", pdf_text._table_html(parts, parts.rows), 500, table=True,
    )
    table = next(frame for frame in document.rootFrame().childFrames() if isinstance(frame, QTextTable))
    widths = table.format().columnWidthConstraints()
    assert [width.type() for width in widths] == [QTextLength.Type.PercentageLength] * 2
    assert [width.rawValue() for width in widths] == [25, 75]


def test_gasomer_table_keeps_interval_heading_and_summary(monkeypatch) -> None:
    heading = "<h3>100-110 m</h3>"
    summary = "<p>Support: 100%</p>"
    table = "<table><tr><td>OPUS_GM_1</td></tr></table>"
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        pdf_text, "_render_table",
        lambda canvas, style, fragment, *, heading: calls.append((heading, fragment)),
    )
    pdf_text._render_html_blocks(_CanvasProbe(), "", (heading, summary, table))  # type: ignore[arg-type]
    assert calls == [(heading + summary, table)]
