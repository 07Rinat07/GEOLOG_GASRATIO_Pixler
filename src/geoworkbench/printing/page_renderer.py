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


def _print_page_aspect_ratio(painter: QPainter, content_rect: QRectF) -> float:
    """Return a page-stable aspect ratio for adaptive tablet column widths.

    ``content_rect`` is shorter on the first page because the full report header
    is present there, and taller on continuation pages.  Deriving column widths
    from that changing rectangle makes every page use a different horizontal
    scale.  The paint device represents the same physical sheet for all pages,
    so its aspect ratio is the stable layout contract.
    """

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
                    page_aspect_ratio=_print_page_aspect_ratio(painter, content_rect),
                    fit_columns=(fit_form_columns if scale_mode is PrintScaleMode.FIT else False),
                    raster_scale=raster_scale,
                    included_track_ids=included_track_ids,
                    grid_print_overrides=dict(grid_print_overrides),
                    show_column_header=show_column_header,
                    repeat_column_header_at_bottom=repeat_column_header_at_bottom,
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
                        # Middle pages must keep the same bounded uniform scale
                        # as the first and last pages.  Height-only filling clips
                        # the depth column on wide forms.
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
        scale = min(
            content_rect.width() / snapshot.layout.total_width,
            content_rect.height() / logical_total_height,
        )
        rendered_width = snapshot.layout.total_width * scale
        rendered_height = logical_total_height * scale
        x = content_rect.left() + (content_rect.width() - rendered_width) / 2.0
        y = content_rect.top() + (content_rect.height() - rendered_height) / 2.0
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
    repeated_header = QRectF(
        x,
        body.bottom() + gap_target_height,
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
