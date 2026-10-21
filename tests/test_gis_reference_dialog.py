from dataclasses import replace

import numpy as np
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QMessageBox

from geoworkbench.domain.models import (
    CalculationState, CurveData, CurveMetadata, Dataset, DatasetKind, DepthDomain,
)
from geoworkbench.services.localization import AppLanguage, Localizer
from geoworkbench.services.semantic_channels import SemanticChannelDictionary
from geoworkbench.ui.gis_reference_dialog import GisReferenceDialog


def _dataset(density=False):
    name, unit = ("RHOB", "g/cm3") if density else ("GR", "API")
    binding = SemanticChannelDictionary().resolve(name, unit=unit)
    curve = CurveData(CurveMetadata(
        "curve-1", name, binding.canonical_mnemonic, unit, "Source",
        "original-run", "source:las", binding,
    ), np.array([2.42, np.nan, 2.9] if density else [65.0, np.nan, 145.0]))
    return Dataset("gis-1", "GIS", DatasetKind.GIS, DepthDomain.MD,
                   np.array([100.0, 101.0, 102.0]), curves={"selected": curve})


def _fill(dialog, density=False):
    dialog.method.setCurrentIndex(2 if density else 1)
    dialog.channel.setCurrentIndex(1)
    for key, value in dict(calibration_id="cal-1", tool_id="tool-1", reviewer="Expert",
                           evidence="Synthetic evidence only", top="100", base="102").items():
        dialog.fields[key].setText(value)
    for field, value in zip(dialog.parameters, ("2,71", "1,0") if density else ("25", "125")):
        field.setText(value)


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("density,expected", [(False, 0.4), (True, (2.71-2.42)/1.71)])
def test_operator_evaluates_actual_row_in_three_languages(qapp, language, density, expected):
    dataset = _dataset(density)
    before = dataset.curves["selected"].values.copy()
    dialog = GisReferenceDialog(dataset, language=language)
    assert dialog.method.currentData() is None and dialog.channel.currentData() is None
    assert all(not field.text() for field in (*dialog.fields.values(), *dialog.parameters))
    _fill(dialog, density)
    dialog.calculate.click()
    assert dialog.sample.estimate.value == pytest.approx(expected)
    assert dialog.sample.md_m == 100 and dialog.sample.sample_index == 0
    assert dialog.sample.calibration.reviewer == "Expert"
    assert "cal-1" in dialog.result_label.text()
    assert dialog.result_label.textFormat() is Qt.TextFormat.PlainText
    assert dialog._t("valid") in dialog.result_label.text()
    dialog.row.setValue(3)
    assert dialog.sample is None and not dialog.result_label.text()
    dialog.calculate.click()
    assert not dialog.sample.estimate.usable_as_fraction
    dialog.fields["reviewer"].setText("Changed")
    assert dialog.sample is None and not dialog.result_label.text()
    dialog.reject()
    assert dialog.result() == QDialog.DialogCode.Rejected
    np.testing.assert_array_equal(dataset.curves["selected"].values, before)
    np.testing.assert_array_equal(dataset.active_index.values, [100, 101, 102])
    dialog.close()


@pytest.mark.parametrize("failure", ["missing", "nan", "scope", "stale", "unit", "selection"])
def test_invalid_inputs_are_blocked_without_exposing_internal_errors(qapp, failure):
    dataset = _dataset()
    dialog = GisReferenceDialog(dataset)
    _fill(dialog)
    if failure == "missing":
        dialog.fields["evidence"].clear()
    elif failure == "nan":
        dialog.row.setValue(2)
    elif failure == "scope":
        dialog.fields["base"].setText("100")
        dialog.row.setValue(3)
    elif failure == "stale":
        dataset.curves["selected"].state = CalculationState.STALE
    elif failure == "unit":
        curve = dataset.curves["selected"]
        curve.metadata = replace(curve.metadata, unit="vendor-unit")
    else:
        dialog.channel.setCurrentIndex(0)
    dialog.calculate.click()
    assert dialog.sample is None
    assert dialog.result_label.text() == dialog._t(
        "selection_required" if failure == "selection" else "invalid",
    )
    dialog.close()


def test_method_change_clears_parameters_and_previous_result(qapp):
    dialog = GisReferenceDialog(_dataset())
    _fill(dialog)
    dialog.calculate.click()
    assert dialog.sample is not None
    dialog.method.setCurrentIndex(2)
    assert all(not field.text() for field in dialog.parameters)
    assert dialog.sample is None and not dialog.result_label.text()
    assert dialog.parameter_labels[0].text() == dialog._t("matrix")
    dialog.close()


@pytest.mark.parametrize("axis", [np.array(100.0), None])
def test_invalid_scalar_axis_is_reported_without_dialog_crash(qapp, axis):
    dataset = _dataset()
    dataset.active_index.values = axis
    dialog = GisReferenceDialog(dataset)
    _fill(dialog)
    dialog.calculate.click()
    assert dialog.sample is None and dialog.result_label.text() == dialog._t("invalid")
    dialog.close()


def test_real_mainwindow_menu_localizes_and_opens_read_only_dialog(qapp, monkeypatch):
    from geoworkbench.ui.main_window import MainWindow

    window = MainWindow()
    dataset = _dataset()
    window.session.add_dataset(dataset)
    window.session.dirty = False
    observed = []

    def run(dialog):
        assert dialog.dataset is dataset
        _fill(dialog)
        dialog.calculate.click()
        observed.append(dialog.sample)
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(GisReferenceDialog, "exec", run)
    for language in AppLanguage:
        window.change_language(language)
        assert window.gis_reference_action.text() == Localizer.create(language).text(
            "petro_reference.action",
        )
        window.gis_reference_action.trigger()
    assert len(observed) == 3 and all(sample is not None for sample in observed)
    assert not window.session.dirty
    messages = []
    monkeypatch.setattr(QMessageBox, "information", lambda *args: messages.append(args[2]))
    dataset.kind = DatasetKind.GTI
    window.gis_reference_action.trigger()
    assert messages == [window._t("petro_reference.select_gis")]
    assert len(observed) == 3
    window.close()
