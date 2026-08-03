from __future__ import annotations

from PySide6.QtCore import QPoint, QRectF, Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import QWidget

from geoworkbench.printing.print_layout import (
    REFERENCE_PRINT_DPI,
    PrintContinuationSlice,
    PrintScaleMode,
)
from geoworkbench.printing.tablet_print import (
    TabletPrintError,
    TabletPrintSnapshot,
    capture_tablet_print_snapshot,
    paint_tablet_header_repeat,
    paint_tablet_snapshot,
    tablet_header_gap_height,
)
from geoworkbench.tablet.tablet_view import TabletView


class PageRenderError(RuntimeError):
    pass


_MIN_HIGH_QUALITY_RASTER_SCALE = 2.5


def _tablet_raster_scale(requested_scale: float, *, high_quality: bool) -> float:
    if not high_quality:
        return 1.0
    return min(4.0, max(_MIN_HIGH_QUALITY_RASTER_SCALE, float(requested_scale)))


def _print_page_aspect_ratio(painter: QPainter, content_rect: QRectF) -> float:
    """Return a page-stable aspect ratio for adaptive tablet column widths."""

    device = painter.device()
    if device is not None:
        width = float(device.width())
        height = float(device.height())
        if width > 0.0 and height > 0.0:
            return width / height
    return content_rect.width() / content_rect.height()


def paint_widget_page(
    widget: QWidget,
    painter: QPainter,
    content_rect: QRectF,
    *,
    fit_form_columns: bool = True,
    scale_mode: PrintScaleMode = PrintScaleMode.FIT,
    continuation: PrintContinuationSlice | None = None,
    high_quality: bool = True,
    show_column_header: bool = True,
    repeat_column_header_at_bottom: bool = False,
    included_track_ids: tuple[str, ...] | None = None,
    grid_print_overrides: tuple[tuple[str, bool], ...] = (),
    target_content_height: int | None = None,
    layout_content_height: int | None = None,
    page_aspect_ratio: float | None = None,
) -> None:
    """Render a chart/tablet into one deterministic paper continuation."""

    width = widget.width()
    height = widget.height()
    if width <= 0 or height <= 0:
        raise PageRenderError("Визуализация не имеет допустимого размера")
    if content_rect.width() <= 0 or content_rect.height() <= 0:
        raise PageRenderError("Устройство печати не предоставило допустимую область страницы")

    painter.save()
    try:
        if high_quality:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.fillRect(content_rect, Qt.GlobalColor.white)
        if isinstance(widget, TabletView) and widget.printable_tracks():
            effective_height = target_content_height or height
            requested_scale = content_rect.height() / max(1, effective_height)
            raster_scale = _tablet_raster_scale(
                requested_scale,
                high_quality=high_quality,
            )
            try:
                snapshot = capture_tablet_print_snapshot(
                    widget,
                    page_aspect_ratio=(
                        page_aspect_ratio
                        if page_aspect_ratio is not None
                        else _print_page_aspect_ratio(painter, content_rect)
                    ),
                    fit_columns=(fit_form_columns if scale_mode is PrintScaleMode.FIT else False),
                    raster_scale=raster_scale,
                    included_track_ids=included_track_ids,
                    grid_print_overrides=dict(grid_print_overrides),
                    show_column_header=show_column_header,
                    repeat_column_header_at_bottom=repeat_column_header_at_bottom,
                    target_content_height=target_content_height,
                    layout_content_height=layout_content_height,
                )
                if repeat_column_header_at_bottom:
                    _paint_tablet_with_repeated_header(
                        painter,
                        content_rect,
                        snapshot,
                        scale_mode=scale_mode,
                        continuation=continuation,
                        show_column_header=show_column_header,
                    )
                else:
                    paint_tablet_snapshot(
                        painter,
                        content_rect,
                        snapshot,
                        scale_mode=scale_mode,
                        continuation=continuation,
                        fill_height=False,
                        show_column_header=show_column_header,
                    )
            except TabletPrintError as exc:
                raise PageRenderError(str(exc)) from exc
            return

        if scale_mode is PrintScaleMode.FIT:
            scale = min(content_rect.width() / width, content_rect.height() / height)
            painter.translate(
                content_rect.left() + (content_rect.width() - width * scale) / 2.0,
                content_rect.top() + (content_rect.height() - height * scale) / 2.0,
            )
            painter.scale(scale, scale)
            widget.render(painter, QPoint())
            return

        device = painter.device()
        dpi = max(1, device.logicalDpiX()) if device is not None else REFERENCE_PRINT_DPI
        scale = dpi / REFERENCE_PRINT_DPI
        left = continuation.source_left_px if continuation is not None else 0.0
        rendered_height = height * scale
        top = content_rect.top() + max(0.0, (content_rect.height() - rendered_height) / 2.0)
        painter.setClipRect(content_rect)
        painter.translate(content_rect.left() - left * scale, top)
        painter.scale(scale, scale)
        widget.render(painter, QPoint())
    except Exception as exc:
        if isinstance(exc, PageRenderError):
            raise
        raise PageRenderError("Не удалось отрисовать визуализацию") from exc
    finally:
        painter.restore()


def _paint_tablet_with_repeated_header(
    painter: QPainter,
    content_rect: QRectF,
    snapshot: TabletPrintSnapshot,
    *,
    scale_mode: PrintScaleMode,
    continuation: PrintContinuationSlice | None,
    show_column_header: bool,
) -> None:
    """Paint the graph at the top and pin the repeated header to the bottom.

    A very short final interval must keep the same paper column widths as prior
    pages. Only the graph body may be compressed vertically; the semantic header
    band is copied without graph pixels and never floats in the page centre.
    """

    body_height = max(1.0, float(snapshot.content_height - snapshot.header_height))
    gap_height = float(tablet_header_gap_height(snapshot.content_height))
    if scale_mode is PrintScaleMode.FIT:
        scale = content_rect.width() / snapshot.layout.total_width
        rendered_width = snapshot.layout.total_width * scale
        x = content_rect.left() + (content_rect.width() - rendered_width) / 2.0
        region_width = rendered_width
    else:
        device = painter.device()
        dpi = max(1, device.logicalDpiX()) if device is not None else REFERENCE_PRINT_DPI
        scale = dpi / REFERENCE_PRINT_DPI
        x = content_rect.left()
        region_width = content_rect.width()

    header_target_height = snapshot.header_height * scale
    body_target_height = body_height * scale
    gap_target_height = gap_height * scale

    y = content_rect.top()
    top_header: QRectF | None = None
    if show_column_header:
        top_header = QRectF(x, y, region_width, header_target_height)
        y = top_header.bottom() + gap_target_height

    repeated_header = QRectF(
        x,
        content_rect.bottom() - header_target_height,
        region_width,
        header_target_height,
    )
    body_bottom = repeated_header.top() - gap_target_height
    available_body_height = max(1.0, body_bottom - y)
    body = QRectF(
        x,
        y,
        region_width,
        min(body_target_height, available_body_height),
    )

    if top_header is not None:
        paint_tablet_header_repeat(
            painter,
            top_header,
            snapshot,
            scale_mode=scale_mode,
            continuation=continuation,
        )
    body_snapshot = snapshot
    if scale_mode is PrintScaleMode.FIT and scale > 0.0:
        body_snapshot = _snapshot_with_compressed_body(
            snapshot,
            target_body_height=max(1.0, body.height() / scale),
        )
    paint_tablet_snapshot(
        painter,
        body,
        body_snapshot,
        scale_mode=scale_mode,
        continuation=continuation,
        fill_height=False,
        show_column_header=False,
    )
    paint_tablet_header_repeat(
        painter,
        repeated_header,
        snapshot,
        scale_mode=scale_mode,
        continuation=continuation,
    )


def _snapshot_with_compressed_body(
    snapshot: TabletPrintSnapshot,
    *,
    target_body_height: float,
) -> TabletPrintSnapshot:
    """Compress graph pixels vertically while preserving header pixels exactly."""

    source_body_height = max(1.0, float(snapshot.content_height - snapshot.header_height))
    resolved_body_height = max(1.0, min(source_body_height, float(target_body_height)))
    if resolved_body_height >= source_body_height - 0.5:
        return snapshot

    raster_scale = float(snapshot.raster_scale)
    header_pixels = max(1, round(snapshot.header_height * raster_scale))
    body_pixels = max(1, round(resolved_body_height * raster_scale))
    compressed: list[QPixmap] = []
    for source in snapshot.pixmaps:
        header_source_height = min(header_pixels, source.height())
        body_source_height = max(1, source.height() - header_source_height)
        target = QPixmap(source.width(), header_pixels + body_pixels)
        target.fill(Qt.GlobalColor.white)
        target_painter = QPainter(target)
        try:
            target_painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            target_painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
            target_painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            target_painter.drawPixmap(
                QRectF(0.0, 0.0, float(source.width()), float(header_pixels)),
                source,
                QRectF(0.0, 0.0, float(source.width()), float(header_source_height)),
            )
            target_painter.drawPixmap(
                QRectF(
                    0.0,
                    float(header_pixels),
                    float(source.width()),
                    float(body_pixels),
                ),
                source,
                QRectF(
                    0.0,
                    float(header_source_height),
                    float(source.width()),
                    float(body_source_height),
                ),
            )
        finally:
            target_painter.end()
        compressed.append(target)

    return TabletPrintSnapshot(
        tuple(compressed),
        snapshot.layout,
        snapshot.header_height + max(1, round(resolved_body_height)),
        snapshot.header_height,
        snapshot.raster_scale,
        snapshot.vertical_ruler_layout,
        snapshot.vertical_ruler_ticks_by_track,
    )
