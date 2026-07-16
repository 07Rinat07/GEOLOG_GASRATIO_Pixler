from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import QLabel
import pytest

from geoworkbench.printing.widget_print import WidgetPrintError, render_widget_to_printer


def test_widget_print_renderer_writes_pdf_printer_output(qapp, tmp_path) -> None:
    widget = QLabel("Print preview")
    widget.resize(640, 360)
    widget.show()
    qapp.processEvents()
    target = tmp_path / "preview.pdf"
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(str(target))

    render_widget_to_printer(widget, printer)

    payload = target.read_bytes()
    assert payload.startswith(b"%PDF-")
    assert b"%%EOF" in payload[-1024:]
    widget.close()


def test_widget_print_renderer_rejects_zero_sized_widget(qapp) -> None:
    widget = QLabel("Hidden")
    widget.resize(0, 0)
    printer = QPrinter(QPrinter.PrinterMode.ScreenResolution)

    with pytest.raises(WidgetPrintError, match="размера"):
        render_widget_to_printer(widget, printer)
