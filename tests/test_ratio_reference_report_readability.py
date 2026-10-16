"""Physical PDF text, not virtual-font requests, defines readable ratio reports."""

import fitz
from types import SimpleNamespace
import numpy as np
import pytest
from PySide6.QtCore import QMarginsF, QRectF
from PySide6.QtGui import QPageLayout, QPageSize, QPainter, QPdfWriter

from geoworkbench.printing.hydrocarbon_interpretation_pdf_renderer import _ratio_reference_chart_rect
from geoworkbench.printing.hydrocarbon_interpretation_pdf_text import measure_report_html_height
from geoworkbench.printing.ratio_phase_summary import ratio_phase_summary_html
from geoworkbench.printing.report_visual_system import modern_oilfield_report_profile
from geoworkbench.printing.gas_ratio_reference import (
    _compact_tick, paint_ratio_reference_summary,
    RATIO_REFERENCE_WIDTH, RATIO_REFERENCE_HEIGHT,
)
from geoworkbench.services.localization import AppLanguage
from test_gas_ratio_reference import _dataset


def test_ratio_axis_compacts_thousands_without_scientific_exponent() -> None:
    assert _compact_tick(0.0) == "0"
    assert _compact_tick(275.0) == "275"
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


@pytest.mark.parametrize("width,height", ((760.0, 480.0), (511.0, 690.0)))
def test_phase_key_fits_below_ratio_plot_on_landscape_and_portrait(qapp, width, height):
    phase_html = ratio_phase_summary_html(
        SimpleNamespace(candidates=(), depth_unit="m"), AppLanguage.RU,
    )
    key_height = measure_report_html_height(
        phase_html, width, visual=modern_oilfield_report_profile(),
    )
    target = _ratio_reference_chart_rect(QRectF(0.0, 0.0, width, height), key_height)
    chart_height = RATIO_REFERENCE_HEIGHT * min(target.width() / RATIO_REFERENCE_WIDTH, target.height() / RATIO_REFERENCE_HEIGHT)
    assert chart_height > 0.0
    assert chart_height + 10.0 + key_height + 32.0 <= height


@pytest.mark.parametrize("language", list(AppLanguage))
def test_production_reference_page_reports_missing_tail_and_preserves_phase_evidence(qapp, tmp_path, language):
    from geoworkbench.printing.hydrocarbon_interpretation_report import export_hydrocarbon_interpretation_pdf
    from test_hydrocarbon_report_client_limitations import _minimal_report

    dataset = _dataset()
    dataset.curves["C1_C5"].values[-1] = np.nan
    report = _minimal_report(dataset_id=dataset.dataset_id)
    target = tmp_path / "profile-coverage.pdf"
    export_hydrocarbon_interpretation_pdf(report, target, dataset=dataset, include_chart=True, language=language)
    with fitz.open(target) as pdf:
        pages = [page for page in pdf if "Pixler ·" in page.get_text() and "102.00" in page.get_text()
                 and "103.00" in page.get_text()]
        assert pages
        page = pages[0]
        text = page.get_text()
        assert "100.00–102.00" in text
        assert "100.00–103.00" in text
        assert "103.00 m ·" not in text
        spans = [span for block in page.get_text("dict")["blocks"] if "lines" in block
                 for line in block["lines"] for span in line["spans"]]
        assert all(page.rect.contains(fitz.Rect(span["bbox"])) for span in spans)
        # The qualitative tendency does not promote unknown interval phases to gas.
        unknown = {AppLanguage.RU: "фаза не определена", AppLanguage.KK: "фаза анықталмаған",
                   AppLanguage.EN: "phase undetermined"}[language]
        assert unknown in text
        headings = {AppLanguage.RU: "Предварительные фазы", AppLanguage.KK: "алдын ала фазалар",
                    AppLanguage.EN: "Preliminary"}
        assert headings[language] in text
