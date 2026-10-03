from __future__ import annotations

import numpy as np
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
