from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite

import pyqtgraph as pg
from PySide6.QtCore import QPoint, QRectF, QSize, Qt
from PySide6.QtGui import QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget

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
from geoworkbench.tablet.models import CurveLineStyle
from geoworkbench.tablet.tablet_view import (
    RenderedTrack,
    TabletVerticalAxisItem,
    TabletView,
)
from geoworkbench.tablet.vertical_ruler import (
    VerticalRulerLayout,
    VerticalRulerTick,
)


_HEADER_GAP_FRACTION = 0.006
_PRINT_CURVE_MIN_WIDTH = 1.55
_PRINT_CURVE_DENSE_MIN_WIDTH = 1.35


@dataclass(slots=True)
class _CurvePrintState:
    item: pg.PlotDataItem
    pen: QPen


def _qt_pen_style(style: CurveLineStyle) -> Qt.PenStyle:
    return {
        CurveLineStyle.SOLID: Qt.PenStyle.SolidLine,
        CurveLineStyle.DASH: Qt.PenStyle.DashLine,
        CurveLineStyle.DOT: Qt.PenStyle.DotLine,
        CurveLineStyle.DASH_DOT: Qt.PenStyle.DashDotLine,
    }[style]


def _print_curve_width(configured_width: float, curve_count: int) -> float:
    """Keep engineering curve weight readable after wide-form A4 fitting."""

    minimum = (
        _PRINT_CURVE_DENSE_MIN_WIDTH
        if max(1, int(curve_count)) >= 5
        else _PRINT_CURVE_MIN_WIDTH
    )
    return min(5.0, max(minimum, float(configured_width)))


def _activate_print_curve_styles(
    rendered: tuple[RenderedTrack, ...],
) -> list[_CurvePrintState]:
    states: list[_CurvePrintState] = []
    for track in rendered:
        curve_count = max(1, len(track.definition.curve_mnemonics))
        for mnemonic, item in (track.curve_items or {}).items():
            saved_pen = QPen(pg.mkPen(item.opts.get("pen")))
            states.append(_CurvePrintState(item, saved_pen))
            style = track.definition.curve_style(mnemonic)
            if style is None:
                # Legacy/imported tracks may rely on the live PlotDataItem pen
                # instead of a persisted CurveStyle. Preserve its exact colour
                # and dash pattern while increasing only the paper line weight.
                print_pen = QPen(saved_pen)
                print_pen.setWidthF(
                    _print_curve_width(print_pen.widthF(), curve_count)
                )
                item.setPen(print_pen)
                continue
            item.setPen(
                pg.mkPen(
                    style.color,
                    width=_print_curve_width(style.width, curve_count),
                    style=_qt_pen_style(style.line_style),
                )
            )
    return states


def _restore_print_curve_styles(states: list[_CurvePrintState]) -> None:
    for state in reversed(states):
        state.item.setPen(state.pen)


def _activate_layout_tree(widget: QWidget) -> None:
    """Synchronously settle a hidden print clone after an off-screen resize."""

    widgets = (widget, *widget.findChildren(QWidget))
    for current in widgets:
        layout = current.layout()
        if layout is None:
            continue
        layout.invalidate()
        layout.activate()


class TabletPrintError(RuntimeError):
    pass


def _settled_print_header_height(rendered: tuple[RenderedTrack, ...]) -> int:
    """Return the exact pixel row where every synchronized plot body starts."""

    plot_tops = tuple(int(item.widget.plot.geometry().top()) for item in rendered)
    if not plot_tops or min(plot_tops) <= 0:
        raise TabletPrintError("Печатная шапка колонок не получила допустимую геометрию")
    # Fixed title and curve-header bands should align every plot. If Qt reports
    # a transient one-pixel frame difference, the shallowest boundary is the
    # only safe crop: it can leave a hairline of white header, never graph data.
    return min(plot_tops)


@dataclass(frozen=True, slots=True)
class TabletPrintSnapshot:
    pixmaps: tuple[QImage | QPixmap, ...]
    layout: AdaptiveColumnLayout
    content_height: int
    header_height: int
    raster_scale: float = 1.0
    vertical_ruler_layout: VerticalRulerLayout | None = None
    vertical_ruler_ticks_by_track: tuple[
        tuple[str, tuple[VerticalRulerTick, ...]], ...
    ] = ()

    def __post_init__(self) -> None:
        if not self.pixmaps or len(self.pixmaps) != len(self.layout.widths):
            raise ValueError("Некорректный снимок печатной формы")
        if self.content_height <= 0:
            raise ValueError("Высота печатной формы должна быть положительной")
        if not 0 < self.header_height < self.content_height:
            raise ValueError("Высота повторяемой шапки колонок некорректна")
        if not 1.0 <= self.raster_scale <= 8.0:
            raise ValueError("Некорректный масштаб печатного снимка")


def tablet_header_gap_height(content_height: int) -> int:
    """Return the logical gap used around an optional repeated track header."""

    return max(1, round(max(1, int(content_height)) * _HEADER_GAP_FRACTION))


def tablet_print_layout_height(
    content_height: int,
    header_height: int,
    *,
    show_column_header: bool,
    repeat_column_header_at_bottom: bool,
) -> int:
    """Return source height represented by one complete printed page."""

    body_height = max(1, int(content_height) - int(header_height))
    header_count = int(bool(show_column_header)) + int(
        bool(repeat_column_header_at_bottom)
    )
    gap_count = header_count if repeat_column_header_at_bottom else 0
    return (
        body_height
        + header_count * int(header_height)
        + gap_count * tablet_header_gap_height(content_height)
    )


def maximum_tablet_body_height_with_repeated_header(
    available_height: int,
    header_height: int,
    *,
    show_column_header: bool,
) -> int:
    """Return the largest graph body that fits beside a repeated header.

    ``available_height`` is expressed in the canonical logical pixels that fit
    on the physical page at the document-wide horizontal scale.  The gap is a
    function of the resulting snapshot height, therefore a small binary search
    keeps this calculation identical to the renderer instead of approximating
    it with a fixed percentage.
    """

    available = int(available_height)
    header = int(header_height)
    if available <= 0:
        raise ValueError("Доступная высота печатной формы должна быть положительной")
    if header <= 0:
        raise ValueError("Высота повторяемой шапки должна быть положительной")

    low = 0
    high = available
    while low < high:
        candidate = (low + high + 1) // 2
        total = tablet_print_layout_height(
            header + candidate,
            header,
            show_column_header=show_column_header,
            repeat_column_header_at_bottom=True,
        )
        if total <= available:
            low = candidate
        else:
            high = candidate - 1
    return low


def capture_tablet_print_snapshot(
    tablet: TabletView,
    *,
    page_aspect_ratio: float,
    fit_columns: bool = True,
    raster_scale: float = 1.0,
    included_track_ids: tuple[str, ...] | None = None,
    grid_print_overrides: Mapping[str, bool] | None = None,
    show_column_header: bool = True,
    repeat_column_header_at_bottom: bool = False,
    target_content_height: int | None = None,
    layout_content_height: int | None = None,
) -> TabletPrintSnapshot:
    """Capture every visible form column, including off-screen columns."""

    if (
        isinstance(raster_scale, bool)
        or not isinstance(raster_scale, (int, float))
        or not isfinite(raster_scale)
        or not 1.0 <= raster_scale <= 8.0
    ):
        raise TabletPrintError("Масштаб печатного renderer должен быть от 1 до 8")
    if target_content_height is not None and (
        isinstance(target_content_height, bool)
        or not isinstance(target_content_height, int)
        or target_content_height <= 0
    ):
        raise TabletPrintError("Автоматическая высота печатной формы должна быть положительной")
    if layout_content_height is not None and (
        isinstance(layout_content_height, bool)
        or not isinstance(layout_content_height, int)
        or layout_content_height <= 0
    ):
        raise TabletPrintError("Высота эталонной компоновки должна быть положительной")

    rendered = tablet.printable_tracks()
    if included_track_ids is not None:
        included = frozenset(included_track_ids)
        rendered = tuple(item for item in rendered if item.definition.track_id in included)
    if not rendered:
        raise TabletPrintError("На планшете нет видимых колонок для печати")

    definitions = [item.definition for item in rendered]
    original_widths = [item.widget.width() for item in rendered]
    original_header_heights = [
        item.widget.synchronized_header_heights for item in rendered
    ]
    original_tablet_size = tablet.size()
    pixmaps: list[QImage | QPixmap] = []
    curve_style_states: list[_CurvePrintState] = []
    grid_states: list[tuple[TabletGridOverlay, bool, bool]] = []
    layout: AdaptiveColumnLayout | None = None
    content_height = 1
    header_height = 0
    annotation_print_enabled = False
    print_ruler_layout: VerticalRulerLayout | None = None
    print_ruler_ticks_by_track: tuple[
        tuple[str, tuple[VerticalRulerTick, ...]], ...
    ] = ()

    try:
        tablet.set_annotation_print_mode(True)
        annotation_print_enabled = True
        for item in rendered:
            item.widget.set_print_mode(True)
        curve_style_states = _activate_print_curve_styles(rendered)
        print_title_band = max(
            item.widget.natural_title_header_height for item in rendered
        )
        print_header_band = max(
            item.widget.natural_curve_header_height for item in rendered
        )
        for item in rendered:
            item.widget.set_synchronized_title_header_height(print_title_band)
            item.widget.set_synchronized_header_height(print_header_band)
        _activate_layout_tree(tablet)
        tablet.refresh_shared_vertical_rulers()

        content_height = max(item.widget.height() for item in rendered)
        if content_height <= 0:
            raise TabletPrintError("Печатная форма не имеет допустимой высоты")
        # Crop at the actual plot boundary. A semantic sum can drift from the
        # settled Qt geometry on a short final page and include graph pixels in
        # the repeated lower header.
        header_height = _settled_print_header_height(rendered)

        requested_body_height: int | None = None
        if target_content_height is not None:
            # Preserve the graph body requested by pagination. Adaptive print
            # widths can wrap titles and increase the final header after this
            # initial measurement; settle the viewport as final header + body.
            requested_body_height = max(
                1,
                int(target_content_height) - header_height,
            )

        canonical_layout_height = max(1, int(layout_content_height or content_height))

        def build_layout(measured_header_height: int) -> AdaptiveColumnLayout:
            if not fit_columns:
                return original_column_layout(definitions)
            canonical_body_height = max(
                1,
                canonical_layout_height - measured_header_height,
            )
            return adaptive_column_layout(
                definitions,
                page_aspect_ratio=page_aspect_ratio,
                content_height=canonical_body_height,
            )

        layout = build_layout(header_height)
        for item in rendered:
            overlay = TabletGridRenderer.overlay_for(item.widget.plot)
            if overlay is not None:
                grid_states.append(
                    (overlay, overlay.print_mode, overlay.print_suppressed)
                )
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

        for _attempt in range(6):
            for item, width in zip(rendered, layout.widths, strict=True):
                item.widget.set_track_width(width)
            _activate_layout_tree(tablet)

            # Width fitting can change both wrapped track titles and curve
            # header controls. Remeasure and synchronize both bands before
            # deciding the hidden viewport height.
            print_title_band = max(
                item.widget.natural_title_header_height for item in rendered
            )
            print_header_band = max(
                item.widget.natural_curve_header_height for item in rendered
            )
            for item in rendered:
                item.widget.set_synchronized_title_header_height(print_title_band)
                item.widget.set_synchronized_header_height(print_header_band)
            _activate_layout_tree(tablet)
            tablet.refresh_shared_vertical_rulers()

            measured_header_height = _settled_print_header_height(rendered)
            current_height = max(item.widget.height() for item in rendered)
            desired_height = current_height
            if requested_body_height is not None:
                desired_height = measured_header_height + requested_body_height
            elif current_height <= measured_header_height:
                desired_height = measured_header_height + 1

            delta = desired_height - current_height
            if abs(delta) > 1:
                tablet.resize(
                    max(1, tablet.width()),
                    max(1, tablet.height() + delta),
                )
                _activate_layout_tree(tablet)
                tablet.refresh_shared_vertical_rulers()

            content_height = max(item.widget.height() for item in rendered)
            if content_height <= measured_header_height:
                tablet.resize(
                    max(1, tablet.width()),
                    max(
                        1,
                        tablet.height()
                        + measured_header_height
                        + 1
                        - content_height,
                    ),
                )
                _activate_layout_tree(tablet)
                tablet.refresh_shared_vertical_rulers()
                content_height = max(item.widget.height() for item in rendered)

            next_layout = build_layout(measured_header_height)
            header_height = measured_header_height
            height_is_stable = (
                requested_body_height is None
                or abs(content_height - desired_height) <= 1
            )
            if next_layout == layout and height_is_stable:
                break
            layout = next_layout

        content_height = max(item.widget.height() for item in rendered)
        if not 0 < header_height < content_height:
            raise TabletPrintError(
                "После адаптации печатной формы шапка не оставляет места для графика"
            )

        print_ruler_layout = tablet.refresh_shared_vertical_rulers()
        print_ruler_ticks_by_track = tuple(
            (
                item.definition.track_id,
                axis.resolved_ticks,
            )
            for item in rendered
            if isinstance(
                axis := item.widget.plot.getAxis("left"),
                TabletVerticalAxisItem,
            )
        )

        for item, logical_width in zip(rendered, layout.widths, strict=True):
            # Every track uses one canonical height, so the repeated-header crop
            # cannot include graph pixels from a differently sized column.
            logical_height = content_height
            pixel_size = QSize(
                max(1, round(logical_width * raster_scale)),
                max(1, round(logical_height * raster_scale)),
            )
            image = QImage(
                pixel_size,
                QImage.Format.Format_ARGB32_Premultiplied,
            )
            if image.isNull():
                raise TabletPrintError(
                    "Не удалось выделить память для печати колонки "
                    f"{item.definition.title} ({pixel_size.width()}×"
                    f"{pixel_size.height()} px)"
                )
            image.fill(Qt.GlobalColor.white)
            painter = QPainter(image)
            if not painter.isActive():
                raise TabletPrintError(
                    f"Не удалось начать отрисовку колонки: {item.definition.title}"
                )
            try:
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
                painter.scale(raster_scale, raster_scale)
                item.widget.render(painter, QPoint())
                tablet.paint_annotations_for_track(item.definition.track_id, painter)
            finally:
                if painter.isActive():
                    painter.end()
            pixmaps.append(image)
    finally:
        _restore_print_curve_styles(curve_style_states)
        for overlay, print_mode, print_suppressed in reversed(grid_states):
            overlay.set_print_mode(print_mode)
            overlay.set_print_suppressed(print_suppressed)
        if annotation_print_enabled:
            tablet.set_annotation_print_mode(False)
        for item, width, header_heights in zip(
            rendered,
            original_widths,
            original_header_heights,
            strict=True,
        ):
            title_height, curve_header_height = header_heights
            item.widget.set_print_mode(False)
            item.widget.set_track_width(width)
            item.widget.set_synchronized_title_header_height(title_height)
            item.widget.set_synchronized_header_height(curve_header_height)
        if tablet.size() != original_tablet_size:
            tablet.resize(original_tablet_size)
        _activate_layout_tree(tablet)
        tablet.refresh_shared_vertical_rulers()

    if layout is None:
        raise TabletPrintError("Не удалось рассчитать компоновку печатной формы")
    return TabletPrintSnapshot(
        tuple(pixmaps),
        layout,
        content_height,
        header_height,
        float(raster_scale),
        print_ruler_layout,
        print_ruler_ticks_by_track,
    )


def _draw_snapshot_raster(
    painter: QPainter,
    target: QRectF,
    raster: QImage | QPixmap,
    source: QRectF,
) -> None:
    """Draw CPU-backed captures while retaining legacy QPixmap compatibility."""

    if isinstance(raster, QImage):
        painter.drawImage(target, raster, source)
    else:
        painter.drawPixmap(target, raster, source)


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
        scale = horizontal_scale
        rendered_width = snapshot.layout.total_width * scale
        rendered_height = logical_content_height * scale
        if rendered_height > page.height() + 2.0:
            # Runtime layout drift must not abort the whole PDF; keep one bounded
            # uniform fallback so every column remains visible on the page.
            scale = min(horizontal_scale, vertical_scale)
            rendered_width = snapshot.layout.total_width * scale
            rendered_height = logical_content_height * scale
        x = page.left() + (page.width() - rendered_width) / 2.0
        y = page.top()
        if fill_height and rendered_height < page.height():
            y += (page.height() - rendered_height) / 2.0

        painter.save()
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            painter.fillRect(page, Qt.GlobalColor.white)
            painter.setClipRect(page)
            for pixmap, logical_width in zip(
                snapshot.pixmaps, snapshot.layout.widths, strict=True
            ):
                source_height = max(
                    1.0,
                    pixmap.height() - source_top * snapshot.raster_scale,
                )
                target = QRectF(
                    x,
                    y,
                    logical_width * scale,
                    (source_height / snapshot.raster_scale) * scale,
                )
                source = QRectF(
                    0.0,
                    source_top * snapshot.raster_scale,
                    float(pixmap.width()),
                    source_height,
                )
                _draw_snapshot_raster(painter, target, pixmap, source)
                x += (logical_width + snapshot.layout.spacing) * scale
        finally:
            painter.restore()
        return

    device = painter.device()
    dpi = max(1, device.logicalDpiX()) if device is not None else REFERENCE_PRINT_DPI
    scale = dpi / REFERENCE_PRINT_DPI
    left = continuation.source_left_px if continuation is not None else 0.0
    right = (
        continuation.source_right_px
        if continuation is not None
        else float(snapshot.layout.total_width)
    )
    if right <= left:
        raise TabletPrintError("Некорректная страница продолжения")
    rendered_height = logical_content_height * scale
    target_top = page.top() + (page.height() - rendered_height) / 2.0

    painter.save()
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.fillRect(page, Qt.GlobalColor.white)
        painter.setClipRect(page)
        source_x = 0.0
        for pixmap, logical_width in zip(
            snapshot.pixmaps, snapshot.layout.widths, strict=True
        ):
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
                    page.left() + (visible_left - left) * scale,
                    target_top,
                    (visible_right - visible_left) * scale,
                    (source_height / snapshot.raster_scale) * scale,
                )
                source = QRectF(
                    source_left,
                    source_top * snapshot.raster_scale,
                    source_width,
                    source_height,
                )
                _draw_snapshot_raster(painter, target, pixmap, source)
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
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.fillRect(page, Qt.GlobalColor.white)
        painter.setClipRect(page)
        if scale_mode is PrintScaleMode.FIT:
            scale = min(
                page.width() / snapshot.layout.total_width,
                page.height() / snapshot.header_height,
            )
            rendered_width = snapshot.layout.total_width * scale
            rendered_height = snapshot.header_height * scale
            x = page.left() + (page.width() - rendered_width) / 2.0
            y = page.top() + (page.height() - rendered_height) / 2.0
            for pixmap, logical_width in zip(
                snapshot.pixmaps, snapshot.layout.widths, strict=True
            ):
                source = QRectF(
                    0.0,
                    0.0,
                    float(pixmap.width()),
                    snapshot.header_height * snapshot.raster_scale,
                )
                target = QRectF(
                    x,
                    y,
                    logical_width * scale,
                    rendered_height,
                )
                _draw_snapshot_raster(painter, target, pixmap, source)
                x += (logical_width + snapshot.layout.spacing) * scale
            painter.drawLine(
                QPoint(round(page.left()), round(y)),
                QPoint(round(page.right()), round(y)),
            )
            return

        device = painter.device()
        dpi = max(1, device.logicalDpiX()) if device is not None else REFERENCE_PRINT_DPI
        scale = dpi / REFERENCE_PRINT_DPI
        left = continuation.source_left_px if continuation is not None else 0.0
        right = (
            continuation.source_right_px
            if continuation is not None
            else float(snapshot.layout.total_width)
        )
        rendered_height = snapshot.header_height * scale
        target_top = page.top() + (page.height() - rendered_height) / 2.0
        source_x = 0.0
        for pixmap, logical_width in zip(
            snapshot.pixmaps, snapshot.layout.widths, strict=True
        ):
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
                    page.left() + (visible_left - left) * scale,
                    target_top,
                    (visible_right - visible_left) * scale,
                    rendered_height,
                )
                _draw_snapshot_raster(painter, target, pixmap, source)
            source_x = track_right + snapshot.layout.spacing
        painter.drawLine(
            QPoint(round(page.left()), round(target_top)),
            QPoint(round(page.right()), round(target_top)),
        )
    finally:
        painter.restore()
