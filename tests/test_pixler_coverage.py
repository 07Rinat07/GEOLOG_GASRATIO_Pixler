from dataclasses import replace

import numpy as np
import pytest

from geoworkbench.domain.models import CalculationState, DatasetIndex, IndexRole, IndexType
from geoworkbench.project.gas_ratio_controller import GasRatioProjectController
from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.pixler_coverage import pixler_coverage
from geoworkbench.ui.gas_ratio_result import gas_ratio_result_text
from test_gas_ratio_project_controller import _session
from test_gas_ratio_reference import _dataset


def test_complete_profiles_pair_all_ratios_on_the_same_row_without_mutation():
    dataset = _dataset()
    dataset.curves["C1_C2"].values[1] = np.nan
    dataset.curves["C1_C3"].values[2] = 0.0
    dataset.curves["C1_C4"].values[2] = np.inf
    before = {name: curve.values.copy() for name, curve in dataset.curves.items()}
    result = pixler_coverage(dataset)
    assert result.total_rows == 4
    assert result.complete_rows == 2
    assert result.first_index == "100.0"
    assert result.last_index == "103.0"
    for name, values in before.items():
        np.testing.assert_array_equal(dataset.curves[name].values, values)


@pytest.mark.parametrize("state", [CalculationState.STALE, CalculationState.CALCULATING,
                                    CalculationState.ERROR])
def test_noncurrent_ratio_cannot_certify_current_profiles(state):
    dataset = _dataset()
    dataset.curves["C1_C5"].state = state
    result = pixler_coverage(dataset)
    assert result.complete_rows == 0
    assert result.unavailable_ratios == ("C1_C5",)


def test_missing_and_wrong_shape_ratios_are_explicit():
    dataset = _dataset()
    del dataset.curves["C1_C4"]
    dataset.curves["C1_C5"].values = np.array([2.0])
    result = pixler_coverage(dataset)
    assert result.complete_rows == 0
    assert result.unavailable_ratios == ("C1_C4", "C1_C5")


def test_canonical_pixler_aliases_and_descending_index():
    dataset = _dataset()
    dataset.active_index.values[:] = [103, 102, 101, 100]
    for name, curve in dataset.curves.items():
        if name.startswith("C1_"):
            curve.metadata = replace(curve.metadata, original_mnemonic=f"PIXLER_{name}",
                                     canonical_mnemonic=None)
    result = pixler_coverage(dataset)
    assert result.complete_rows == 4
    assert (result.first_index, result.last_index) == ("103.0", "100.0")


def test_datetime_index_is_preserved_and_nat_does_not_count():
    dataset = _dataset()
    values = np.array(["2026-10-16T00:00", "NaT", "2026-10-16T00:02", "2026-10-16T00:03"],
                      dtype="datetime64[m]")
    dataset.indexes["time"] = DatasetIndex("time", "TIME", IndexType.DATETIME, IndexRole.TIME,
                                           None, values)
    dataset.active_index_id = "time"
    result = pixler_coverage(dataset)
    assert result.complete_rows == 3
    assert "2026-10-16T00:03" in result.last_index
    text = gas_ratio_result_text(dataset, AppLanguage.EN)
    assert "(TIME)" in text
    assert " m" not in text.splitlines()[2]


@pytest.mark.parametrize("language", list(AppLanguage))
def test_receipt_reports_gaps_and_no_profiles_in_every_language(language):
    dataset = _dataset()
    dataset.curves["C1_C2"].values[1] = np.nan
    text = gas_ratio_result_text(dataset, language)
    assert "3/4" in text
    assert dataset.name in text
    assert "100.0–103.0" in text
    assert "PDF" in text
    del dataset.curves["C1_C5"]
    text = gas_ratio_result_text(dataset, language)
    assert "0/4" in text
    assert "C1_C5" in text
    assert "100.0–103.0" not in text


def test_explicit_recalculation_restores_complete_profiles_on_extended_tail():
    session = _session("extended-tail")
    dataset = session.current_dataset
    assert dataset is not None
    controller = GasRatioProjectController(session)
    controller.calculate_basic_ratios()
    for curve in dataset.curves.values():
        if curve.metadata.provenance.startswith("calculation:"):
            curve.values[-1] = np.nan
            curve.state = CalculationState.STALE
    assert pixler_coverage(dataset).complete_rows == 0
    outcome = controller.calculate_basic_ratios()
    coverage = pixler_coverage(outcome.dataset)
    assert coverage.complete_rows == 4
    assert coverage.last_index == "1001.5"


def test_empty_dataset_has_no_profile_bounds():
    dataset = _dataset()
    dataset.active_index.values = np.array([])
    result = pixler_coverage(dataset)
    assert result.complete_rows == 0
    assert result.first_index == result.last_index == ""


def test_main_window_logs_and_displays_calculated_dataset_summary(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import Mock
    from geoworkbench.ui.main_window import MainWindow

    session = _session("visible-result")
    messages = []
    logs = []
    monkeypatch.setattr("geoworkbench.ui.main_window.QMessageBox.information",
                        lambda parent, title, text: messages.append(text))
    window = SimpleNamespace(
        _select_gas_ratio_profile=lambda: None,
        gas_ratio_project_controller=GasRatioProjectController(session),
        curve_view=Mock(), tablet_view=Mock(), _log=logs.append,
        _t=lambda key, **kwargs: key, _refresh_tree=Mock(), _update_title=Mock(),
        statusBar=Mock(), language=AppLanguage.EN,
    )
    # Cancel leaves calculation and receipt untouched.
    MainWindow.calculate_ratios(window)
    assert not messages
    from geoworkbench.calculations.calculation_profiles import default_gas_ratio_profile
    window._select_gas_ratio_profile = default_gas_ratio_profile
    MainWindow.calculate_ratios(window)
    assert len(messages) == 1
    assert "4/4" in messages[0]
    assert "1001.5" in messages[0]
    assert messages[0] in logs
