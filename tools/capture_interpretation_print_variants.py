from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
import re

import fitz
from PySide6.QtGui import QPageLayout
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import QApplication

from capture_interpretation_report import _render_page, _session, _text_spans
from geoworkbench.printing.hydrocarbon_interpretation_report import (
    export_hydrocarbon_interpretation_pdf,
)
from geoworkbench.printing.hydrocarbon_interpretation_report_identity import (
    InterpretationReportIdentity,
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


_COVER_TITLE = "Отчёт ГТИ по скважине Северная-12"
_COVER_MARKERS = (
    "GEOLOG GASRATIO@Pixler",
    "Интерпретация газового каротажа",
    "Проект Северный купол",
    "Северная-12",
    "Месторождение Северное",
    "АО Заказчик",
    "ТОО Сервис ГТИ",
    "Буровая ZJ-70",
    "GAS-INT-012",
    "Финальный",
    "Инженер ГТИ И.И.",
    "Ведущий геолог П.П.",
    "Руководитель проекта С.С.",
)
_MANUAL_IDENTITY = InterpretationReportIdentity(
    report_title=_COVER_TITLE,
    report_subtitle="Интерпретация газового каротажа",
    project_name="Проект Северный купол",
    well_name="Северная-12",
    field_name="Месторождение Северное",
    location="Блок 4, Казахстан",
    operator_name="АО Заказчик",
    contractor_name="ТОО Сервис ГТИ",
    rig_name="Буровая ZJ-70",
    dataset_name="Основной комплект газового каротажа",
    interval="",
    document_number="GAS-INT-012",
    revision="02",
    document_status="Финальный",
    report_date="01.08.2026",
    prepared_by="Инженер ГТИ И.И.",
    checked_by="Ведущий геолог П.П.",
    approved_by="Руководитель проекта С.С.",
    confidentiality="Для служебного использования",
    remarks="Контрольный отчёт с вручную заданными реквизитами.",
)
_NUMERIC_LABEL = re.compile(r"^-?\d+(?:[.,]\d+)?$")


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


def _axis_numeric_labels(page: fitz.Page) -> tuple[tuple[str, ...], tuple[str, ...]]:
    left: list[str] = []
    right: list[str] = []
    for span in _text_spans(page):
        text = str(span["text"]).strip().replace(" ", "")
        if not _NUMERIC_LABEL.fullmatch(text):
            continue
        box = fitz.Rect(span["bbox"])
        if box.y0 < page.rect.height * 0.17 or box.y1 > page.rect.height * 0.82:
            continue
        if box.x1 < page.rect.width * 0.18:
            left.append(text)
        elif box.x0 > page.rect.width * 0.82:
            right.append(text)
    return tuple(left), tuple(right)


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
        normalized_cover_text = " ".join(cover_text.split())
        missing = [marker for marker in _COVER_MARKERS if marker not in cover_text]
        if missing:
            raise RuntimeError(f"{label}: cover fields are missing: {missing}")
        if _COVER_TITLE not in normalized_cover_text:
            raise RuntimeError(f"{label}: cover title is not visible")
        if "Новый проект" in cover_text or "acceptance-dataset" in cover_text:
            raise RuntimeError(f"{label}: technical source names leaked into the cover")

        title_spans = [
            span
            for span in _text_spans(cover)
            if float(span["size"]) >= 20.0
            and float(span["bbox"][1]) < cover.rect.height * 0.35
        ]
        if not title_spans:
            raise RuntimeError(f"{label}: cover title geometry is missing")
        title_box = fitz.Rect(title_spans[0]["bbox"])
        for span in title_spans[1:]:
            title_box.include_rect(fitz.Rect(span["bbox"]))
        if abs(title_box.x0 + title_box.x1 - cover.rect.width) > cover.rect.width * 0.16:
            raise RuntimeError(f"{label}: cover title is not centered")
        if title_box.y0 > cover.rect.height * 0.30:
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
            page = document[page_index]
            text = page.get_text()
            if text.count("Глубина") < 2:
                raise RuntimeError(f"{label}: both depth scales are not visible")
            left_labels, right_labels = _axis_numeric_labels(page)
            if len(left_labels) < 3 or len(right_labels) < 3:
                raise RuntimeError(
                    f"{label}: numeric depth labels are too sparse on page "
                    f"{page_index + 1}: left={left_labels}, right={right_labels}"
                )
            if left_labels != right_labels:
                raise RuntimeError(
                    f"{label}: left and right numeric depth scales differ on page "
                    f"{page_index + 1}: left={left_labels}, right={right_labels}"
                )
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
            zoom=1.4,
        )
        _render_page(
            document[chart_pages[-1]],
            artifact_dir / f"{label}-chart-last.png",
            zoom=1.4,
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
    identity = replace(
        _MANUAL_IDENTITY,
        interval=f"{float(dataset.depth.min()):.2f}–{float(dataset.depth.max()):.2f} {report.depth_unit}",
    )
    target = output / f"{label}.pdf"
    export_hydrocarbon_interpretation_pdf(
        report,
        target,
        language=AppLanguage.RU,
        dataset=dataset,
        include_chart=True,
        orientation=QPageLayout.Orientation.Portrait,
        identity=identity,
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
        for page_number, page in enumerate(document, start=1):
            images = page.get_images(full=True)
            if not images:
                raise RuntimeError(
                    f"Windows page-range simulation page {page_number} is not rasterized"
                )
            image_rectangles = page.get_image_rects(images[0][0])
            largest_area = max(
                (rectangle.get_area() for rectangle in image_rectangles),
                default=0.0,
            )
            if largest_area < page.rect.get_area() * 0.70:
                raise RuntimeError(
                    f"Windows page-range simulation page {page_number} is clipped"
                )
            pixmap = page.get_pixmap(matrix=fitz.Matrix(0.35, 0.35), alpha=False)
            dark_channels = sum(value < 245 for value in pixmap.samples)
            if dark_channels < len(pixmap.samples) * 0.02:
                raise RuntimeError(
                    f"Windows page-range simulation page {page_number} is blank"
                )
        _render_page(document[0], output / "windows-print-page-001.png", zoom=1.3)
        _render_page(document[1], output / "windows-print-page-002.png", zoom=1.4)
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
                "cover=manual-details; depth-scale=labelled-major-plus-minor",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
