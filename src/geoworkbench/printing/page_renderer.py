from __future__ import annotations

from PySide6.QtCore import QPoint, QRectF, Qt
from PySide6.QtGui import QPainter
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
)
from geoworkbench.tablet.tablet_view import TabletView


class PageRenderError(RuntimeError):
    pass


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
        painter.fillRect(content_rect, Qt.GlobalColor.white)
        if isinstance(widget, TabletView) and widget.printable_tracks():
            requested_scale = content_rect.height() / max(1, height)
            raster_scale = min(4.0, max(1.0, requested_scale)) if high_quality else 1.0
            try:
                snapshot = capture_tablet_print_snapshot(
                    widget,
                    page_aspect_ratio=content_rect.width() / content_rect.height(),
                    fit_columns=(fit_form_columns if scale_mode is PrintScaleMode.FIT else False),
                    raster_scale=raster_scale,
                    included_track_ids=included_track_ids,
                    grid_print_overrides=dict(grid_print_overrides),
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
                        fill_height=(
                            scale_mode is PrintScaleMode.FIT and not show_column_header
                        ),
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
    gap = max(1.0, content_rect.height() * 0.006)
    if scale_mode is PrintScaleMode.FIT:
        horizontal_scale = content_rect.width() / snapshot.layout.total_width
        header_height = min(
            content_rect.height() * (0.20 if show_column_header else 0.24),
            snapshot.header_height * horizontal_scale,
        )
        rendered_width = snapshot.layout.total_width * horizontal_scale
        x = content_rect.left() + (content_rect.width() - rendered_width) / 2.0
        top_header = (
            QRectF(x, content_rect.top(), rendered_width, header_height)
            if show_column_header
            else None
        )
        body_top = (
            top_header.bottom() + gap
            if top_header is not None
            else content_rect.top()
        )
        body = QRectF(
            x,
            body_top,
            rendered_width,
            max(
                1.0,
                content_rect.bottom() - body_top - gap - header_height,
            ),
        )
        repeated_header = QRectF(
            x,
            body.bottom() + gap,
            rendered_width,
            header_height,
        )
    else:
        device = painter.device()
        dpi = max(1, device.logicalDpiX()) if device is not None else REFERENCE_PRINT_DPI
        header_height = min(
            content_rect.height() * (0.20 if show_column_header else 0.24),
            snapshot.header_height * dpi / REFERENCE_PRINT_DPI,
        )
        top_header = (
            QRectF(
                content_rect.left(),
                content_rect.top(),
                content_rect.width(),
                header_height,
            )
            if show_column_header
            else None
        )
        body_top = (
            top_header.bottom() + gap
            if top_header is not None
            else content_rect.top()
        )
        body = QRectF(
            content_rect.left(),
            body_top,
            content_rect.width(),
            max(
                1.0,
                content_rect.bottom() - body_top - gap - header_height,
            ),
        )
        repeated_header = QRectF(
            content_rect.left(),
            body.bottom() + gap,
            content_rect.width(),
            header_height,
        )

    if top_header is not None:
        paint_tablet_header_repeat(
            painter,
            top_header,
            snapshot,
            scale_mode=scale_mode,
            continuation=continuation,
        )
    paint_tablet_snapshot(
        painter,
        body,
        snapshot,
        scale_mode=scale_mode,
        continuation=continuation,
        fill_height=scale_mode is PrintScaleMode.FIT,
        show_column_header=False,
    )
    paint_tablet_header_repeat(
        painter,
        repeated_header,
        snapshot,
        scale_mode=scale_mode,
        continuation=continuation,
    )
