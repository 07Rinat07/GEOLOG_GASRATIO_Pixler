from __future__ import annotations

import fitz
from PySide6.QtGui import QPageLayout, QPageSize, QPdfWriter
from PySide6.QtPrintSupport import QAbstractPrintDialog

from geoworkbench.printing.hydrocarbon_interpretation_system_print import (
    print_pdf_page_selection,
    selected_report_pages,
)


def _source_pdf(path) -> None:
    document = fitz.open()
    for index, color in enumerate(((1, 0, 0), (0, 1, 0), (0, 0, 1)), start=1):
        page = document.new_page(width=595.0, height=842.0)
        page.draw_rect(page.rect, fill=color, color=color)
        page.insert_text((72.0, 72.0), f"SOURCE PAGE {index}", fontsize=18.0)
    document.save(path)
    document.close()


def _pdf_writer(path) -> QPdfWriter:
    writer = QPdfWriter(str(path))
    writer.setResolution(300)
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setPageOrientation(QPageLayout.Orientation.Portrait)
    return writer


def test_selected_report_pages_obeys_page_range() -> None:
    pages = selected_report_pages(
        102,
        QAbstractPrintDialog.PrintRange.PageRange,
        1,
        2,
    )

    assert pages == (1, 2)


def test_selected_report_pages_supports_explicit_reverse_order() -> None:
    pages = selected_report_pages(
        102,
        QAbstractPrintDialog.PrintRange.PageRange,
        1,
        3,
        reverse=True,
    )

    assert pages == (3, 2, 1)


def test_selected_report_pages_clamps_invalid_driver_values() -> None:
    pages = selected_report_pages(
        5,
        QAbstractPrintDialog.PrintRange.PageRange,
        -10,
        400,
    )

    assert pages == (1, 2, 3, 4, 5)


def test_pdf_writer_receives_only_requested_pages(tmp_path) -> None:
    source = tmp_path / "source.pdf"
    target = tmp_path / "selected-pages.pdf"
    _source_pdf(source)
    writer = _pdf_writer(target)
    progress: list[int] = []

    completed = print_pdf_page_selection(
        source,
        writer,
        (1, 2),
        progress=lambda _current, _total, page: progress.append(page),
    )
    del writer

    assert completed is True
    assert progress == [1, 2]
    with fitz.open(target) as printed:
        assert printed.page_count == 2


def test_pdf_writer_can_stop_before_all_pages_are_spooled(tmp_path) -> None:
    source = tmp_path / "source.pdf"
    target = tmp_path / "cancelled.pdf"
    _source_pdf(source)
    writer = _pdf_writer(target)
    checks = 0
    progress: list[int] = []

    def cancel_requested() -> bool:
        nonlocal checks
        checks += 1
        return checks >= 2

    completed = print_pdf_page_selection(
        source,
        writer,
        (1, 2, 3),
        cancel_requested=cancel_requested,
        progress=lambda _current, _total, page: progress.append(page),
    )
    del writer

    assert completed is False
    assert progress == [1]
