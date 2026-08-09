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
    tablet_header_gap_height,
    tablet_print_layout_height,
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
        detail = str(exc).strip()
        cause = type(exc).__name__ + (f": {detail}" if detail else "")
        raise PageRenderError(
            f"Не удалось отрисовать визуализацию: {cause}"
        ) from exc
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
    """Paint body and optional header copies with one common geometric scale."""

    body_height = max(1.0, float(snapshot.content_height - snapshot.header_height))
    gap_height = float(tablet_header_gap_height(snapshot.content_height))
    logical_total_height = float(
        tablet_print_layout_height(
            snapshot.content_height,
            snapshot.header_height,
            show_column_header=show_column_header,
            repeat_column_header_at_bottom=True,
        )
    )

    if scale_mode is PrintScaleMode.FIT:
        scale = content_rect.width() / snapshot.layout.total_width
        rendered_width = snapshot.layout.total_width * scale
        rendered_height = logical_total_height * scale
        if rendered_height > content_rect.height() + 2.0:
            raise TabletPrintError(
                "Нижняя шапка не помещается при едином масштабе формы. "
                "Включите автоматический интервал страницы или уменьшите "
                "ручной интервал."
            )
        x = content_rect.left()
        # Keep the final graph and its repeated legend together. A partial
        # depth/time interval deliberately remains short to preserve the same
        # engineering scale as the preceding pages.
        y = content_rect.top()
        region_width = rendered_width
    else:
        device = painter.device()
        dpi = max(1, device.logicalDpiX()) if device is not None else REFERENCE_PRINT_DPI
        scale = dpi / REFERENCE_PRINT_DPI
        rendered_height = logical_total_height * scale
        x = content_rect.left()
        y = content_rect.top() + max(0.0, (content_rect.height() - rendered_height) / 2.0)
        region_width = content_rect.width()

    header_target_height = snapshot.header_height * scale
    body_target_height = body_height * scale
    gap_target_height = gap_height * scale

    top_header: QRectF | None = None
    if show_column_header:
        top_header = QRectF(x, y, region_width, header_target_height)
        y = top_header.bottom() + gap_target_height

    body = QRectF(x, y, region_width, body_target_height)
    repeated_header_top = body.bottom() + gap_target_height
    repeated_header = QRectF(
        x,
        repeated_header_top,
        region_width,
        header_target_height,
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
