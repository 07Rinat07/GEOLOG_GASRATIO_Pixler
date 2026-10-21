from dataclasses import replace

import numpy as np
import pytest

from geoworkbench.domain.models import CalculationState
from geoworkbench.services.gas_update_coverage import gas_update_coverage
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.daily_las_growth_result import daily_las_growth_result_text
from test_las_parameter_resolver import _dataset


def test_raw_coverage_counts_zero_and_rejects_nonfinite_without_mutation():
    dataset = _dataset(("S800", "Содержание метана", "%", [0.0, np.inf]),
                       ("C2", "Ethane", "%", [np.nan, 0.2]))
    before = dataset.curves.copy()
    coverage = gas_update_coverage(dataset)
    entries = {item.component: item for item in coverage.components}
    assert entries["C1"].source == "S800"
    assert entries["C1"].count == 1
    assert entries["C1"].last_index == "100.0"
    assert entries["C2"].last_index == "101.0"
    assert entries["C3"].count == 0
    assert dataset.curves == before


def test_ambiguous_sources_are_not_presented_as_missing():
    dataset = _dataset(("C1", "Methane", "%", [1.0, 2.0]),
                       ("CH4", "Methane", "%", [3.0, 4.0]))
    methane = next(item for item in gas_update_coverage(dataset).components if item.component == "C1")
    assert methane.ambiguous
    assert not methane.source


def test_calculated_curves_are_excluded_and_stale_ratios_require_recalculation():
    dataset = _dataset(("C1", "Methane", "%", [1.0, 2.0]),
                       ("C1_C2", "", "", [2.0, 3.0]))
    for curve in dataset.curves.values():
        curve.metadata = replace(curve.metadata, provenance="calculation:gas-ratio:2.0")
        curve.state = CalculationState.STALE
    coverage = gas_update_coverage(dataset)
    assert all(item.count == 0 for item in coverage.components)
    assert coverage.stale_ratios == ("C1_C2",)


@pytest.mark.parametrize("language", list(AppLanguage))
def test_receipt_explicitly_reports_component_gaps_and_stale_ratios(language, tmp_path):
    dataset = _dataset(("TG", "Total gas", "%", [0.0, 0.1]),
                       ("C1_C2", "", "", [2.0, 3.0]))
    dataset.curves["curve-1"].state = CalculationState.STALE
    text = daily_las_growth_result_text(dataset, tmp_path / "well.geologpkg", language)
    assert "TG: TG: 2/2" in text
    assert "C1:" in text
    assert "Haworth / Pixler" in text


def test_descending_index_last_measurement_is_not_deepest():
    dataset = _dataset(("C1", "Methane", "%", [1.0, 0.0]))
    dataset.active_index.values[:] = [101.0, 100.0]
    methane = next(item for item in gas_update_coverage(dataset).components if item.component == "C1")
    assert methane.last_index == "100.0"
