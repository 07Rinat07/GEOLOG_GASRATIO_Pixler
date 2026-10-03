from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import atan2, cos, radians, sin

from PySide6.QtCore import QLineF, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF

from geoworkbench.domain.localized_content import localized_text
from geoworkbench.domain.models import CurveData
from geoworkbench.domain.report_annotations import (
    ReportAnnotationAnchor,
    ReportAnnotationKind,
    ReportAnnotationRecord,
)
from geoworkbench.printing.unicode_support import print_font
from geoworkbench.services.localization import AppLanguage


REFERENCE_PIXEL_TO_POINT = 72.0 / 96.0


def build_report_annotation_track_map(
    *,
    panels: Sequence[tuple[str, tuple[CurveData, ...]]],
    panel_rects: Sequence[QRectF],
    geology_tracks: Sequence[str],
    geology_rects: Sequence[QRectF],
    left_depth_rect: QRectF,
    right_depth_rect: QRectF,
) -> dict[str, QRectF]:
    """Map logical report track keys to concrete plot rectangles.

    The mapping is fail-closed: only tracks present in this rendered snapshot
    are exposed. Missing tracks never fall back to a neighbour.
    """

    mapping: dict[str, QRectF] = {
        "depth:left": QRectF(left_depth_rect),
        "depth:right": QRectF(right_depth_rect),
    }
    for name, rect in zip(geology_tracks, geology_rects, strict=True):
        if name == "cuttings":
            mapping["geology:cuttings"] = QRectF(rect)
        elif name == "lba":
            mapping["geology:lba"] = QRectF(rect)

    for (_panel_name, curves), rect in zip(panels, panel_rects, strict=True):
        for curve in curves:
            mnemonic = (
                curve.metadata.canonical_mnemonic
                or curve.metadata.original_mnemonic
            ).strip()
            if mnemonic:
                mapping.setdefault(f"curve:{mnemonic.casefold()}", QRectF(rect))
    return mapping


def resolve_report_annotation_track_rect(
    track_key: str | None,
    track_map: Mapping[str, QRectF],
) -> QRectF | None:
    if track_key is None:
        return None
    key = track_key.strip().casefold()
    rect = track_map.get(key)
    return QRectF(rect) if rect is not None else None


def paint_report_annotations(
    painter: QPainter,
    annotations: Sequence[ReportAnnotationRecord],
    language: AppLanguage,
    *,
    page_top_depth: float,
    page_bottom_depth: float,
    plot_bounds: QRectF,
    track_map: Mapping[str, QRectF],
    pixel_scale: float = 1.0,
) -> int:
    """Paint one report-annotation snapshot over a depth chart.

    Annotation geometry is clipped to the plot bounds so title, legend, footer
    and page-number areas remain reserved. Returns the number of painted records.
    """

    if page_bottom_depth <= page_top_depth or plot_bounds.isEmpty():
        return 0
    scale = float(pixel_scale)
    if scale <= 0.0:
        raise ValueError("pixel_scale must be positive")

    painted = 0
    painter.save()
    painter.setClipRect(plot_bounds)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
    try:
        for record in annotations:
            if not record.visible or not record.print_enabled:
                continue
            target = _target_rect(record, plot_bounds, track_map)
            if target is None or target.isEmpty():
                continue

            if record.anchor is ReportAnnotationAnchor.INTERVAL:
                assert record.top_depth is not None
                assert record.bottom_depth is not None
                overlap_top = max(page_top_depth, record.top_depth)
                overlap_bottom = min(page_bottom_depth, record.bottom_depth)
                if overlap_bottom < overlap_top:
                    continue
                top_y = _depth_y(overlap_top, page_top_depth, page_bottom_depth, target)
                bottom_y = _depth_y(overlap_bottom, page_top_depth, page_bottom_depth, target)
                interval_rect = QRectF(
                    target.left(),
                    min(top_y, bottom_y),
                    target.width(),
                    abs(bottom_y - top_y),
                )
                if record.kind is ReportAnnotationKind.INTERVAL_HIGHLIGHT:
                    _paint_interval_highlight(painter, interval_rect, record)
                    painted += 1
                    continue
                anchor = QPointF(
                    target.left() + target.width() * record.x_fraction,
                    (top_y + bottom_y) / 2.0,
                )
            elif record.anchor is ReportAnnotationAnchor.DEPTH:
                assert record.depth is not None
                if not page_top_depth <= record.depth <= page_bottom_depth:
                    continue
                anchor = QPointF(
                    target.left() + target.width() * record.x_fraction,
                    _depth_y(record.depth, page_top_depth, page_bottom_depth, target),
                )
            else:
                anchor = QPointF(
                    target.left() + target.width() * record.x_fraction,
                    target.center().y(),
                )

            text = localized_text(
                record.text_i18n,
                language,
                legacy=record.text,
            )
            if record.kind is ReportAnnotationKind.ARROW:
                _paint_arrow_annotation(
                    painter,
                    record,
                    anchor,
                    text,
                    plot_bounds,
                    scale,
                )
            else:
                _paint_box_annotation(
                    painter,
                    record,
                    anchor,
                    text,
                    plot_bounds,
                    scale,
                    draw_leader=record.kind is ReportAnnotationKind.CALLOUT,
                )
            painted += 1
    finally:
        painter.restore()
    return painted


def _target_rect(
    record: ReportAnnotationRecord,
    plot_bounds: QRectF,
    track_map: Mapping[str, QRectF],
) -> QRectF | None:
    if record.track_key is None:
        return QRectF(plot_bounds)
    return resolve_report_annotation_track_rect(record.track_key, track_map)


def _depth_y(
    depth: float,
    page_top_depth: float,
    page_bottom_depth: float,
    rect: QRectF,
) -> float:
    fraction = (depth - page_top_depth) / (page_bottom_depth - page_top_depth)
    return rect.top() + fraction * rect.height()


def _paint_interval_highlight(
    painter: QPainter,
    rect: QRectF,
    record: ReportAnnotationRecord,
) -> None:
    style = record.style
    fill = _color(style.fill_color, "#fff7ed")
    fill.setAlphaF(min(1.0, max(0.0, style.fill_opacity)))
    painter.setBrush(fill)
    painter.setPen(
        QPen(
            _color(style.border_color, "#ea580c"),
            max(0.0, style.border_width),
            _pen_style(style.border_style),
        )
        if style.border_width > 0.0
        else Qt.PenStyle.NoPen
    )
    painter.drawRect(rect)


def _paint_arrow_annotation(
    painter: QPainter,
    record: ReportAnnotationRecord,
    anchor: QPointF,
    text: str,
    bounds: QRectF,
    scale: float,
) -> None:
    style = record.style
    endpoint = QPointF(
        anchor.x() + record.offset_x * scale,
        anchor.y() + record.offset_y * scale,
    )
    endpoint.setX(min(max(endpoint.x(), bounds.left()), bounds.right()))
    endpoint.setY(min(max(endpoint.y(), bounds.top()), bounds.bottom()))

    pen = QPen(
        _color(style.leader_color, "#2563eb"),
        max(0.6, style.leader_width * scale),
        _pen_style(style.leader_style),
    )
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawLine(QLineF(endpoint, anchor))
    _paint_arrow_head(
        painter,
        endpoint,
        anchor,
        style.arrow_style,
        _color(style.leader_color, "#2563eb"),
        max(4.0 * scale, 2.5),
    )
    if text:
        _paint_box_annotation(
            painter,
            record,
            endpoint,
            text,
            bounds,
            scale,
            draw_leader=False,
            use_offsets=False,
        )


def _paint_box_annotation(
    painter: QPainter,
    record: ReportAnnotationRecord,
    anchor: QPointF,
    text: str,
    bounds: QRectF,
    scale: float,
    *,
    draw_leader: bool,
    use_offsets: bool = True,
) -> None:
    style = record.style
    width = min(max(record.width * scale, 1.0), bounds.width())
    height = min(max(record.height * scale, 1.0), bounds.height())
    offset_x = record.offset_x * scale if use_offsets else 0.0
    offset_y = record.offset_y * scale if use_offsets else 0.0
    box = QRectF(anchor.x() + offset_x, anchor.y() + offset_y, width, height)
    box = _clamp_rect(box, bounds)

    if draw_leader:
        endpoint = _nearest_point_on_rect(anchor, box)
        pen = QPen(
            _color(style.leader_color, "#2563eb"),
            max(0.6, style.leader_width * scale),
            _pen_style(style.leader_style),
        )
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawLine(QLineF(anchor, endpoint))
        _paint_arrow_head(
            painter,
            endpoint,
            anchor,
            style.arrow_style,
            _color(style.leader_color, "#2563eb"),
            max(4.0 * scale, 2.5),
        )

    painter.save()
    try:
        if style.rotation:
            painter.translate(box.center())
            painter.rotate(style.rotation)
            painter.translate(-box.center())

        radius = max(0.0, style.corner_radius * scale)
        if style.shadow:
            shadow = QColor("#0f172a")
            shadow.setAlpha(min(110, int(30 + style.shadow_blur * 5)))
            shadow_box = box.translated(
                style.shadow_offset_x * scale,
                style.shadow_offset_y * scale,
            )
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(shadow)
            painter.drawRoundedRect(shadow_box, radius, radius)

        fill = _color(style.fill_color, "#ffffff")
        fill.setAlphaF(min(1.0, max(0.0, style.fill_opacity)))
        painter.setBrush(fill)
        painter.setPen(
            QPen(
                _color(style.border_color, "#2563eb"),
                max(0.0, style.border_width * scale),
                _pen_style(style.border_style),
            )
            if style.border_width > 0.0
            else Qt.PenStyle.NoPen
        )
        painter.drawRoundedRect(box, radius, radius)

        padding = max(0.0, style.padding * scale)
        content = box.adjusted(padding, padding, -padding, -padding)
        _paint_text(painter, content, text, record)
    finally:
        painter.restore()


def _paint_text(
    painter: QPainter,
    rect: QRectF,
    text: str,
    record: ReportAnnotationRecord,
) -> None:
    style = record.style
    font = print_font(style.font_size, text=text)
    if style.font_family.strip():
        font.setFamily(style.font_family)
    font.setBold(style.bold)
    font.setItalic(style.italic)
    font.setUnderline(style.underline)
    painter.setFont(font)
    painter.setPen(_color(style.text_color, "#0f172a"))
    flags = Qt.TextFlag.TextWordWrap
    flags |= {
        "left": Qt.AlignmentFlag.AlignLeft,
        "center": Qt.AlignmentFlag.AlignHCenter,
        "right": Qt.AlignmentFlag.AlignRight,
    }.get(style.alignment, Qt.AlignmentFlag.AlignLeft)
    flags |= {
        "top": Qt.AlignmentFlag.AlignTop,
        "center": Qt.AlignmentFlag.AlignVCenter,
        "bottom": Qt.AlignmentFlag.AlignBottom,
    }.get(style.vertical_alignment, Qt.AlignmentFlag.AlignTop)
    painter.drawText(rect, flags, text)


def _clamp_rect(rect: QRectF, bounds: QRectF) -> QRectF:
    left = min(max(rect.left(), bounds.left()), bounds.right() - rect.width())
    top = min(max(rect.top(), bounds.top()), bounds.bottom() - rect.height())
    return QRectF(left, top, rect.width(), rect.height())


def _nearest_point_on_rect(point: QPointF, rect: QRectF) -> QPointF:
    x = min(max(point.x(), rect.left()), rect.right())
    y = min(max(point.y(), rect.top()), rect.bottom())
    if rect.contains(point):
        candidates = (
            QPointF(rect.left(), point.y()),
            QPointF(rect.right(), point.y()),
            QPointF(point.x(), rect.top()),
            QPointF(point.x(), rect.bottom()),
        )
        return min(
            candidates,
            key=lambda candidate: (
                (candidate.x() - point.x()) ** 2 + (candidate.y() - point.y()) ** 2
            ),
        )
    return QPointF(x, y)


def _paint_arrow_head(
    painter: QPainter,
    tip: QPointF,
    tail: QPointF,
    arrow_style: str,
    color: QColor,
    size: float,
) -> None:
    if arrow_style == "none":
        return
    angle = atan2(tail.y() - tip.y(), tail.x() - tip.x())
    if arrow_style == "circle":
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(tip, size * 0.55, size * 0.55)
        return
    left = QPointF(
        tip.x() + cos(angle + radians(28.0)) * size,
        tip.y() + sin(angle + radians(28.0)) * size,
    )
    right = QPointF(
        tip.x() + cos(angle - radians(28.0)) * size,
        tip.y() + sin(angle - radians(28.0)) * size,
    )
    painter.setPen(QPen(color, max(0.8, size * 0.15)))
    if arrow_style == "open":
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawLine(QLineF(tip, left))
        painter.drawLine(QLineF(tip, right))
        return
    painter.setBrush(color)
    painter.drawPolygon(QPolygonF((tip, left, right)))


def _pen_style(value: str) -> Qt.PenStyle:
    return {
        "solid": Qt.PenStyle.SolidLine,
        "dash": Qt.PenStyle.DashLine,
        "dot": Qt.PenStyle.DotLine,
    }.get(value, Qt.PenStyle.SolidLine)


def _color(value: str, default: str) -> QColor:
    color = QColor(value)
    return color if color.isValid() else QColor(default)


__all__ = [
    "REFERENCE_PIXEL_TO_POINT",
    "build_report_annotation_track_map",
    "paint_report_annotations",
    "resolve_report_annotation_track_rect",
]
