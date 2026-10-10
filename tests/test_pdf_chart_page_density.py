from __future__ import annotations

import fitz
import numpy as np
import pytest

from geoworkbench.printing.hydrocarbon_interpretation_pdf_layout import plan_depth_pages
from geoworkbench.printing.hydrocarbon_interpretation_report import (
    export_hydrocarbon_interpretation_pdf_with_passport,
)
from geoworkbench.services.hydrocarbon_interpretation import (
    build_hydrocarbon_interpretation_report,
)
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.interpretation_print_layout_dialog import (
    InterpretationPrintLayoutDialog,
)
from test_interpretation_report_charts import _session_with_report_curves


def test_depth_density_presets_cover_the_entire_well_without_gaps() -> None:
    bounds = (51.0, 5680.0)
    heights = 310.0
    detailed = plan_depth_pages(*bounds, heights)
    selected = [
        plan_depth_pages(*bounds, heights, target_depth_per_page=depth)
        for depth in (100.0, 250.0, 500.0)
    ]
    assert selected[0] == detailed
    assert len(selected[0]) > len(selected[1]) > len(selected[2])
    for pages in selected:
        assert pages[0].top_depth == bounds[0]
        assert pages[-1].bottom_depth == bounds[1]
        assert all(
            before.bottom_depth == pytest.approx(after.top_depth)
            for before, after in zip(pages, pages[1:])
        )
        assert all(
            page.span > 0 and page.plot_height_points <= heights + 1e-8
            for page in pages
        )


@pytest.mark.parametrize("invalid", (0.0, -100.0, float("nan"), float("inf")))
def test_depth_density_rejects_invalid_target(invalid: float) -> None:
    with pytest.raises(ValueError, match="интервал глубины"):
        plan_depth_pages(100.0, 400.0, 300.0, target_depth_per_page=invalid)


def test_print_layout_exposes_explicit_depth_density_without_changing_default(qapp) -> None:
    dialog = InterpretationPrintLayoutDialog(language=AppLanguage.RU)
    try:
        assert dialog.selected_layout().target_depth_per_page == 100.0
        assert dialog.chart_density_combo.count() == 3
        dialog.chart_density_combo.setCurrentIndex(2)
        assert dialog.selected_layout().target_depth_per_page == 500.0
    finally:
        dialog.close()


def test_pdf_density_is_reflected_in_pages_passport_and_unchanged_las(qapp, tmp_path) -> None:
    session = _session_with_report_curves(depth_span=700, samples=71)
    dataset = session.current_dataset
    assert dataset is not None
    original = {key: curve.values.copy() for key, curve in dataset.curves.items()}
    report = build_hydrocarbon_interpretation_report(session)
    files = []
    counts = []
    for target in (100.0, 500.0):
        result = export_hydrocarbon_interpretation_pdf_with_passport(
            session, report, tmp_path / f"chart-{int(target)}.pdf",
            language=AppLanguage.RU, include_chart=True,
            target_depth_per_page=target,
        )
        assert dict(result.passport.render.options)["target_depth_per_page"] == str(target)
        assert result.passport.dataset_sha256
        with fitz.open(result.primary_path) as document:
            files.append(document.page_count)
            counts.append(document.page_count)
    assert counts[0] > counts[1]  # same report text, fewer graphical sheets
    for key, values in original.items():
        np.testing.assert_array_equal(dataset.curves[key].values, values)
