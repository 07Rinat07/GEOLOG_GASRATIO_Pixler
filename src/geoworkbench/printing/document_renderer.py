from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass, replace
from typing import Iterator

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QWidget

from geoworkbench.domain.models import MasterlogTemplate
from geoworkbench.printing.auto_pagination import (
    PRINT_FOOTER_MM,
    PRINT_SIMPLE_HEADER_MM,
    PRINT_VERTICAL_GAP_MM,
    automatic_tablet_first_page_geometry,
    automatic_tablet_page_geometry,
    balanced_automatic_page_ranges,
    printable_tablet_body_height_mm,
)
from geoworkbench.printing.form_column_layout import original_column_layout
from geoworkbench.printing.masterlog_renderer import (
    masterlog_header_size_mm,
    paint_masterlog_header,
)
from geoworkbench.printing.page_renderer import paint_widget_page
from geoworkbench.printing.pagination import (
    PrintPageSlice,
    PrintPaginationSettings,
    PrintRangeMode,
    build_page_slices,
)
from geoworkbench.printing.print_job import PrintHeaderPlacement, PrintJobSettings
from geoworkbench.printing.print_layout import (
    PrintContinuationSlice,
    PrintScaleMode,
    build_horizontal_continuations,
)
from geoworkbench.printing.unicode_support import print_font
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage, Localizer
from geoworkbench.tablet.models import minimum_track_width
from geoworkbench.tablet.tablet_view import TabletView


_DOCUMENT_HEADER_FONT_SCALE = 1.60


@dataclass(frozen=True, slots=True)
class PrintDocumentContext:
    title: str
    language: AppLanguage = AppLanguage.RU
    header_template: MasterlogTemplate | None = None
    session: ProjectSession | None = None


@dataclass(frozen=True, slots=True)
class PrintDocumentPage:
    vertical: PrintPageSlice
    continuation: PrintContinuationSlice
    index: int
    total: int

    @property
    def start(self) -> float | None:
        return self.vertical.start

    @property
    def end(self) -> float | None:
        return self.vertical.end

    @property
    def has_vertical_range(self) -> bool:
        return self.vertical.has_vertical_range

    @property
    def is_last_vertical_page(self) -> bool:
        return self.vertical.index == self.vertical.total


@dataclass(frozen=True, slots=True)
class PrintDocumentPlan:
    pages: tuple[PrintDocumentPage, ...]
    axis_label: str = ""
    axis_unit: str = ""
    source_width_px: int = 1
    source_height_px: int = 1
    target_content_height_px: int | None = None
    tablet_page_aspect_ratio: float | None = None
    resolved_units_per_page: float | None = None
    tablet_header_height_px: int | None = None
    first_page_target_content_height_px: int | None = None
    first_page_units_per_page: float | None = None

    @property
    def page_count(self) -> int:
        return len(self.pages)

    @property
    def continuation_count(self) -> int:
        return max(page.continuation.total for page in self.pages)


def printable_content_dimensions(widget: QWidget, job: PrintJobSettings) -> tuple[int, int]:
    width = max(1, int(widget.width()))
    height = max(1, int(widget.height()))
    if isinstance(widget, TabletView) and widget.printable_tracks():
        printable_tracks = _selected_tablet_tracks(widget, job)
        definitions = [item.definition for item in printable_tracks]
        if job.page.scale_mode is PrintScaleMode.ACTUAL_SIZE:
            width = original_column_layout(definitions).total_width
        else:
            width = max(
                width,
                sum(
                    max(minimum_track_width(item.kind), int(item.width))
                    for item in definitions
                ),
            )
        height = max(1, max(item.widget.height() for item in printable_tracks))
    return width, height


def _selected_tablet_tracks(widget: TabletView, job: PrintJobSettings):
    rendered = widget.printable_tracks()
    if job.included_track_ids is None:
        return rendered
    selected_ids = set(job.included_track_ids)
    selected = tuple(
        item for item in rendered if item.definition.track_id in selected_ids
    )
    if len(selected) != len(selected_ids):
        missing = selected_ids.difference(item.definition.track_id for item in selected)
        raise ValueError(
            "Выбранные для печати колонки больше не доступны: "
            + ", ".join(sorted(missing))
        )
    return selected


def build_document_plan(
    widget: QWidget,
    job: PrintJobSettings,
    *,
    context: PrintDocumentContext | None = None,
) -> PrintDocumentPlan:
    source_width, source_height = printable_content_dimensions(widget, job)
    target_content_height: int | None = None
    tablet_page_aspect_ratio: float | None = None
    resolved_units_per_page: float | None = None
    tablet_header_height_px: int | None = None
    first_page_target_content_height_px: int | None = None
    first_page_units_per_page: float | None = None
    pagination = job.pagination

    if isinstance(widget, TabletView):
        full_range = widget.printable_vertical_range()
        if (
            pagination.auto_units_per_page
            and pagination.range_mode is not PrintRangeMode.CURRENT
            and job.page.scale_mode is PrintScaleMode.FIT
            and full_range is not None
        ):
            printable_tracks = _selected_tablet_tracks(widget, job)
            selected_definitions = [item.definition for item in printable_tracks]
            auto_source_width = original_column_layout(selected_definitions).total_width
            header_height = max(
                item.widget.title.height() + item.widget.print_curve_header_height
                for item in printable_tracks
            )
            current_range = widget.visible_depth_range or full_range
            current_span = abs(float(current_range[1]) - float(current_range[0]))
            media = job.page.media_dimensions(source_width, source_height)
            full_header_band_mm = _planned_full_header_band_height_mm(
                context,
                content_width_mm=media.content_width_mm,
                content_height_mm=media.content_height_mm,
            )
            regular_header_band_mm = (
                full_header_band_mm
                if full_header_band_mm is not None
                and job.header_placement is PrintHeaderPlacement.EVERY_PAGE
                else PRINT_SIMPLE_HEADER_MM
            )
            first_header_band_mm = full_header_band_mm or PRINT_SIMPLE_HEADER_MM
            auto_geometry = automatic_tablet_page_geometry(
                # Selected columns determine the automatic density. The live
                # TabletView width can still include columns excluded from this job.
                source_width_px=auto_source_width,
                source_content_height_px=source_height,
                header_height_px=header_height,
                current_span=current_span,
                content_width_mm=media.content_width_mm,
                content_height_mm=media.content_height_mm,
                header_band_mm=regular_header_band_mm,
            )
            domain_span = abs(float(full_range[1]) - float(full_range[0]))
            resolved_units_per_page = auto_geometry.units_per_page
            target_content_height = auto_geometry.target_content_height_px
            tablet_page_aspect_ratio = auto_geometry.page_aspect_ratio
            tablet_header_height_px = header_height
            regular_body_height_mm = printable_tablet_body_height_mm(
                media.content_height_mm,
                header_band_mm=regular_header_band_mm,
            )
            first_body_height_mm = printable_tablet_body_height_mm(
                media.content_height_mm,
                header_band_mm=first_header_band_mm,
            )
            first_geometry = automatic_tablet_first_page_geometry(
                canonical_content_height_px=target_content_height,
                column_header_height_px=header_height,
                regular_units_per_page=resolved_units_per_page,
                regular_body_height_mm=regular_body_height_mm,
                first_body_height_mm=first_body_height_mm,
            )
            first_page_units_per_page = first_geometry.units_per_page
            first_page_target_content_height_px = first_geometry.target_content_height_px
            pagination = replace(
                pagination,
                units_per_page=max(min(resolved_units_per_page, domain_span), 1e-9),
                auto_units_per_page=False,
                overlap=0.0,
            )

        if (
            first_page_units_per_page is not None
            and resolved_units_per_page is not None
        ):
            vertical_pages = _build_automatic_page_slices(
                pagination=pagination,
                current_range=widget.visible_depth_range,
                full_range=full_range,
                first_units_per_page=first_page_units_per_page,
                regular_units_per_page=resolved_units_per_page,
            )
        else:
            vertical_pages = build_page_slices(
                pagination=pagination,
                current_range=widget.visible_depth_range,
                full_range=full_range,
            )
        axis_label = widget.printable_vertical_label
        axis_unit = widget.printable_vertical_unit
    else:
        vertical_pages = (PrintPageSlice(None, None, 1, 1),)
        axis_label = ""
        axis_unit = ""

    media = job.page.media_dimensions(
        source_width,
        target_content_height or source_height,
    )
    continuations = build_horizontal_continuations(
        source_width_px=float(source_width),
        available_width_mm=media.content_width_mm,
        scale_mode=job.page.scale_mode,
        overlap_mm=(
            job.page.continuation_overlap_mm
            if job.page.scale_mode is PrintScaleMode.ACTUAL_SIZE
            else 0.0
        ),
    )
    total = len(vertical_pages) * len(continuations)
    pages: list[PrintDocumentPage] = []
    index = 1
    for vertical in vertical_pages:
        for continuation in continuations:
            pages.append(PrintDocumentPage(vertical, continuation, index, total))
            index += 1
    return PrintDocumentPlan(
        pages=tuple(pages),
        axis_label=axis_label,
        axis_unit=axis_unit,
        source_width_px=source_width,
        source_height_px=source_height,
        target_content_height_px=target_content_height,
        tablet_page_aspect_ratio=tablet_page_aspect_ratio,
        resolved_units_per_page=resolved_units_per_page,
        tablet_header_height_px=tablet_header_height_px,
        first_page_target_content_height_px=first_page_target_content_height_px,
        first_page_units_per_page=first_page_units_per_page,
    )


def _planned_full_header_band_height_mm(
    context: PrintDocumentContext | None,
    *,
    content_width_mm: float,
    content_height_mm: float,
) -> float | None:
    if (
        context is None
        or context.header_template is None
        or context.session is None
    ):
        return None
    size = masterlog_header_size_mm(context.header_template)
    if size.width() <= 0.0 or size.height() <= 0.0:
        return None
    proportional = content_width_mm * size.height() / size.width()
    minimum = min(content_height_mm * 0.08, 15.0)
    return max(minimum, min(proportional, content_height_mm * 0.46))


def _build_automatic_page_slices(
    *,
    pagination: PrintPaginationSettings,
    current_range: tuple[float, float] | None,
    full_range: tuple[float, float] | None,
    first_units_per_page: float,
    regular_units_per_page: float,
) -> tuple[PrintPageSlice, ...]:
    if full_range is None:
        return (PrintPageSlice(None, None, 1, 1),)
    domain_span = abs(float(full_range[1]) - float(full_range[0]))
    selector = replace(
        pagination,
        units_per_page=max(
            domain_span,
            first_units_per_page,
            regular_units_per_page,
            1e-9,
        ),
        auto_units_per_page=False,
        overlap=0.0,
    )
    selected = build_page_slices(
        pagination=selector,
        current_range=current_range,
        full_range=full_range,
    )
    if not selected or not selected[0].has_vertical_range:
        return selected
    assert selected[0].start is not None and selected[0].end is not None
    start = float(selected[0].start)
    end = float(selected[0].end)
    if end <= start:
        return (PrintPageSlice(start, end, 1, 1),)

    raw = list(
        balanced_automatic_page_ranges(
            start,
            end,
            first_units_per_page=max(first_units_per_page, 1e-9),
            regular_units_per_page=max(regular_units_per_page, 1e-9),
        )
    )
    total = len(raw)
    return tuple(
        PrintPageSlice(page_start, page_end, index + 1, total)
        for index, (page_start, page_end) in enumerate(raw)
    )


def paint_document_pages(
    widget: QWidget,
    painter: QPainter,
    page_device,
    page_rect: QRectF,
    *,
    job: PrintJobSettings,
    context: PrintDocumentContext,
    high_quality: bool = True,
    first_page: int | None = None,
    last_page: int | None = None,
) -> PrintDocumentPlan:
    plan = build_document_plan(widget, job, context=context)
    selected = tuple(
        page
        for page in plan.pages
        if (first_page is None or page.index >= first_page)
        and (last_page is None or page.index <= last_page)
    )
    if not selected:
        raise ValueError("Выбранный диапазон страниц не содержит страниц для печати")

    with _preserve_tablet_range(widget):
        for output_index, page in enumerate(selected):
            if output_index > 0 and not page_device.newPage():
                raise RuntimeError("Принтер/PDF не смог создать следующую страницу")
            _apply_page_range(widget, page)
            paint_document_page(
                widget,
                painter,
                page_rect,
                page=page,
                plan=plan,
                job=job,
                context=context,
                high_quality=high_quality,
            )
    return plan


def _page_target_content_height(
    plan: PrintDocumentPlan,
    page: PrintDocumentPage,
) -> int | None:
    """Return a page-specific hidden viewport without changing widths."""

    target = plan.target_content_height_px
    regular_units = plan.resolved_units_per_page
    if (
        target is None
        or regular_units is None
        or regular_units <= 0.0
        or not page.has_vertical_range
    ):
        return target

    header_height = max(0, int(plan.tablet_header_height_px or 0))
    capacity = regular_units
    page_target = target
    if (
        page.vertical.index == 1
        and plan.first_page_target_content_height_px is not None
        and plan.first_page_units_per_page is not None
    ):
        page_target = plan.first_page_target_content_height_px
        capacity = plan.first_page_units_per_page

    assert page.start is not None and page.end is not None
    page_span = abs(float(page.end) - float(page.start))
    if page_span <= 0.0 or page_span >= capacity * 0.999:
        return page_target
    body_height = max(1, int(page_target) - header_height)
    partial_body_height = max(1, round(body_height * page_span / capacity))
    return header_height + partial_body_height


def paint_document_page(
    widget: QWidget,
    painter: QPainter,
    page_rect: QRectF,
    *,
    page: PrintDocumentPage,
    plan: PrintDocumentPlan,
    job: PrintJobSettings,
    context: PrintDocumentContext,
    high_quality: bool = True,
) -> None:
    if page_rect.width() <= 0 or page_rect.height() <= 0:
        raise ValueError("Недопустимая область страницы")

    localizer = Localizer.create(context.language)
    simple_header_height, footer_height = _band_heights(painter, page_rect)
    vertical_gap = _vertical_gap_height(painter)
    paint_full_header = _should_paint_full_header(job, page, context)
    header_height = (
        _print_header_band_height(painter, page_rect, context.header_template)
        if paint_full_header and context.header_template is not None
        else simple_header_height
    )
    header = QRectF(page_rect.left(), page_rect.top(), page_rect.width(), header_height)
    footer = QRectF(
        page_rect.left(),
        page_rect.bottom() - footer_height,
        page_rect.width(),
        footer_height,
    )
    body = QRectF(
        page_rect.left(),
        header.bottom() + vertical_gap / 2.0,
        page_rect.width(),
        max(1.0, footer.top() - header.bottom() - vertical_gap),
    )

    range_text = _page_range_text(widget, page, plan, job, localizer)
    continuation_text = _continuation_text(page, localizer)
    right_text = " · ".join(part for part in (range_text, continuation_text) if part)

    painter.save()
    try:
        painter.fillRect(page_rect, Qt.GlobalColor.white)
        if (
            paint_full_header
            and context.header_template is not None
            and context.session is not None
        ):
            paint_masterlog_header(
                painter,
                header,
                _print_header_template(context.header_template),
                context.session,
                language=context.language,
            )
        else:
            _paint_header(
                painter,
                header,
                title=context.title,
                range_text=right_text,
            )
        paint_widget_page(
            widget,
            painter,
            body,
            fit_form_columns=job.page.effective_fit_form_columns,
            scale_mode=job.page.scale_mode,
            continuation=page.continuation,
            high_quality=high_quality,
            show_column_header=_should_paint_column_header_at_top(page),
            repeat_column_header_at_bottom=_should_paint_column_header_at_bottom(
                job, page
            ),
            included_track_ids=job.included_track_ids,
            grid_print_overrides=job.grid_print_overrides,
            target_content_height=_page_target_content_height(plan, page),
            layout_content_height=plan.target_content_height_px,
            page_aspect_ratio=plan.tablet_page_aspect_ratio,
        )
        _paint_footer(
            painter,
            footer,
            page=page,
            show_page_numbers=job.pagination.show_page_numbers,
            localizer=localizer,
        )
    finally:
        painter.restore()


def _print_header_template(template: MasterlogTemplate) -> MasterlogTemplate:
    """Return a print-only copy with more readable passport/header text."""

    prepared = deepcopy(template)
    for element in prepared.header_elements:
        raw_size = element.properties.get("font_size_mm", 3.5)
        if not isinstance(raw_size, (int, float)) or isinstance(raw_size, bool):
            raw_size = 3.5
        element.properties["font_size_mm"] = min(
            50.0,
            max(1.0, float(raw_size) * _DOCUMENT_HEADER_FONT_SCALE),
        )
    return prepared


def _should_paint_full_header(
    job: PrintJobSettings,
    page: PrintDocumentPage,
    context: PrintDocumentContext,
) -> bool:
    if context.header_template is None or context.session is None:
        return False
    return (
        job.header_placement is PrintHeaderPlacement.EVERY_PAGE
        or page.index == 1
    )


def _should_paint_column_header_at_bottom(
    job: PrintJobSettings,
    page: PrintDocumentPage,
) -> bool:
    return job.repeat_column_header_at_bottom and page.is_last_vertical_page


def _should_paint_column_header_at_top(page: PrintDocumentPage) -> bool:
    # The form header is the legend for the plotted curves.  It always belongs
    # at the start of the document; the optional bottom copy supplements it at
    # the end of the well and must never replace it.
    return page.index == 1


def _paint_header(painter: QPainter, rect: QRectF, *, title: str, range_text: str) -> None:
    painter.save()
    try:
        painter.setPen(Qt.GlobalColor.black)
        painter.setFont(print_font(9.0, bold=True, text=f"{title} {range_text}"))
        metrics = painter.fontMetrics()
        right_width = metrics.horizontalAdvance(range_text) + 8 if range_text else 0
        title_rect = QRectF(
            rect.left(), rect.top(), max(1.0, rect.width() - right_width), rect.height()
        )
        title_text = metrics.elidedText(title, Qt.TextElideMode.ElideRight, int(title_rect.width()))
        painter.drawText(
            title_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            title_text,
        )
        if range_text:
            painter.setFont(print_font(8.0, text=range_text))
            painter.drawText(
                rect,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                range_text,
            )
        painter.drawLine(rect.bottomLeft(), rect.bottomRight())
    finally:
        painter.restore()


def _paint_footer(
    painter: QPainter,
    rect: QRectF,
    *,
    page: PrintDocumentPage,
    show_page_numbers: bool,
    localizer: Localizer,
) -> None:
    painter.save()
    try:
        painter.setPen(Qt.GlobalColor.black)
        painter.drawLine(rect.topLeft(), rect.topRight())
        painter.setFont(print_font(7.5, text="GEOLOG GASRATIO@Pixler"))
        painter.drawText(
            rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "GEOLOG GASRATIO@Pixler",
        )
        if show_page_numbers:
            painter.drawText(
                rect,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                localizer.text("print_center.page_number", page=page.index, total=page.total),
            )
    finally:
        painter.restore()


def _page_range_text(
    widget: QWidget,
    page: PrintDocumentPage,
    plan: PrintDocumentPlan,
    job: PrintJobSettings,
    localizer: Localizer,
) -> str:
    if not job.pagination.show_page_range or not page.has_vertical_range:
        return ""
    assert page.start is not None and page.end is not None
    if isinstance(widget, TabletView):
        start = widget.format_vertical_value(page.start)
        end = widget.format_vertical_value(page.end)
    else:
        suffix = f" {plan.axis_unit}" if plan.axis_unit else ""
        start = f"{page.start:g}{suffix}"
        end = f"{page.end:g}{suffix}"
    label = plan.axis_label or localizer.text("print.depth")
    return localizer.text("print_center.page_range", axis=label, start=start, end=end)


def _continuation_text(page: PrintDocumentPage, localizer: Localizer) -> str:
    if page.continuation.total <= 1:
        return ""
    return localizer.text(
        "print_center.continuation",
        part=page.continuation.index,
        total=page.continuation.total,
    )


def _print_header_band_height(
    painter: QPainter, page_rect: QRectF, template: MasterlogTemplate
) -> float:
    size = masterlog_header_size_mm(template)
    if size.width() <= 0 or size.height() <= 0:
        return 1.0
    proportional = page_rect.width() * size.height() / size.width()
    dpi = max(72, painter.device().logicalDpiY()) if painter.device() is not None else 96
    minimum = min(page_rect.height() * 0.08, 15.0 * dpi / 25.4)
    # A very tall imported header must not consume the whole sheet.  The header
    # stays legible while at least half of the printable page remains for curves.
    return max(minimum, min(proportional, page_rect.height() * 0.46))


def _vertical_gap_height(painter: QPainter) -> float:
    """Return the same physical inter-band gap used by pagination planning."""

    dpi = max(72, painter.device().logicalDpiY()) if painter.device() is not None else 96
    return PRINT_VERTICAL_GAP_MM * dpi / 25.4


def _band_heights(painter: QPainter, page_rect: QRectF) -> tuple[float, float]:
    dpi = max(72, painter.device().logicalDpiY()) if painter.device() is not None else 96
    millimeter = dpi / 25.4
    header = max(PRINT_SIMPLE_HEADER_MM * millimeter, page_rect.height() * 0.025)
    footer = max(PRINT_FOOTER_MM * millimeter, page_rect.height() * 0.020)
    return min(header, page_rect.height() * 0.12), min(footer, page_rect.height() * 0.10)


def _apply_page_range(widget: QWidget, page: PrintDocumentPage) -> None:
    if isinstance(widget, TabletView) and page.has_vertical_range:
        assert page.start is not None and page.end is not None
        widget.set_visible_depth(page.start, page.end)


@contextmanager
def _preserve_tablet_range(widget: QWidget) -> Iterator[None]:
    if not isinstance(widget, TabletView):
        yield
        return
    original = widget.visible_depth_range
    try:
        yield
    finally:
        if original is not None:
            widget.set_visible_depth(*original)
