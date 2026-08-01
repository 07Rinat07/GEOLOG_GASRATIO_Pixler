from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite

from PySide6.QtCore import QPoint, QRectF, QSize, Qt
from PySide6.QtGui import QPainter, QPixmap
from geoworkbench.printing.form_column_layout import (
    AdaptiveColumnLayout,
    adaptive_column_layout,
    original_column_layout,
)
from geoworkbench.printing.print_layout import (
    REFERENCE_PRINT_DPI,
    PrintContinuationSlice,
    PrintScaleMode,
)
from geoworkbench.tablet.grid_renderer import TabletGridOverlay, TabletGridRenderer
from geoworkbench.tablet.tablet_view import TabletView


class TabletPrintError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class TabletPrintSnapshot:
    pixmaps: tuple[QPixmap, ...]
    layout: AdaptiveColumnLayout
    content_height: int
    header_height: int
    raster_scale: float = 1.0

    def __post_init__(self) -> None:
        if not self.pixmaps or len(self.pixmaps) != len(self.layout.widths):
            raise ValueError("Некорректный снимок печатной формы")
        if self.content_height <= 0:
            raise ValueError("Высота печатной формы должна быть положительной")
        if not 0 < self.header_height < self.content_height:
            raise ValueError("Высота повторяемой шапки колонок некорректна")
        if not 1.0 <= self.raster_scale <= 8.0:
            raise ValueError("Некорректный масштаб печатного снимка")


def capture_tablet_print_snapshot(
    tablet: TabletView,
    *,
    page_aspect_ratio: float,
    fit_columns: bool = True,
    raster_scale: float = 1.0,
    included_track_ids: tuple[str, ...] | None = None,
    grid_print_overrides: Mapping[str, bool] | None = None,
) -> TabletPrintSnapshot:
    """Capture every visible form column, including off-screen columns.

    ``raster_scale`` lets PDF and image exports render the Qt widgets into a
    larger intermediate surface.  This avoids enlarging a low-resolution screen
    screenshot when the destination is an A4 page at 300 or 600 DPI.
    """

    if (
        isinstance(raster_scale, bool)
        or not isinstance(raster_scale, (int, float))
        or not isfinite(raster_scale)
        or not 1.0 <= raster_scale <= 8.0
    ):
        raise TabletPrintError("Масштаб печатного renderer должен быть от 1 до 8")

    rendered = tablet.printable_tracks()
    if included_track_ids is not None:
        included = frozenset(included_track_ids)
        rendered = tuple(item for item in rendered if item.definition.track_id in included)
    if not rendered:
        raise TabletPrintError("На планшете нет видимых колонок для печати")
    content_height = max(item.widget.height() for item in rendered)
    if content_height <= 0:
        raise TabletPrintError("Печатная форма не имеет допустимой высоты")

    definitions = [item.definition for item in rendered]
    layout = (
        adaptive_column_layout(
            definitions,
            page_aspect_ratio=page_aspect_ratio,
            content_height=content_height,
        )
        if fit_columns
        else original_column_layout(definitions)
    )
    original_widths = [item.widget.width() for item in rendered]
    pixmaps: list[QPixmap] = []
    grid_states: list[tuple[TabletGridOverlay, bool, bool]] = []
    tablet.set_annotation_print_mode(True)
    try:
        for item, width in zip(rendered, layout.widths, strict=True):
            item.widget.set_print_mode(True)
            item.widget.set_track_width(width)
            overlay = TabletGridRenderer.overlay_for(item.widget.plot)
            if overlay is not None:
                grid_states.append((overlay, overlay.print_mode, overlay.print_suppressed))
                overlay.set_print_mode(True)
                print_grid = (
                    grid_print_overrides.get(
                        item.definition.track_id,
                        item.definition.grid_print,
                    )
                    if grid_print_overrides is not None
                    else item.definition.grid_print
                )
                overlay.set_print_suppressed(not print_grid)
        header_height = max(
            item.widget.title.height() + item.widget.curve_header_scroll.height()
            for item in rendered
        )
        for item, logical_width in zip(rendered, layout.widths, strict=True):
            logical_height = max(1, item.widget.height())
            pixel_size = QSize(
                max(1, round(logical_width * raster_scale)),
                max(1, round(logical_height * raster_scale)),
            )
            pixmap = QPixmap(pixel_size)
            pixmap.fill(Qt.GlobalColor.white)
            painter = QPainter(pixmap)
            try:
                painter.scale(raster_scale, raster_scale)
                item.widget.render(painter, QPoint())
                # The professional annotation layer is a tablet-wide overlay,
                # not a child of an individual PyQtGraph column. Paint the
                # corresponding clipped portion into every column snapshot so
                # screen, PDF and physical print keep the same geometry.
                tablet.paint_annotations_for_track(item.definition.track_id, painter)
            finally:
                painter.end()
            if pixmap.isNull():
                raise TabletPrintError(
                    f"Не удалось подготовить колонку к печати: {item.definition.title}"
                )
            pixmaps.append(pixmap)
    finally:
        for overlay, print_mode, print_suppressed in reversed(grid_states):
            overlay.set_print_mode(print_mode)
            overlay.set_print_suppressed(print_suppressed)
        tablet.set_annotation_print_mode(False)
        for item, width in zip(rendered, original_widths, strict=True):
            item.widget.set_print_mode(False)
            item.widget.set_track_width(width)

    return TabletPrintSnapshot(
        tuple(pixmaps),
        layout,
        content_height,
        header_height,
        float(raster_scale),
    )


def paint_tablet_snapshot(
    painter: QPainter,
    page: QRectF,
    snapshot: TabletPrintSnapshot,
    *,
    scale_mode: PrintScaleMode = PrintScaleMode.FIT,
    continuation: PrintContinuationSlice | None = None,
    fill_height: bool = False,
    show_column_header: bool = True,
) -> None:
    if page.width() <= 0 or page.height() <= 0:
        raise TabletPrintError("Устройство печати не предоставило допустимую область страницы")

    source_top = 0.0 if show_column_header else float(snapshot.header_height)
    logical_content_height = max(1.0, snapshot.content_height - source_top)

    if scale_mode is PrintScaleMode.FIT:
        horizontal_scale = page.width() / snapshot.layout.total_width
        vertical_scale = page.height() / logical_content_height
        if not fill_height:
            horizontal_scale = vertical_scale = min(horizontal_scale, vertical_scale)
        rendered_width = snapshot.layout.total_width * horizontal_scale
        rendered_height = logical_content_height * vertical_scale
        x = page.left() + (page.width() - rendered_width) / 2.0
        y = page.top() + (page.height() - rendered_height) / 2.0

        painter.save()
        try:
            painter.fillRect(page, Qt.GlobalColor.white)
            for pixmap, logical_width in zip(snapshot.pixmaps, snapshot.layout.widths, strict=True):
                source_height = max(
                    1.0,
                    pixmap.height() - source_top * snapshot.raster_scale,
                )
                target = QRectF(
                    x,
                    y,
                    logical_width * horizontal_scale,
                    (source_height / snapshot.raster_scale) * vertical_scale,
                )
                source = QRectF(
                    0.0,
                    source_top * snapshot.raster_scale,
                    float(pixmap.width()),
                    source_height,
                )
                painter.drawPixmap(target, pixmap, source)
                x += (logical_width + snapshot.layout.spacing) * horizontal_scale
        finally:
            painter.restore()
        return

    device = painter.device()
    dpi = max(1, device.logicalDpiX()) if device is not None else REFERENCE_PRINT_DPI
    horizontal_scale = dpi / REFERENCE_PRINT_DPI
    left = continuation.source_left_px if continuation is not None else 0.0
    right = (
        continuation.source_right_px
        if continuation is not None
        else float(snapshot.layout.total_width)
    )
    if right <= left:
        raise TabletPrintError("Некорректная страница продолжения")

    painter.save()
    try:
        painter.fillRect(page, Qt.GlobalColor.white)
        painter.setClipRect(page)
        source_x = 0.0
        for pixmap, logical_width in zip(snapshot.pixmaps, snapshot.layout.widths, strict=True):
            track_left = source_x
            track_right = track_left + logical_width
            visible_left = max(left, track_left)
            visible_right = min(right, track_right)
            if visible_right > visible_left:
                source_left = (visible_left - track_left) * snapshot.raster_scale
                source_width = (visible_right - visible_left) * snapshot.raster_scale
                source_height = max(
                    1.0,
                    pixmap.height() - source_top * snapshot.raster_scale,
                )
                target = QRectF(
                    page.left() + (visible_left - left) * horizontal_scale,
                    page.top(),
                    (visible_right - visible_left) * horizontal_scale,
                    page.height(),
                )
                source = QRectF(
                    source_left,
                    source_top * snapshot.raster_scale,
                    source_width,
                    source_height,
                )
                painter.drawPixmap(target, pixmap, source)
            source_x = track_right + snapshot.layout.spacing
    finally:
        painter.restore()


def paint_tablet_header_repeat(
    painter: QPainter,
    page: QRectF,
    snapshot: TabletPrintSnapshot,
    *,
    scale_mode: PrintScaleMode = PrintScaleMode.FIT,
    continuation: PrintContinuationSlice | None = None,
) -> None:
    """Repeat the captured track/curve header without duplicating graph data."""

    if page.width() <= 0 or page.height() <= 0:
        raise TabletPrintError("Область нижней шапки колонок имеет неверный размер")

    painter.save()
    try:
        painter.fillRect(page, Qt.GlobalColor.white)
        painter.setClipRect(page)
        if scale_mode is PrintScaleMode.FIT:
            # The repeated header must follow the selected paper orientation.
            # Its band is intentionally shorter than the live Qt header, so a
            # single uniform scale would shrink a landscape header back toward
            # portrait width. Scale width and height independently instead.
            horizontal_scale = page.width() / snapshot.layout.total_width
            rendered_width = snapshot.layout.total_width * horizontal_scale
            x = page.left() + (page.width() - rendered_width) / 2.0
            for pixmap, logical_width in zip(snapshot.pixmaps, snapshot.layout.widths, strict=True):
                source = QRectF(
                    0.0,
                    0.0,
                    float(pixmap.width()),
                    snapshot.header_height * snapshot.raster_scale,
                )
                target = QRectF(
                    x,
                    page.top(),
                    logical_width * horizontal_scale,
                    page.height(),
                )
                painter.drawPixmap(target, pixmap, source)
                x += (logical_width + snapshot.layout.spacing) * horizontal_scale
            painter.drawLine(page.topLeft(), page.topRight())
            return

        device = painter.device()
        dpi = max(1, device.logicalDpiX()) if device is not None else REFERENCE_PRINT_DPI
        horizontal_scale = dpi / REFERENCE_PRINT_DPI
        left = continuation.source_left_px if continuation is not None else 0.0
        right = (
            continuation.source_right_px
            if continuation is not None
            else float(snapshot.layout.total_width)
        )
        source_x = 0.0
        for pixmap, logical_width in zip(snapshot.pixmaps, snapshot.layout.widths, strict=True):
            track_left = source_x
            track_right = track_left + logical_width
            visible_left = max(left, track_left)
            visible_right = min(right, track_right)
            if visible_right > visible_left:
                source = QRectF(
                    (visible_left - track_left) * snapshot.raster_scale,
                    0.0,
                    (visible_right - visible_left) * snapshot.raster_scale,
                    snapshot.header_height * snapshot.raster_scale,
                )
                target = QRectF(
                    page.left() + (visible_left - left) * horizontal_scale,
                    page.top(),
                    (visible_right - visible_left) * horizontal_scale,
                    page.height(),
                )
                painter.drawPixmap(target, pixmap, source)
            source_x = track_right + snapshot.layout.spacing
        painter.drawLine(page.topLeft(), page.topRight())
    finally:
        painter.restore()
