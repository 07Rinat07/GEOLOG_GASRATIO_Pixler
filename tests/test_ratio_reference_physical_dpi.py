import fitz
import numpy as np
import pytest
from PySide6.QtCore import QMarginsF, QRectF
from PySide6.QtGui import QPageLayout, QPageSize, QPainter, QPdfWriter
from PySide6.QtPrintSupport import QPrinter

from geoworkbench.printing.gas_ratio_reference import paint_ratio_reference_summary
from geoworkbench.services.localization import AppLanguage
from test_gas_ratio_reference import _dataset


def _export(path, dataset, language, dpi, printer):
    if printer:
        device = QPrinter(QPrinter.PrinterMode.HighResolution)
        device.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        device.setOutputFileName(str(path))
        device.setFullPage(True)
    else:
        device = QPdfWriter(str(path))
    device.setResolution(dpi)
    device.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    device.setPageOrientation(QPageLayout.Orientation.Landscape)
    device.setPageMargins(QMarginsF(0, 0, 0, 0), QPageLayout.Unit.Millimeter)
    painter = QPainter(device)
    try:
        painter.scale(dpi / 72, dpi / 72)
        before_font, before_pen, before_transform = painter.font(), painter.pen(), painter.transform()
        assert paint_ratio_reference_summary(painter, QRectF(20, 20, 700, 455), dataset, language)
        assert painter.font() == before_font
        assert painter.pen() == before_pen
        assert painter.transform() == before_transform
    finally:
        painter.end()
    del device
    with fitz.open(path) as pdf:
        assert len(pdf) == 1
        spans = [span for block in pdf[0].get_text("dict")["blocks"] if "lines" in block
                 for line in block["lines"] for span in line["spans"]]
        for span in spans:
            assert pdf[0].rect.contains(fitz.Rect(span["bbox"]))
        return spans


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("dpi", [72, 96, 144, 300, 600])
@pytest.mark.parametrize("printer", [False, True])
def test_ratio_reference_pdf_retains_physical_text_at_print_dpi(qapp, tmp_path, language, dpi, printer):
    dataset = _dataset()
    before_depth = dataset.depth.copy()
    before = {name: curve.values.copy() for name, curve in dataset.curves.items()}
    baseline = _export(tmp_path / "baseline.pdf", dataset, language, 72, printer)
    actual = _export(tmp_path / "actual.pdf", dataset, language, dpi, printer)
    assert [span["text"] for span in actual] == [span["text"] for span in baseline]
    assert len(actual) > 40
    for expected, span in zip(baseline, actual, strict=True):
        assert span["size"] == pytest.approx(expected["size"], abs=0.3)
        assert span["bbox"] == pytest.approx(expected["bbox"], abs=0.8)
    np.testing.assert_array_equal(dataset.depth, before_depth)
    for name, curve in dataset.curves.items():
        np.testing.assert_array_equal(curve.values, before[name])
