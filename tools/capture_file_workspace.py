from __future__ import annotations

import argparse
from pathlib import Path

import fitz
from PySide6.QtCore import QPoint
from PySide6.QtGui import QColor, QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QTabWidget

from geoworkbench.ui.file_workspace_depth import FileWorkspaceWidget


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture localized Files workspace acceptance screenshots"
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
        QPalette.ColorRole.BrightText: "#ff7676",
        QPalette.ColorRole.Highlight: "#4c9dff",
        QPalette.ColorRole.HighlightedText: "#07111f",
    }
    for role, value in colors.items():
        palette.setColor(role, QColor(value))
    return palette


def _sample_pdf(path: Path) -> Path:
    document = fitz.open()
    try:
        for index in range(3):
            page = document.new_page(width=595, height=842)
            page.insert_text((55, 62), "GEOLOG GASRATIO · FILES WORKSPACE", fontsize=17)
            page.insert_text(
                (55, 96), f"Acceptance document · page {index + 1}", fontsize=11
            )
            page.draw_rect(
                fitz.Rect(55, 130, 540, 320), color=(0.2, 0.45, 0.8), width=2
            )
            page.insert_textbox(
                fitz.Rect(78, 160, 510, 290),
                "PDF editing area\nUse the visible square eraser or select an area for formatted text.\n"
                "Redaction, annotations and styled text are handled by PyMuPDF.",
                fontsize=14,
                align=fitz.TEXT_ALIGN_CENTER,
            )
            for row in range(8):
                y = 380 + row * 42
                page.draw_line(
                    (70, y), (525, y), color=(0.55, 0.6, 0.68), width=0.7
                )
                page.insert_text(
                    (78, y - 9), f"Engineering record {row + 1}", fontsize=10
                )
        document.save(path)
    finally:
        document.close()
    return path


def _save(
    widget: FileWorkspaceWidget,
    path: Path,
    application: QApplication,
) -> None:
    application.processEvents()
    pixmap = widget.grab()
    path.parent.mkdir(parents=True, exist_ok=True)
    if pixmap.isNull() or not pixmap.save(str(path), "PNG"):
        raise RuntimeError(f"Failed to capture workspace screenshot: {path}")


def _capture_language(
    language: str,
    source: Path,
    output: Path,
    application: QApplication,
) -> None:
    widget = FileWorkspaceWidget(language=language)
    widget.resize(1680, 980)
    widget.show()
    application.processEvents()

    widget.document_service.open(source)
    widget._refresh_document()
    widget._fit_page()
    widget.eraser_button.setChecked(True)
    application.processEvents()
    overlay = widget._eraser_overlay
    QTest.mouseMove(overlay, QPoint(max(20, overlay.width() // 2), max(20, overlay.height() // 3)))
    application.processEvents()
    _save(widget, output / f"{language}-files-pdf-eraser.png", application)
    widget.eraser_button.setChecked(False)

    widget.sections.setCurrentIndex(1)
    _save(widget, output / f"{language}-files-pdf-tools.png", application)

    widget.sections.setCurrentIndex(4)
    volume_index = widget.converter_category.findData("volume")
    if volume_index < 0:
        raise RuntimeError("Volume category is missing")
    widget.converter_category.setCurrentIndex(volume_index)
    application.processEvents()
    source_index = widget.converter_source.findData("ml")
    target_index = widget.converter_target.findData("l")
    if source_index < 0 or target_index < 0:
        raise RuntimeError("ml/l conversion units are missing")
    widget.converter_source.setCurrentIndex(source_index)
    widget.converter_target.setCurrentIndex(target_index)
    widget.converter_value.setText("7 1/2")
    widget.expression_input.setText("sqrt(144) + 2 1/2")
    widget._convert_units_live()
    widget._calculate_expression_live()
    _save(widget, output / f"{language}-files-engineering-tools.png", application)

    petroleum_tabs = widget.findChild(QTabWidget, "petroleumCalculatorTabs")
    if petroleum_tabs is not None:
        petroleum_tabs.setCurrentIndex(0)
    _save(widget, output / f"{language}-files-petroleum-calculators.png", application)

    if petroleum_tabs is not None:
        petroleum_tabs.setCurrentIndex(3)
        widget.depth_ground_elevation.setValue(150.0)
        widget.depth_datum_height.setValue(7.5)
        widget.depth_measured_depth.setValue(3_000.0)
        widget.depth_vertical_well.setChecked(False)
        widget.depth_true_vertical_depth.setValue(2_500.0)
    _save(widget, output / f"{language}-files-depth-reference.png", application)

    widget.sections.setCurrentIndex(2)
    widget.logo_text.setPlainText("BPServices\nGEOLOG")
    widget.logo_foreground.setText("#f8fafc")
    widget.logo_background.setText("#1f4d3a")
    widget.logo_border_width.setValue(3)
    widget.logo_border_color.setText("#4c9dff")
    widget._refresh_logo()
    _save(widget, output / f"{language}-files-logo-designer.png", application)

    widget.sections.setCurrentIndex(3)
    _save(widget, output / f"{language}-files-archive-manager.png", application)

    widget.close()
    application.processEvents()


def main() -> int:
    args = _arguments()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)

    application = QApplication.instance() or QApplication([])
    application.setStyle("Fusion")
    application.setPalette(_dark_palette())

    source = _sample_pdf(output / "acceptance-document.pdf")
    for language in ("ru", "kk", "en"):
        _capture_language(language, source, output, application)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
