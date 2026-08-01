from __future__ import annotations

import argparse
from pathlib import Path

import fitz
import numpy as np
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    CuttingsSample,
    Dataset,
    DatasetKind,
    DepthDomain,
)
from geoworkbench.printing.hydrocarbon_interpretation_report import (
    export_hydrocarbon_interpretation_pdf,
)
from geoworkbench.project.interpretation_calculation_controller import (
    InterpretationCalculationController,
    NormalizedGasCalculationMode,
)
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.hydrocarbon_interpretation import (
    build_hydrocarbon_interpretation_report,
)
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.drilling_calculation_dialog import DrillingCalculationDialog
from geoworkbench.ui.interpretation_report_workspace import InterpretationReportWorkspace


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture normalized-gas interpretation workspace screenshots"
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def _dark_palette() -> QPalette:
    palette = QPalette()
    colors = {
        QPalette.ColorRole.Window: "#171a1f",
        QPalette.ColorRole.WindowText: "#f4f7fb",
        QPalette.ColorRole.Base: "#20242b",
        QPalette.ColorRole.AlternateBase: "#262b34",
        QPalette.ColorRole.ToolTipBase: "#20242b",
        QPalette.ColorRole.ToolTipText: "#f4f7fb",
        QPalette.ColorRole.Text: "#f4f7fb",
        QPalette.ColorRole.Button: "#262b34",
        QPalette.ColorRole.ButtonText: "#f4f7fb",
        QPalette.ColorRole.Highlight: "#4c9dff",
        QPalette.ColorRole.HighlightedText: "#07111f",
        QPalette.ColorRole.Mid: "#546070",
    }
    for role, value in colors.items():
        palette.setColor(role, QColor(value))
    return palette


def _add_curve(
    dataset: Dataset,
    mnemonic: str,
    values: np.ndarray,
    unit: str,
    provenance: str,
) -> None:
    dataset.curves[mnemonic] = CurveData(
        CurveMetadata(
            mnemonic,
            mnemonic,
            mnemonic,
            unit,
            mnemonic,
            dataset.dataset_id,
            provenance,
        ),
        np.asarray(values, dtype=np.float64),
    )


def _session(
    *,
    depth_span: float = 100.0,
    samples: int = 401,
    repeated_anomalies: bool = False,
) -> ProjectSession:
    depth = np.linspace(1_000.0, 1_000.0 + depth_span, samples)
    dataset = Dataset(
        f"normalized-gas-{int(depth_span)}",
        f"Normalized gas {int(depth_span)} m",
        DatasetKind.GTI,
        DepthDomain.MD,
        depth,
    )
    constants = {
        "C1": (80.0, "%"),
        "C2": (10.0, "%"),
        "C3": (5.0, "%"),
        "IC4": (1.0, "%"),
        "NC4": (2.0, "%"),
        "IC5": (1.0, "%"),
        "NC5": (1.0, "%"),
        "ROP": (60.0, "m/h"),
        "BIT": (215.9, "mm"),
        "FLOW": (1_500.0, "l/min"),
        "RPM": (120.0, "1/min"),
        "WOB": (10.0, "t"),
        "MW_IN": (1.2, "g/cm3"),
    }
    for mnemonic, (value, unit) in constants.items():
        _add_curve(
            dataset,
            mnemonic,
            np.full(depth.shape, value),
            unit,
            "source:acceptance",
        )

    phase = np.linspace(0.0, 12.0 * np.pi, depth.size)
    _add_curve(dataset, "WH", 14.0 + 5.0 * np.sin(phase), "%", "calculation:test")
    _add_curve(dataset, "BH", 8.0 + 2.0 * np.cos(phase * 0.8), "", "calculation:test")
    _add_curve(dataset, "CH", 0.45 + 0.2 * np.sin(phase * 0.6), "", "calculation:test")
    _add_curve(dataset, "C1_C2", 8.0 + 2.0 * np.sin(phase * 0.7), "", "calculation:test")
    _add_curve(dataset, "C1_C3", 18.0 + 4.0 * np.cos(phase * 0.5), "", "calculation:test")
    _add_curve(dataset, "DEXP", 1.1 + 0.15 * np.sin(phase * 0.4), "", "calculation:test")

    server = np.ones(depth.shape, dtype=np.float64)
    if repeated_anomalies:
        centers = np.arange(depth[0] + 75.0, depth[-1] - 50.0, 110.0)
    else:
        centers = np.asarray([depth[0] + depth_span * 0.45])
    for center in centers:
        nearest = int(np.argmin(np.abs(depth - center)))
        start = max(0, nearest - 2)
        stop = min(server.size, nearest + 3)
        profile = np.asarray([28.0, 65.0, 120.0, 70.0, 32.0])
        server[start:stop] = profile[: stop - start]
    _add_curve(
        dataset,
        "NORMALIZED_TOTAL_GAS",
        server,
        "normalized gas units",
        "source:server",
    )

    session = ProjectSession()
    well = session.add_dataset(dataset, "Acceptance well")
    for index, center in enumerate(centers[:8]):
        well.cuttings.append(
            CuttingsSample(
                f"acceptance-lba-{index}",
                float(center - 3.0),
                float(center + 3.0),
                lba_group=2,
                lba_type_id="ПБ",
                lba_intensity=3,
                lba_color="ЖК — жёлто-коричневый",
            )
        )
    return session


def _save_widget(widget, target: Path, application: QApplication) -> None:
    widget.show()
    application.processEvents()
    pixmap = widget.grab()
    target.parent.mkdir(parents=True, exist_ok=True)
    if pixmap.isNull() or not pixmap.save(str(target), "PNG"):
        raise RuntimeError(f"Failed to capture screenshot: {target}")
    widget.close()
    application.processEvents()


def _capture(
    language: AppLanguage,
    output: Path,
    application: QApplication,
) -> None:
    controller = InterpretationCalculationController(_session())
    controller.calculate_normalized_gas(
        normalized_gas_mode=NormalizedGasCalculationMode.COMPARE
    )
    widget = InterpretationReportWorkspace(controller, language=language)
    widget.resize(1680, 980)
    widget.refresh()
    _save_widget(
        widget,
        output / f"{language.value}-normalized-gas-interpretation.png",
        application,
    )

    dialog = DrillingCalculationDialog(controller, language=language)
    dialog.resize(1280, 820)
    _save_widget(
        dialog,
        output / f"{language.value}-normalized-gas-dexp-inputs.png",
        application,
    )


def _render_page(page: fitz.Page, target: Path) -> None:
    pixmap = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
    pixmap.save(str(target))


def _text_spans(page: fitz.Page) -> list[dict]:
    spans: list[dict] = []
    for block in page.get_text("dict").get("blocks", []):
        for line in block.get("lines", []):
            spans.extend(line.get("spans", []))
    return spans


def _verify_pdf(pdf_path: Path, artifact_dir: Path, label: str) -> str:
    with fitz.open(pdf_path) as document:
        if document.page_count < 3:
            raise RuntimeError(f"{label}: expected at least three report pages")
        chart_pages = [
            index
            for index, page in enumerate(document)
            if "Лист графика" in page.get_text()
        ]
        if not chart_pages:
            raise RuntimeError(f"{label}: chart pages were not found")
        if label == "short" and len(chart_pages) != 1:
            raise RuntimeError(f"{label}: short well must use one chart page")
        if label == "long" and len(chart_pages) < 2:
            raise RuntimeError(f"{label}: long well must use multiple chart pages")

        maximum_font_size = 0.0
        for page_index, page in enumerate(document):
            page_rect = page.rect
            for span in _text_spans(page):
                maximum_font_size = max(maximum_font_size, float(span["size"]))
                box = fitz.Rect(span["bbox"])
                if not page_rect.contains(box + (-1.0, -1.0, 1.0, 1.0)):
                    raise RuntimeError(
                        f"{label}: text leaves page {page_index + 1}: {span['text']!r}"
                    )
        if maximum_font_size > 24.0:
            raise RuntimeError(
                f"{label}: font was scaled twice; maximum size={maximum_font_size:.2f} pt"
            )

        for chart_index in chart_pages:
            text = document[chart_index].get_text()
            if text.count("Глубина") < 2:
                raise RuntimeError(
                    f"{label}: both left and right depth scales are not visible"
                )
            if "вертикальный масштаб 1:" not in text:
                raise RuntimeError(f"{label}: physical depth scale is missing")

        artifact_dir.mkdir(parents=True, exist_ok=True)
        _render_page(document[0], artifact_dir / f"{label}-cover.png")
        _render_page(
            document[chart_pages[0]],
            artifact_dir / f"{label}-chart-first.png",
        )
        _render_page(
            document[chart_pages[-1]],
            artifact_dir / f"{label}-chart-last.png",
        )
        _render_page(
            document[-1],
            artifact_dir / f"{label}-final.png",
        )
        return (
            f"{label}: pages={document.page_count}; chart_pages={len(chart_pages)}; "
            f"max_font={maximum_font_size:.2f}pt"
        )


def _capture_pdf_acceptance(output: Path) -> None:
    target_dir = output / "pdf-layout"
    target_dir.mkdir(parents=True, exist_ok=True)
    results: list[str] = []
    cases = (
        ("short", _session(depth_span=40.0, samples=241)),
        (
            "long",
            _session(
                depth_span=3_000.0,
                samples=3_001,
                repeated_anomalies=True,
            ),
        ),
    )
    for label, session in cases:
        dataset = session.current_dataset
        if dataset is None:
            raise RuntimeError(f"{label}: acceptance dataset is missing")
        report = build_hydrocarbon_interpretation_report(
            session,
            normalized_gas_mode=NormalizedGasCalculationMode.SERVER,
        )
        target = target_dir / f"{label}-well-report.pdf"
        export_hydrocarbon_interpretation_pdf(
            report,
            target,
            language=AppLanguage.RU,
            dataset=dataset,
            include_chart=True,
        )
        results.append(_verify_pdf(target, target_dir, label))
    (target_dir / "metrics.txt").write_text("\n".join(results) + "\n", encoding="utf-8")


def main() -> int:
    args = _arguments()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    application = QApplication.instance() or QApplication([])
    application.setStyle("Fusion")
    application.setPalette(_dark_palette())
    for language in (AppLanguage.RU, AppLanguage.KK, AppLanguage.EN):
        _capture(language, output, application)
    _capture_pdf_acceptance(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
