from __future__ import annotations

import pytest
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFontMetricsF, QImage, QPainter

from geoworkbench.domain.annotation_style import AnnotationStyle
from geoworkbench.domain.report_annotations import (
    ReportAnnotationAnchor,
    ReportAnnotationKind,
    ReportAnnotationRecord,
)
from geoworkbench.printing import report_annotation_rendering as rendering
from geoworkbench.printing.unicode_support import print_font
from geoworkbench.services.localization import AppLanguage


LABELS = {
    AppLanguage.RU: "Известняк плотный с тонкими трещинами, кальцитовым заполнением и примесью глинистого материала",
    AppLanguage.KK: "Әктас тығыз, жіңішке жарықшақтары кальцитпен толтырылған, сазды материалдың қоспасы кездеседі",
    AppLanguage.EN: "Dense limestone with thin calcite-filled fractures and a minor admixture of clay material",
}


def _record(*, font_size: float = 28.0) -> ReportAnnotationRecord:
    return ReportAnnotationRecord(
        annotation_id="multilingual-well-note",
        scope_id="report:well:dataset:composition",
        kind=ReportAnnotationKind.TEXT,
        anchor=ReportAnnotationAnchor.DEPTH,
        depth=105.0,
        track_key="curve:TG",
        text="Source description must remain unchanged",
        text_i18n={language.value: text for language, text in LABELS.items()},
        style=AnnotationStyle(
            font_size=font_size,
            fill_color="#ffffff",
            border_width=0.0,
            shadow=False,
        ),
    )


@pytest.mark.parametrize("language", list(LABELS))
def test_annotation_multilingual_text_is_fitted_to_box_without_changing_source(language) -> None:
    image = QImage(500, 240, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor("#ffffff"))
    painter = QPainter(image)
    record = _record()
    content = LABELS[language]
    rect = QRectF(60.0, 55.0, 195.0, 52.0)
    font = print_font(record.style.font_size, text=content)
    font.setFamily(record.style.font_family)
    try:
        fitted = rendering._fitted_annotation_font(
            painter, font, rect, content,
            Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignLeft
            | Qt.AlignmentFlag.AlignTop,
        )
        metrics = QFontMetricsF(fitted, image)
        measure = metrics.boundingRect(
            QRectF(0.0, 0.0, rect.width(), 100_000.0),
            int(Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignLeft
                | Qt.AlignmentFlag.AlignTop),
            content,
        )
        assert fitted.pointSizeF() <= font.pointSizeF()
        assert fitted.pointSizeF() < record.style.font_size
        assert measure.width() <= rect.width() + 2.0
        assert measure.height() <= rect.height() + 2.0

        rendering._paint_text(painter, rect, content, record)
        # Glyphs must not leak outside the callout's own rectangle.
        for x, y in ((45, 60), (270, 80), (120, 40), (120, 125)):
            assert image.pixelColor(x, y) == QColor("#ffffff")
    finally:
        painter.end()
    assert record.text == "Source description must remain unchanged"
    assert record.style.font_size == 28.0
    assert record.text_i18n[language.value] == content


@pytest.mark.parametrize("language", list(LABELS))
def test_annotation_renderer_uses_only_selected_saved_language(
    monkeypatch: pytest.MonkeyPatch, language: AppLanguage,
) -> None:
    image = QImage(400, 220, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor("#ffffff"))
    painter = QPainter(image)
    observed: list[str] = []
    original = _record()

    def capture(painter, record, anchor, text, bounds, scale, **kwargs):
        observed.append(text)

    monkeypatch.setattr(rendering, "_paint_box_annotation", capture)
    try:
        count = rendering.paint_report_annotations(
            painter, (original,), language,
            page_top_depth=100.0, page_bottom_depth=110.0,
            plot_bounds=QRectF(30.0, 10.0, 340.0, 200.0),
            track_map={"curve:tg": QRectF(70.0, 10.0, 200.0, 200.0)},
        )
    finally:
        painter.end()
    assert count == 1
    assert observed == [LABELS[language]]
    assert original.text == "Source description must remain unchanged"


def test_unbreakable_label_does_not_draw_outside_its_small_box() -> None:
    image = QImage(280, 140, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor("#ffffff"))
    painter = QPainter(image)
    record = _record(font_size=48.0)
    try:
        rendering._paint_text(
            painter, QRectF(90.0, 45.0, 28.0, 14.0),
            "LONG_UNBROKEN_VENDOR_LABEL_" * 100, record,
        )
    finally:
        painter.end()
    for x, y in ((89, 52), (120, 52), (105, 44), (105, 60)):
        assert image.pixelColor(x, y) == QColor("#ffffff")
