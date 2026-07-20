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


def test_tablet_print_renderer_includes_all_tracks_and_restores_screen_widths(
    qapp, tmp_path
) -> None:
    import numpy as np

    from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
    from geoworkbench.printing.page_settings import PrintOrientation, PrintPageSettings
    from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind
    from geoworkbench.tablet.tablet_view import TabletView

    dataset = Dataset(
        "dataset-print",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 110.0, 120.0]),
    )
    view = TabletView()
    view.resize(900, 620)
    view.set_layout_model(
        TabletLayout(
            [
                TrackDefinition("depth", "Depth", TrackKind.DEPTH, width=120),
                TrackDefinition("one", "One", TrackKind.CURVE, width=420),
                TrackDefinition("two", "Two", TrackKind.CURVE, width=360),
                TrackDefinition("three", "Three", TrackKind.TEXT, width=520),
            ]
        )
    )
    view.set_dataset(dataset)
    view.show()
    qapp.processEvents()
    original_widths = tuple(item.widget.width() for item in view.printable_tracks())

    target = tmp_path / "tablet-a4.pdf"
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(str(target))
    settings = PrintPageSettings(orientation=PrintOrientation.PORTRAIT)
    printer.setPageSize(settings.qt_page_size)
    printer.setPageOrientation(settings.qt_orientation)

    render_widget_to_printer(view, printer, fit_form_columns=True)

    assert target.read_bytes().startswith(b"%PDF-")
    assert len(view.printable_tracks()) == 4
    assert tuple(item.widget.width() for item in view.printable_tracks()) == original_widths
    view.close()
