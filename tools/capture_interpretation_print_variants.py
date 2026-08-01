from __future__ import annotations

import argparse
from pathlib import Path

import fitz
from PySide6.QtGui import QPageLayout
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import QApplication

from capture_interpretation_report import _render_page, _session, _text_spans
from geoworkbench.printing.hydrocarbon_interpretation_report import (
    export_hydrocarbon_interpretation_pdf,
)
from geoworkbench.printing.hydrocarbon_interpretation_system_print import (
    configure_interpretation_printer,
    print_pdf_page_selection,
)
from geoworkbench.project.interpretation_calculation_controller import (
    NormalizedGasCalculationMode,
)
from geoworkbench.services.hydrocarbon_interpretation import (
    build_hydrocarbon_interpretation_report,
)
from geoworkbench.services.localization import AppLanguage


_COVER_MARKERS = (
    "GEOLOG GASRATIO@Pixler",
    "Отчёт по интерпретации газового каротажа",
    "Автоматизированный аналитический отчёт",
    "Проект:",
    "Скважина:",
    "Набор данных:",
    "Сформирован:",
    "Основная кривая:",
    "Порог robust z:",
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture portrait interpretation reports and selected Windows pages"
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def _verify_inside_pages(document: fitz.Document, label: str) -> None:
    for page_index, page in enumerate(document, start=1):
        safe_page = page.rect + (-1.5, -1.5, 1.5, 1.5)
        for span in _text_spans(page):
            box = fitz.Rect(span["bbox"])
            if not safe_page.contains(box):
                raise RuntimeError(
                    f"{label}: text leaves page {page_index}: {span['text']!r}"
                )
        for drawing in page.get_drawings():
            box = fitz.Rect(drawing["rect"])
            if not safe_page.contains(box):
                raise RuntimeError(
                    f"{label}: vector frame leaves page {page_index}: {box}"
                )


def _verify_portrait_report(
    pdf_path: Path,
    artifact_dir: Path,
    label: str,
    *,
    expect_multiple_charts: bool,
) -> tuple[int, tuple[int, ...]]:
    with fitz.open(pdf_path) as document:
        if document.page_count < 3:
            raise RuntimeError(f"{label}: report is unexpectedly short")
        if any(page.rect.width >= page.rect.height for page in document):
            raise RuntimeError(f"{label}: at least one page is not portrait")
        _verify_inside_pages(document, label)

        cover = document[0]
        cover_text = cover.get_text()
        missing = [marker for marker in _COVER_MARKERS if marker not in cover_text]
        if missing:
            raise RuntimeError(f"{label}: cover fields are missing: {missing}")
        title_spans = [
            span
            for span in _text_spans(cover)
            if "Отчёт по интерпретации газового каротажа" in span["text"]
        ]
        if not title_spans:
            raise RuntimeError(f"{label}: cover title is not visible")
        title_box = fitz.Rect(title_spans[0]["bbox"])
        if abs(title_box.x0 + title_box.x1 - cover.rect.width) > cover.rect.width * 0.16:
            raise RuntimeError(f"{label}: cover title is not centered")
        if title_box.y0 > cover.rect.height * 0.28:
            raise RuntimeError(f"{label}: cover title is too low")

        chart_pages = tuple(
            index
            for index, page in enumerate(document)
            if "Лист графика" in page.get_text()
        )
        if not chart_pages:
            raise RuntimeError(f"{label}: chart pages are missing")
        if expect_multiple_charts and len(chart_pages) < 2:
            raise RuntimeError(f"{label}: long well needs multiple chart pages")
        for page_index in chart_pages:
            text = document[page_index].get_text()
            if text.count("Глубина") < 2:
                raise RuntimeError(f"{label}: both depth scales are not visible")
            for marker in (
                "Общий и нормализованный газ",
                "Haworth и Pixler",
                "Буровой контекст и DEXP",
            ):
                if marker not in text:
                    raise RuntimeError(
                        f"{label}: chart heading is missing on page {page_index + 1}: {marker}"
                    )

        all_text = "\n".join(page.get_text() for page in document)
        for marker in (
            "Методы и доступность",
            "Перспективные интервалы УВ-проявлений",
            "Интерпретация по интервалам",
            "Интервалы, подтверждённые геологом",
            "Ограничения методики",
        ):
            if marker not in all_text:
                raise RuntimeError(f"{label}: report section is missing: {marker}")

        _render_page(cover, artifact_dir / f"{label}-cover.png", zoom=1.5)
        _render_page(
            document[chart_pages[0]],
            artifact_dir / f"{label}-chart-first.png",
            zoom=1.2,
        )
        _render_page(
            document[chart_pages[-1]],
            artifact_dir / f"{label}-chart-last.png",
            zoom=1.2,
        )
        _render_page(
            document[-1],
            artifact_dir / f"{label}-final.png",
            zoom=1.2,
        )
        return document.page_count, chart_pages


def _build_portrait_report(
    output: Path,
    label: str,
    *,
    depth_span: float,
    samples: int,
    repeated_anomalies: bool,
) -> tuple[Path, int, tuple[int, ...]]:
    session = _session(
        depth_span=depth_span,
        samples=samples,
        repeated_anomalies=repeated_anomalies,
    )
    dataset = session.current_dataset
    if dataset is None:
        raise RuntimeError(f"{label}: acceptance dataset is missing")
    report = build_hydrocarbon_interpretation_report(
        session,
        normalized_gas_mode=NormalizedGasCalculationMode.SERVER,
    )
    target = output / f"{label}.pdf"
    export_hydrocarbon_interpretation_pdf(
        report,
        target,
        language=AppLanguage.RU,
        dataset=dataset,
        include_chart=True,
        orientation=QPageLayout.Orientation.Portrait,
    )
    page_count, chart_pages = _verify_portrait_report(
        target,
        output,
        label,
        expect_multiple_charts=depth_span > 100.0,
    )
    return target, page_count, chart_pages


def _capture_selected_windows_pages(
    source: Path,
    output: Path,
) -> tuple[Path, list[int]]:
    target = output / "windows-print-pages-001-002.pdf"
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(str(target))
    configure_interpretation_printer(
        printer,
        QPageLayout.Orientation.Portrait,
    )
    sent_pages: list[int] = []
    completed = print_pdf_page_selection(
        source,
        printer,
        (1, 2),
        progress=lambda _current, _total, page: sent_pages.append(page),
    )
    del printer
    if not completed or sent_pages != [1, 2]:
        raise RuntimeError(
            f"Windows page-range simulation sent unexpected pages: {sent_pages}"
        )
    with fitz.open(target) as document:
        if document.page_count != 2:
            raise RuntimeError(
                f"Windows page-range simulation created {document.page_count} pages"
            )
        if any(page.rect.width >= page.rect.height for page in document):
            raise RuntimeError("Windows page-range simulation is not portrait")
        _render_page(document[0], output / "windows-print-page-001.png", zoom=1.3)
        _render_page(document[1], output / "windows-print-page-002.png", zoom=1.3)
    return target, sent_pages


def main() -> int:
    args = _arguments()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    _application = QApplication.instance() or QApplication([])

    short_pdf, short_pages, short_charts = _build_portrait_report(
        output,
        "portrait-short-well-report",
        depth_span=40.0,
        samples=241,
        repeated_anomalies=False,
    )
    long_pdf, long_pages, long_charts = _build_portrait_report(
        output,
        "portrait-long-well-report",
        depth_span=3_000.0,
        samples=3_001,
        repeated_anomalies=True,
    )
    selected_pdf, sent_pages = _capture_selected_windows_pages(short_pdf, output)
    (output / "metrics.txt").write_text(
        "\n".join(
            (
                f"short={short_pdf.name}; pages={short_pages}; charts={len(short_charts)}",
                f"long={long_pdf.name}; pages={long_pages}; charts={len(long_charts)}",
                f"selection={selected_pdf.name}; sent={sent_pages}",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
