"""Physical PDF text, not virtual-font requests, defines readable ratio reports."""

import fitz
import numpy as np
import pytest
from PySide6.QtCore import QMarginsF, QRectF
from PySide6.QtGui import QPageLayout, QPageSize, QPainter, QPdfWriter

from geoworkbench.printing.gas_ratio_reference import (
    _compact_tick, paint_ratio_reference_summary,
)
from geoworkbench.services.localization import AppLanguage
from test_gas_ratio_reference import _dataset


def test_ratio_axis_compacts_thousands_without_scientific_exponent() -> None:
    assert _compact_tick(0.0) == "0"
    assert _compact_tick(275.0) == "2.8e+02"
    assert _compact_tick(1100.0) == "1.1k"
    assert _compact_tick(5400.0) == "5.4k"


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("dpi", (72, 300))
def test_portrait_pdf_ratio_ticks_remain_legible_and_inside_page(
    qapp, tmp_path, language, dpi,
) -> None:
    dataset = _dataset()
    source = {name: curve.values.copy() for name, curve in dataset.curves.items()}
    destination = tmp_path / f"ratio-{dpi}.pdf"
    writer = QPdfWriter(str(destination))
    writer.setResolution(dpi)
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setPageMargins(QMarginsF(0, 0, 0, 0), QPageLayout.Unit.Millimeter)
    painter = QPainter(writer)
    try:
        painter.scale(dpi / 72.0, dpi / 72.0)
        assert paint_ratio_reference_summary(
            painter, QRectF(42.0, 42.0, 511.0, 690.0), dataset, language,
        )
    finally:
        painter.end()
    with fitz.open(destination) as document:
        page = document[0]
        spans = [
            span
            for block in page.get_text("dict")["blocks"] if "lines" in block
            for line in block["lines"] for span in line["spans"]
        ]
        labels = [span for span in spans if span["text"] in ("0.2", "0.4", "0.6", "1.0", "C1/C2", "C1/C5")]
        assert labels
        assert min(label["size"] for label in labels) >= 6.5
        assert all(page.rect.contains(fitz.Rect(label["bbox"])) for label in labels)
    for name, curve in dataset.curves.items():
        np.testing.assert_array_equal(curve.values, source[name])
