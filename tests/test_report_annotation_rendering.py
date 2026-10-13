from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QImage, QPainter

from geoworkbench.domain.annotation_style import AnnotationStyle
from geoworkbench.domain.models import CurveData, CurveMetadata
from geoworkbench.domain.report_annotations import (
    ReportAnnotationAnchor,
    ReportAnnotationKind,
    ReportAnnotationRecord,
)
from geoworkbench.printing.report_annotation_rendering import (
    build_report_annotation_track_map,
    paint_report_annotations,
    resolve_report_annotation_track_rect,
)
from geoworkbench.services.localization import AppLanguage


pytestmark = pytest.mark.usefixtures("qapp")


def _curve() -> CurveData:
    return CurveData(
        CurveMetadata(
            "curve-tg",
            "S1500",
            "TG",
            "%",
            "Total gas",
            "dataset",
        ),
        np.asarray([1.0, 2.0, 3.0], dtype=np.float64),
    )


def _highlight(track_key: str) -> ReportAnnotationRecord:
    return ReportAnnotationRecord(
        annotation_id=f"rann-{track_key.replace(':', '-')}",
        scope_id="report:well:dataset:composition",
        kind=ReportAnnotationKind.INTERVAL_HIGHLIGHT,
        anchor=ReportAnnotationAnchor.INTERVAL,
        track_key=track_key,
        top_depth=25.0,
        bottom_depth=50.0,
        style=AnnotationStyle(
            fill_color="#ff0000",
            fill_opacity=1.0,
            border_width=0.0,
            shadow=False,
        ),
    )


def test_report_annotation_track_map_is_logical_and_fail_closed() -> None:
    panel_rect = QRectF(100.0, 20.0, 80.0, 180.0)
    cuttings_rect = QRectF(50.0, 20.0, 40.0, 180.0)
    left_depth = QRectF(0.0, 20.0, 40.0, 180.0)
    right_depth = QRectF(190.0, 20.0, 40.0, 180.0)

    mapping = build_report_annotation_track_map(
        panels=(("total", (_curve(),)),),
        panel_rects=(panel_rect,),
        geology_tracks=("cuttings",),
        geology_rects=(cuttings_rect,),
        left_depth_rect=left_depth,
        right_depth_rect=right_depth,
    )

    assert resolve_report_annotation_track_rect("curve:TG", mapping) == panel_rect
    assert resolve_report_annotation_track_rect("curve:tg", mapping) == panel_rect
    assert resolve_report_annotation_track_rect("geology:cuttings", mapping) == cuttings_rect
    assert resolve_report_annotation_track_rect("depth:left", mapping) == left_depth
    assert resolve_report_annotation_track_rect("depth:right", mapping) == right_depth
    assert resolve_report_annotation_track_rect("geology:lba", mapping) is None
    assert resolve_report_annotation_track_rect("curve:ROP", mapping) is None


def test_missing_report_annotation_track_is_not_painted_into_neighbour() -> None:
    image = QImage(240, 220, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor("#ffffff"))
    painter = QPainter(image)
    try:
        painted = paint_report_annotations(
            painter,
            (_highlight("curve:MISSING"),),
            AppLanguage.EN,
            page_top_depth=0.0,
            page_bottom_depth=100.0,
            plot_bounds=QRectF(0.0, 20.0, 230.0, 180.0),
            track_map={"curve:tg": QRectF(50.0, 20.0, 100.0, 180.0)},
        )
    finally:
        painter.end()

    assert painted == 0
    assert image.pixelColor(75, 75) == QColor("#ffffff")


def test_interval_highlight_is_clipped_to_its_track_and_depth_range() -> None:
    image = QImage(240, 220, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor("#ffffff"))
    painter = QPainter(image)
    try:
        painted = paint_report_annotations(
            painter,
            (_highlight("curve:TG"),),
            AppLanguage.EN,
            page_top_depth=0.0,
            page_bottom_depth=100.0,
            plot_bounds=QRectF(0.0, 20.0, 230.0, 180.0),
            track_map={"curve:tg": QRectF(50.0, 20.0, 100.0, 180.0)},
        )
    finally:
        painter.end()

    assert painted == 1
    assert image.pixelColor(75, 75) != QColor("#ffffff")
    assert image.pixelColor(25, 75) == QColor("#ffffff")
    assert image.pixelColor(75, 130) == QColor("#ffffff")


def test_depth_annotation_outside_page_is_skipped() -> None:
    record = ReportAnnotationRecord(
        annotation_id="rann-outside",
        scope_id="report:well:dataset:composition",
        kind=ReportAnnotationKind.CALLOUT,
        anchor=ReportAnnotationAnchor.DEPTH,
        track_key="curve:TG",
        depth=150.0,
        text="Outside",
    )
    image = QImage(240, 220, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor("#ffffff"))
    painter = QPainter(image)
    try:
        painted = paint_report_annotations(
            painter,
            (record,),
            AppLanguage.EN,
            page_top_depth=0.0,
            page_bottom_depth=100.0,
            plot_bounds=QRectF(0.0, 20.0, 230.0, 180.0),
            track_map={"curve:tg": QRectF(50.0, 20.0, 100.0, 180.0)},
        )
    finally:
        painter.end()

    assert painted == 0



def test_page_seam_depth_annotation_is_drawn_exactly_once() -> None:
    record = ReportAnnotationRecord(
        annotation_id="rann-page-seam",
        scope_id="report:well:dataset:composition",
        kind=ReportAnnotationKind.CALLOUT,
        anchor=ReportAnnotationAnchor.DEPTH,
        depth=100.0,
        text="Boundary at 100 m",
        track_key="curve:TG",
    )
    # All chart sheets except the last own [top, bottom) depths; the final
    # one also owns the well's bottom depth. The single-page preview remains
    # fully inclusive for its selected range.
    observed = []
    for top, bottom, include_bottom in (
        (0.0, 100.0, False),
        (100.0, 200.0, False),
        (200.0, 300.0, True),
    ):
        image = QImage(240, 220, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(QColor("#ffffff"))
        painter = QPainter(image)
        try:
            observed.append(
                paint_report_annotations(
                    painter, (record,), AppLanguage.RU,
                    page_top_depth=top, page_bottom_depth=bottom,
                    plot_bounds=QRectF(0.0, 20.0, 230.0, 180.0),
                    track_map={"curve:tg": QRectF(50.0, 20.0, 100.0, 180.0)},
                    include_bottom_depth=include_bottom,
                )
            )
        finally:
            painter.end()
    assert observed == [0, 1, 0]
    image = QImage(240, 220, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor("#ffffff"))
    painter = QPainter(image)
    try:
        assert paint_report_annotations(
            painter, (record,), AppLanguage.RU,
            page_top_depth=0.0, page_bottom_depth=100.0,
            plot_bounds=QRectF(0.0, 20.0, 230.0, 180.0),
            track_map={"curve:tg": QRectF(50.0, 20.0, 100.0, 180.0)},
        ) == 1  # legacy inclusive preview
    finally:
        painter.end()


def test_last_chart_page_keeps_annotation_on_final_depth() -> None:
    record = ReportAnnotationRecord(
        annotation_id="rann-last-bottom",
        scope_id="report:well:dataset:composition",
        kind=ReportAnnotationKind.TEXT,
        anchor=ReportAnnotationAnchor.DEPTH,
        depth=300.0, text="Final depth",
    )
    image = QImage(240, 220, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor("#ffffff"))
    painter = QPainter(image)
    try:
        assert paint_report_annotations(
            painter, (record,), AppLanguage.EN,
            page_top_depth=200.0, page_bottom_depth=300.0,
            plot_bounds=QRectF(0.0, 20.0, 230.0, 180.0),
            track_map={},
            include_bottom_depth=True,
        ) == 1
    finally:
        painter.end()


def test_zero_thickness_interval_touch_at_page_seam_is_not_painted() -> None:
    record = _highlight("curve:TG")
    image = QImage(240, 220, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor("#ffffff"))
    painter = QPainter(image)
    try:
        # The interval begins at 25 m; a sheet ending at 25 m contains no
        # positive-thickness part of that interval.
        assert paint_report_annotations(
            painter, (record,), AppLanguage.EN,
            page_top_depth=0.0, page_bottom_depth=25.0,
            plot_bounds=QRectF(0.0, 20.0, 230.0, 180.0),
            track_map={"curve:tg": QRectF(50.0, 20.0, 100.0, 180.0)},
            include_bottom_depth=False,
        ) == 0
    finally:
        painter.end()


def test_actual_multi_page_pdf_forwards_page_seam_ownership(qapp, tmp_path, monkeypatch) -> None:
    from geoworkbench.printing import hydrocarbon_interpretation_pdf_chart_enhanced as printed
    from geoworkbench.printing.hydrocarbon_interpretation_report import (
        export_hydrocarbon_interpretation_pdf,
    )
    from geoworkbench.services.hydrocarbon_interpretation import (
        build_hydrocarbon_interpretation_report,
    )
    from test_interpretation_report_charts import _session_with_report_curves

    session = _session_with_report_curves(depth_span=600.0, samples=121)
    dataset = session.current_dataset
    assert dataset is not None
    report = build_hydrocarbon_interpretation_report(session)
    record = ReportAnnotationRecord(
        annotation_id="rann-pdf-seam",
        scope_id="report:well:dataset:composition",
        kind=ReportAnnotationKind.TEXT,
        anchor=ReportAnnotationAnchor.DEPTH,
        depth=float(dataset.depth[30]),
        text="Real chart note",
    )
    observed = []
    paint = printed.paint_report_annotations

    def capture(*args, **kwargs):
        observed.append((
            kwargs["page_top_depth"], kwargs["page_bottom_depth"],
            kwargs["include_bottom_depth"],
        ))
        return paint(*args, **kwargs)

    monkeypatch.setattr(printed, "paint_report_annotations", capture)
    target = tmp_path / "page-seams.pdf"
    result = export_hydrocarbon_interpretation_pdf(
        report, target, dataset=dataset, include_chart=True,
        annotations=(record,), target_depth_per_page=100.0,
    )
    assert result.is_file()
    assert len(observed) >= 2
    assert all(a < b for a, b, _ in observed)
    assert all(a[1] == pytest.approx(b[0]) for a, b in zip(observed, observed[1:]))
    assert [item[2] for item in observed] == [
        *(False for _ in observed[:-1]), True,
    ]


@pytest.mark.parametrize("language", list(AppLanguage))
def test_symbol_uses_catalog_painter_and_print_selection(qapp, language) -> None:
    from dataclasses import replace
    from geoworkbench.domain.report_author_symbols import AuthorSymbolId

    record = ReportAnnotationRecord("symbol", "report:well:dataset:composition",
                                    ReportAnnotationKind.SYMBOL, ReportAnnotationAnchor.DEPTH,
                                    depth=50.0, symbol_id=AuthorSymbolId.CROSS,
                                    style=AnnotationStyle(border_color="#000000", shadow=False))
    image = QImage(200, 200, QImage.Format.Format_ARGB32)
    image.fill(QColor("white"))
    painter = QPainter(image)
    try:
        args = dict(page_top_depth=0.0, page_bottom_depth=100.0,
                    plot_bounds=QRectF(10, 10, 180, 180), track_map={})
        assert paint_report_annotations(painter, [replace(record, print_enabled=False)], language, **args) == 0
        assert image.pixelColor(100, 100) == QColor("white")
        assert paint_report_annotations(painter, [record], language, **args) == 1
    finally:
        painter.end()
    assert image.pixelColor(100, 100) != QColor("white")
    assert image.pixelColor(0, 0) == QColor("white")
