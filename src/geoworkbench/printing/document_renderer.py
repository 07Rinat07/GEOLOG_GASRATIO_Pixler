from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QApplication, QWidget

from geoworkbench.domain.models import MasterlogTemplate
from geoworkbench.project.session import ProjectSession
from geoworkbench.printing.form_column_layout import original_column_layout
from geoworkbench.printing.page_renderer import paint_widget_page
from geoworkbench.printing.masterlog_renderer import (
    masterlog_header_size_mm,
    paint_masterlog_header,
)
from geoworkbench.printing.pagination import (
    PrintPageSlice,
    build_page_slices,
)
from geoworkbench.printing.print_job import PrintHeaderPlacement, PrintJobSettings
from geoworkbench.printing.print_layout import (
    PrintContinuationSlice,
    PrintScaleMode,
    build_horizontal_continuations,
)
from geoworkbench.printing.unicode_support import print_font
from geoworkbench.services.localization import AppLanguage, Localizer
from geoworkbench.tablet.models import minimum_track_width
from geoworkbench.tablet.tablet_view import TabletView


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
        definitions = [item.definition for item in widget.printable_tracks()]
        if job.page.scale_mode is PrintScaleMode.ACTUAL_SIZE:
            width = original_column_layout(definitions).total_width
        else:
            width = max(
                width,
                sum(max(minimum_track_width(item.kind), int(item.width)) for item in definitions),
            )
        height = max(1, max(item.widget.height() for item in widget.printable_tracks()))
    return width, height


def build_document_plan(widget: QWidget, job: PrintJobSettings) -> PrintDocumentPlan:
    if isinstance(widget, TabletView):
        vertical_pages = build_page_slices(
            pagination=job.pagination,
            current_range=widget.visible_depth_range,
            full_range=widget.printable_vertical_range(),
        )
        axis_label = widget.printable_vertical_label
        axis_unit = widget.printable_vertical_unit
    else:
        vertical_pages = (PrintPageSlice(None, None, 1, 1),)
        axis_label = ""
        axis_unit = ""

    source_width, source_height = printable_content_dimensions(widget, job)
    media = job.page.media_dimensions(source_width, source_height)
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
    return PrintDocumentPlan(tuple(pages), axis_label, axis_unit, source_width, source_height)


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
    plan = build_document_plan(widget, job)
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
            QApplication.processEvents()
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
        header.bottom() + 2.0,
        page_rect.width(),
        max(1.0, footer.top() - header.bottom() - 4.0),
    )

    range_text = _page_range_text(widget, page, plan, job, localizer)
    continuation_text = _continuation_text(page, localizer)
    right_text = " · ".join(part for part in (range_text, continuation_text) if part)

    painter.save()
    try:
        painter.fillRect(page_rect, Qt.GlobalColor.white)
        if paint_full_header and context.header_template is not None and context.session is not None:
            paint_masterlog_header(
                painter,
                header,
                context.header_template,
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
            repeat_column_header_at_bottom=_should_paint_column_header_at_bottom(
                job, page
            ),
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


def _band_heights(painter: QPainter, page_rect: QRectF) -> tuple[float, float]:
    dpi = max(72, painter.device().logicalDpiY()) if painter.device() is not None else 96
    millimeter = dpi / 25.4
    header = max(7.0 * millimeter, page_rect.height() * 0.025)
    footer = max(6.0 * millimeter, page_rect.height() * 0.020)
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
        QApplication.processEvents()
