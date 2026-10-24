from dataclasses import replace

import numpy as np
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QDialog, QMessageBox

from geoworkbench.domain.models import (
    CalculationState, CurveData, CurveMetadata, Dataset, DatasetKind, DepthDomain,
)
from geoworkbench.services.localization import AppLanguage, Localizer
from geoworkbench.services.semantic_channels import SemanticChannelDictionary
from geoworkbench.ui.gis_reference_dialog import GisReferenceDialog
from geoworkbench.ui.gis_input_inventory_dialog import GisInputInventoryDialog


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
@pytest.mark.parametrize("descending", [False, True])
def test_source_sample_preview_preserves_exact_row_and_missing_values(qapp, language, descending):
    dataset = _dataset()
    if descending:
        dataset.active_index.values = np.array([102.0, 101.0, 100.0])
    curve = dataset.curves["selected"]
    before = curve.values.copy()
    depths = dataset.active_index.values.copy()
    dialog = GisReferenceDialog(dataset, language=language)
    try:
        dialog.method.setCurrentIndex(1)
        dialog.channel.setCurrentIndex(1)
        dialog.review_source.click()
        assert dialog.source_sample_label.text() == dialog._t(
            "source_sample", row=1, md="102" if descending else "100", value="65", unit="API",
        )
        assert dialog.source_sample_label.textFormat() is Qt.TextFormat.PlainText
        assert dialog.sample is None and not dialog.result_label.text()
        assert all(not field.text() for field in dialog.fields.values())
        dialog.row.setValue(2)
        assert not dialog.source_sample_label.text()
        dialog.review_source.click()
        assert dialog.source_sample_label.text() == dialog._t("sample_unavailable")
        dialog.row.setValue(3)
        dialog.review_source.click()
        assert dialog.source_sample_label.text() == dialog._t(
            "source_sample", row=3, md="100" if descending else "102", value="145", unit="API",
        )
        dialog.channel.setCurrentIndex(0)
        assert not dialog.source_sample_label.text()
        np.testing.assert_array_equal(curve.values, before)
        np.testing.assert_array_equal(dataset.active_index.values, depths)
    finally:
        dialog.close()


@pytest.mark.parametrize("change", ["shrink", "inf", "axis", "stale", "removed"])
def test_sample_preview_rechecks_changed_source_and_never_retains_old_value(qapp, change):
    dataset = _dataset()
    curve = dataset.curves["selected"]
    dialog = GisReferenceDialog(dataset)
    try:
        dialog.method.setCurrentIndex(1)
        dialog.channel.setCurrentIndex(1)
        dialog.row.setValue(3)
        dialog.review_source.click()
        assert "145" in dialog.source_sample_label.text()
        if change == "shrink":
            dataset.active_index.values = np.array([100.0])
            curve.values = np.array([65.0])
        elif change == "inf":
            curve.values[2] = np.inf
        elif change == "axis":
            dataset.active_index.unit = "ft"
        elif change == "stale":
            curve.state = CalculationState.STALE
        else:
            dataset.curves.clear()
        dialog.review_source.click()
        assert "145" not in dialog.source_sample_label.text()
        assert dialog.sample is None
        if change in {"shrink", "inf"}:
            assert dialog.source_sample_label.text() == dialog._t("sample_unavailable")
        else:
            assert not dialog.source_sample_label.text()
    finally:
        dialog.close()


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("failure,issue", [
    ("unit", "petro_reference.issue.method_unit_mismatch"),
    ("family", "petro_reference.issue.method_family_mismatch"),
    ("missing", "petro_reference.issue.curve_not_found"),
    ("identity", "gis_inventory.issue.missing_curve_id"),
    ("axis", "gis_inventory.issue.unverified_metre_md_alignment"),
    ("stale", "gis_inventory.issue.curve_not_current"),
])
def test_source_review_explains_blockers_without_calibration(qapp, language, failure, issue):
    dataset = _dataset()
    curve = dataset.curves["selected"]
    values = curve.values.copy()
    dialog = GisReferenceDialog(dataset, language=language)
    dialog.method.setCurrentIndex(1)
    dialog.channel.setCurrentIndex(1)
    if failure == "unit":
        binding = SemanticChannelDictionary().resolve("GR", unit="uR/h")
        curve.metadata = replace(curve.metadata, unit="uR/h", semantic=binding)
    elif failure == "family":
        dialog.method.setCurrentIndex(2)
    elif failure == "missing":
        dataset.curves.clear()
    elif failure == "identity":
        curve.metadata = replace(curve.metadata, curve_id="")
    elif failure == "axis":
        dataset.active_index.unit = "ft"
    else:
        curve.state = CalculationState.STALE
    metadata = curve.metadata
    try:
        dialog.review_source.click()
        text = dialog.source_review_label.text()
        assert dialog.localizer.text(issue) in text
        assert "gis_inventory." not in text and "petro_reference." not in text
        assert dialog.source_review_label.textFormat() is Qt.TextFormat.PlainText
        assert dialog.sample is None and not dialog.result_label.text()
        assert all(not field.text() for field in dialog.fields.values())
        assert curve.metadata is metadata
        np.testing.assert_array_equal(curve.values, values)
        np.testing.assert_array_equal(dataset.active_index.values, [100, 101, 102])
    finally:
        dialog.close()


@pytest.mark.parametrize("language", list(AppLanguage))
def test_source_review_refreshes_live_state_and_clears_on_selection_change(qapp, language):
    dataset = _dataset()
    dialog = GisReferenceDialog(dataset, language=language)
    try:
        dialog.review_source.click()
        assert dialog.source_review_label.text() == dialog._t("selection_required")
        _fill(dialog)
        dialog.review_source.click()
        assert dialog.source_review_label.text() == dialog._t("source_ready")
        assert dialog.sample is None
        dataset.curves["selected"].state = CalculationState.STALE
        dialog.calculate.click()
        assert dialog.sample is None
        assert dialog.localizer.text("gis_inventory.issue.curve_not_current") in (
            dialog.source_review_label.text()
        )
        assert dialog.result_label.text() == dialog._t("invalid")
        dataset.curves["selected"].state = CalculationState.CURRENT
        dialog.review_source.click()
        assert dialog.source_review_label.text() == dialog._t("source_ready")
        assert not dialog.result_label.text()
        dialog.method.setCurrentIndex(2)
        assert not dialog.source_review_label.text()
        dialog.review_source.click()
        dialog.channel.setCurrentIndex(0)
        assert not dialog.source_review_label.text()
        assert dialog.fields["calibration_id"].text() == "cal-1"
    finally:
        dialog.close()


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


@pytest.mark.parametrize("language", list(AppLanguage))
def test_source_inventory_shows_descending_md_and_finite_pairs(qapp, language):
    dataset = _dataset()
    dataset.active_index.values = np.array([102.0, 101.0, 100.0])
    depths = dataset.active_index.values.copy()
    values = dataset.curves["selected"].values.copy()
    dialog = GisInputInventoryDialog(dataset, language=language)
    assert dialog.inventory.axis_issues == ()
    assert dialog.table.rowCount() == 1
    assert dialog.table.item(0, 2).text() == "2"
    assert dialog.table.item(0, 3).text() == "100 – 102"
    assert dialog.table.item(0, 4).text() == "original-run"
    assert dialog.table.item(0, 5).text() == dialog._t("ok")
    assert dialog._t("direction_descending") in dialog.axis_label.text()
    assert dialog.table.editTriggers() == QAbstractItemView.EditTrigger.NoEditTriggers
    dialog.close()
    np.testing.assert_array_equal(dataset.active_index.values, depths)
    np.testing.assert_array_equal(dataset.curves["selected"].values, values)


@pytest.mark.parametrize("language", list(AppLanguage))
def test_source_inventory_reports_invalid_axis_and_stale_curve(qapp, language):
    dataset = _dataset()
    dataset.active_index.values = np.array([100.0, 100.0, 102.0])
    dataset.curves["selected"].state = CalculationState.STALE
    dialog = GisInputInventoryDialog(dataset, language=language)
    assert "ambiguous_depth_order" in dialog.inventory.axis_issues
    assert dialog._t("direction_unknown") in dialog.axis_label.text()
    assert dialog.table.item(0, 3).text() == "—"
    assert dialog.localizer.text("gis_inventory.issue.ambiguous_depth_order") in (
        dialog.axis_label.text()
    )
    assert dialog.localizer.text("gis_inventory.issue.curve_not_current") in (
        dialog.table.item(0, 5).text()
    )
    dialog.close()


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("curve_id", ["", "  \t"])
def test_inventory_reports_missing_identity_before_reference_calculation(qapp, language, curve_id):
    from geoworkbench.services.gis_reference_input_review import review_gis_reference_input

    dataset = _dataset()
    curve = dataset.curves["selected"]
    curve.metadata = replace(curve.metadata, curve_id=curve_id)
    metadata = curve.metadata
    values = curve.values.copy()
    dialog = GisInputInventoryDialog(dataset, language=language)
    try:
        warning = dialog._t("issue.missing_curve_id")
        assert not warning.startswith("gis_inventory.")
        assert dialog.table.item(0, 5).text() == warning
        assert dialog.inventory.curves[0].curve_id == curve_id
        review = review_gis_reference_input(
            dataset, method_id="igr-linear-1", curve_key="selected",
        )
        assert not review.ready_for_calibration
        assert "missing_curve_id" in review.issues
        assert curve.metadata is metadata
        np.testing.assert_array_equal(curve.values, values)
        np.testing.assert_array_equal(dataset.active_index.values, [100, 101, 102])
    finally:
        dialog.close()


def test_inventory_button_refreshes_source_without_recalculating(qapp, monkeypatch):
    dataset = _dataset()
    dialog = GisReferenceDialog(dataset, language=AppLanguage.EN)
    _fill(dialog)
    dialog.calculate.click()
    sample = dialog.sample
    assert sample is not None
    seen = []

    def inspect(inventory_dialog):
        seen.append((
            inventory_dialog.inventory.curves[0].issues,
            inventory_dialog.localizer.language,
        ))
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(GisInputInventoryDialog, "exec", inspect)
    dialog.inventory_button.click()
    dataset.curves["selected"].state = CalculationState.STALE
    dialog.inventory_button.click()
    assert seen == [((), AppLanguage.EN), (("curve_not_current",), AppLanguage.EN)]
    assert dialog.sample is sample
    assert dialog.fields["calibration_id"].text() == "cal-1"
    dialog.close()


def _inventory_details(dialog):
    return {
        dialog.details.item(row, 0).text(): dialog.details.item(row, 1).text()
        for row in range(dialog.details.rowCount())
    }


@pytest.mark.parametrize("language", list(AppLanguage))
def test_inventory_selection_shows_saved_provenance_as_literal_text(qapp, language):
    dataset = _dataset()
    curve = dataset.curves["selected"]
    hostile = '<b>Жыныс & rock</b><img src="file:///not-loaded">'
    curve.metadata = replace(
        curve.metadata, provenance=hostile,
        semantic=replace(curve.metadata.semantic, evidence=(hostile, "raw evidence")),
    )
    metadata = curve.metadata
    values = curve.values.copy()
    depths = dataset.active_index.values.copy()
    dialog = GisInputInventoryDialog(dataset, language=language)
    assert dialog.details.rowCount() == 0
    dialog.table.selectRow(0)
    details = _inventory_details(dialog)
    assert details == {
        dialog._t("dataset_id"): dataset.dataset_id,
        dialog._t("axis_id"): dataset.active_index.index_id,
        dialog._t("curve_id"): "curve-1",
        dialog._t("curve_key"): "selected",
        dialog._t("original_mnemonic"): "GR",
        dialog._t("canonical_mnemonic"): metadata.semantic.canonical_mnemonic,
        dialog._t("family"): metadata.semantic.family,
        dialog._t("source"): "original-run",
        dialog._t("provenance"): hostile,
        dialog._t("version"): str(curve.version),
        dialog._t("semantic_evidence"): hostile + "\nraw evidence",
    }
    assert dialog.details.isVisibleTo(dialog)
    assert dialog.details.editTriggers() == QAbstractItemView.EditTrigger.NoEditTriggers
    assert all(not key.startswith("gis_inventory.") for key in details)
    # QTableWidgetItem display data is plain text; imported markup stays literal.
    assert dialog.details.item(8, 1).data(Qt.ItemDataRole.DisplayRole) == hostile
    dialog.table.clearSelection()
    assert dialog.details.rowCount() == 0
    assert curve.metadata is metadata
    np.testing.assert_array_equal(curve.values, values)
    np.testing.assert_array_equal(dataset.active_index.values, depths)
    dialog.close()


@pytest.mark.parametrize("language", list(AppLanguage))
def test_inventory_details_switch_clear_and_preserve_missing_evidence(qapp, language):
    dataset = _dataset()
    dataset.curves["unknown"] = CurveData(
        CurveMetadata("unknown-id", "VENDOR", None, None, "", "", "", None),
        np.array([1.0, 2.0, 3.0]),
    )
    dialog = GisInputInventoryDialog(dataset, language=language)
    dialog.table.selectRow(0)
    assert _inventory_details(dialog)[dialog._t("curve_id")] == "curve-1"
    dialog.table.selectRow(1)
    details = _inventory_details(dialog)
    assert details[dialog._t("curve_id")] == "unknown-id"
    for key in ("canonical_mnemonic", "family", "source", "provenance", "semantic_evidence"):
        assert details[dialog._t(key)] == dialog._t("not_recorded")
    dialog.table.clearSelection()
    assert dialog.details.rowCount() == 0
    dialog.close()
    dataset.curves.clear()
    empty = GisInputInventoryDialog(dataset, language=language)
    assert empty.table.rowCount() == empty.details.rowCount() == 0
    empty.close()


def test_inventory_details_use_qc_snapshot_and_refresh_only_on_reopen(qapp):
    dataset = _dataset()
    curve = dataset.curves["selected"]
    dialog = GisInputInventoryDialog(dataset)
    curve.metadata = replace(curve.metadata, provenance="changed", semantic=None)
    dialog.table.selectRow(0)
    assert _inventory_details(dialog)[dialog._t("provenance")] == "source:las"
    assert dialog.table.item(0, 5).text() == dialog._t("ok")
    reopened = GisInputInventoryDialog(dataset)
    reopened.table.selectRow(0)
    assert _inventory_details(reopened)[reopened._t("provenance")] == "changed"
    assert _inventory_details(reopened)[reopened._t("family")] == reopened._t("not_recorded")
    assert reopened.localizer.text("gis_inventory.issue.unverified_semantics") in (
        reopened.table.item(0, 5).text()
    )
    dialog.close()
    reopened.close()


@pytest.mark.parametrize("language", list(AppLanguage))
def test_axis_evidence_is_available_without_curve_selection_and_stays_literal(qapp, language):
    dataset = _dataset()
    evidence = ('<b>MD & тереңдік</b><img src="file:///not-loaded">', "source marker")
    dataset.active_index.evidence = evidence
    depths = dataset.active_index.values.copy()
    dialog = GisInputInventoryDialog(dataset, language=language)
    dialog.detail_tabs.setCurrentWidget(dialog.axis_details)
    assert dialog.axis_details.isVisibleTo(dialog)
    assert dialog.detail_tabs.tabText(1) == dialog._t("axis_details_tab")
    assert not dialog.detail_tabs.tabText(1).startswith("gis_inventory.")
    assert dialog.details.rowCount() == 0
    assert dialog.axis_details.item(0, 1).text() == dataset.dataset_id
    assert dialog.axis_details.item(1, 1).text() == dataset.active_index.index_id
    assert dialog.axis_details.item(2, 1).text() == "m"
    assert dialog.axis_details.item(3, 1).data(Qt.ItemDataRole.DisplayRole) == "\n".join(evidence)
    assert dialog.axis_details.item(4, 1).text() == dialog._t("ok")
    assert dialog.axis_details.editTriggers() == QAbstractItemView.EditTrigger.NoEditTriggers
    dialog.table.selectRow(0)
    dialog.table.clearSelection()
    assert dialog.details.rowCount() == 0
    assert dialog.axis_details.item(3, 1).text() == "\n".join(evidence)
    np.testing.assert_array_equal(dataset.active_index.values, depths)
    assert dataset.active_index.evidence == evidence
    dialog.close()


@pytest.mark.parametrize("language", list(AppLanguage))
def test_axis_evidence_empty_dataset_and_unverified_unit_remain_explicit(qapp, language):
    dataset = _dataset()
    dataset.curves.clear()
    dataset.active_index.unit = "ft"
    dataset.active_index.evidence = ()
    dialog = GisInputInventoryDialog(dataset, language=language)
    dialog.detail_tabs.setCurrentWidget(dialog.axis_details)
    assert dialog.table.rowCount() == dialog.details.rowCount() == 0
    assert dialog.axis_details.item(2, 1).text() == "ft"
    assert dialog.axis_details.item(3, 1).text() == dialog._t("not_recorded")
    assert dialog.axis_details.item(4, 1).text() == dialog.localizer.text(
        "gis_inventory.issue.unverified_metre_md_alignment",
    )
    assert dataset.active_index.unit == "ft"
    dialog.close()


def test_axis_details_and_qc_share_snapshot_until_reopen(qapp):
    dataset = _dataset()
    dataset.active_index.evidence = ("opening evidence",)
    dialog = GisInputInventoryDialog(dataset)
    dataset.active_index.evidence = ("changed evidence",)
    dataset.active_index.unit = "ft"
    dialog.detail_tabs.setCurrentWidget(dialog.axis_details)
    assert dialog.axis_details.item(2, 1).text() == "m"
    assert dialog.axis_details.item(3, 1).text() == "opening evidence"
    assert dialog.axis_details.item(4, 1).text() == dialog._t("ok")
    reopened = GisInputInventoryDialog(dataset)
    assert reopened.axis_details.item(2, 1).text() == "ft"
    assert reopened.axis_details.item(3, 1).text() == "changed evidence"
    assert reopened.axis_details.item(4, 1).text() == reopened.localizer.text(
        "gis_inventory.issue.unverified_metre_md_alignment",
    )
    dialog.close()
    reopened.close()
