from dataclasses import replace
from time import monotonic, sleep

import numpy as np
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QPushButton, QScrollArea

from geoworkbench.domain.models import CurveData, CurveMetadata, DatasetKind
from geoworkbench.project.external_las_insert_controller import ExternalLasInsertController
from geoworkbench.services.external_las_insert import ExternalLasCurveSelection
from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.semantic_channels import SemanticChannelDictionary
from geoworkbench.ui.gis_interval_compare_dialog import GisIntervalCompareDialog
from geoworkbench.ui.gis_reference_dialog import GisReferenceDialog
from test_external_las_insert_controller import dataset as make_dataset, imported
from test_gas_interval_gis_review_ui import _with_inserted_gis
from test_gis_interval_compare import _two_curves


def _wait_review(qapp, dialog):
    deadline = monotonic() + 30.0
    while dialog._worker is not None and monotonic() < deadline:
        qapp.processEvents()
        sleep(0.005)
    qapp.processEvents()
    assert dialog._worker is None


@pytest.mark.parametrize("language", list(AppLanguage))
def test_explicit_comparison_shows_separate_values_and_blocks_stale_source(qapp, language):
    dataset = _two_curves()
    dialog = GisIntervalCompareDialog(dataset, top="100", bottom="102", language=language)
    try:
        assert dialog.table.rowCount() == 2
        dialog.table.item(0, 0).setCheckState(Qt.CheckState.Checked)
        dialog.table.item(1, 0).setCheckState(Qt.CheckState.Checked)
        dialog.review.click()
        _wait_review(qapp, dialog)
        assert dialog.status.text() == dialog._t("complete")
        assert dialog.table.item(0, 2).text() == "API"
        assert dialog.table.item(1, 2).text() == "ohm.m"
        assert dialog.table.item(0, 4).text() == "2 / 3"
        assert dialog.table.item(1, 5).text() == "1"
        assert dialog.table.item(1, 7).text() == "0–20"
        assert dialog.table.item(1, 8).text() == dialog._t("reviewed")
        dataset.curves["RT"].metadata = replace(dataset.curves["RT"].metadata, unit="invalid")
        dialog.review.click()
        _wait_review(qapp, dialog)
        assert dialog.table.item(0, 8).text() == dialog._t("reviewed")
        assert dialog.table.item(1, 4).text() == "—"
        assert dialog.table.item(1, 8).text() != dialog._t("reviewed")
        dialog.table.setCurrentCell(1, 5)
        assert dialog.missing_details.text() == dialog._t("missing_select")
        dialog.top.setText("101")
        assert dialog.table.item(0, 4).text() == "—" and not dialog.status.text()
    finally:
        dialog.close()


def test_comparison_requires_explicit_selection_and_finite_interval(qapp):
    dialog = GisIntervalCompareDialog(_two_curves(), top="100", bottom="102")
    try:
        dialog.review.click()
        assert dialog.status.text() == dialog._t("selection_required", limit=8)
        dialog.table.item(0, 0).setCheckState(Qt.CheckState.Checked)
        dialog.top.setText("invalid")
        dialog.review.click()
        assert dialog.status.text() == dialog._t("invalid")
        assert dialog.table.item(0, 4).text() == "—"
    finally:
        dialog.close()


@pytest.mark.parametrize("language", list(AppLanguage))
def test_missing_depth_details_follow_reviewed_row_and_clear_on_input_change(qapp, language):
    dataset = _two_curves()
    dialog = GisIntervalCompareDialog(dataset, top="100", bottom="102", language=language)
    try:
        for row in range(2):
            dialog.table.item(row, 0).setCheckState(Qt.CheckState.Checked)
        dialog.review.click()
        _wait_review(qapp, dialog)
        assert dialog.missing_details.text() == dialog._t(
            "missing_preview", curve="GR", depths="101", shown=1, total=1,
        )
        dialog.table.setCurrentCell(1, 5)
        assert dialog.missing_details.text() == dialog._t(
            "missing_preview", curve="RT", depths="102", shown=1, total=1,
        )
        dialog.top.setText("101")
        assert dialog.missing_details.text() == dialog._t("missing_select")
        dialog.review.click()
        _wait_review(qapp, dialog)
        dialog.table.setCurrentCell(1, 5)
        assert "102" in dialog.missing_details.text()
        dialog.top.setText("110")
        dialog.bottom.setText("120")
        dialog.review.click()
        _wait_review(qapp, dialog)
        assert dialog.missing_details.text() == dialog._t("missing_no_rows", curve="GR")
    finally:
        dialog.close()


def test_missing_details_are_bounded_and_do_not_claim_continuous_coverage(qapp):
    dataset = _two_curves()
    dataset.active_index.values = np.arange(100.0, 113.0)
    dataset.depth = dataset.active_index.values
    dataset.curves["GR"].values = np.full(13, np.nan)
    dataset.curves["RT"].values = np.ones(13)
    dialog = GisIntervalCompareDialog(dataset, top="100", bottom="112")
    try:
        for row in range(2):
            dialog.table.item(row, 0).setCheckState(Qt.CheckState.Checked)
        dialog.review.click()
        _wait_review(qapp, dialog)
        assert dialog.missing_details.text() == dialog._t(
            "missing_preview", curve="GR", depths=", ".join(str(i) for i in range(100, 110)),
            shown=10, total=13,
        )
        dialog.table.setCurrentCell(1, 5)
        assert dialog.missing_details.text() == dialog._t("missing_none", curve="RT")
    finally:
        dialog.close()


def test_missing_details_distinguish_close_depths_in_source_order(qapp):
    dataset = _two_curves()
    dataset.active_index.values = np.array([1500.0000004, 1500.0000003, 1500.0000002])
    dataset.depth = dataset.active_index.values
    dataset.curves["GR"].values = np.array([np.nan, 20.0, np.nan])
    dialog = GisIntervalCompareDialog(dataset, top="1500", bottom="1501")
    try:
        dialog.table.item(0, 0).setCheckState(Qt.CheckState.Checked)
        dialog.review.click()
        _wait_review(qapp, dialog)
        assert dialog.table.item(0, 4).text() == "1 / 3"
        assert dialog.table.item(0, 5).text() == "2"
        assert dialog.table.item(0, 8).text() == dialog._t("reviewed")
        assert dialog.missing_details.text() == dialog._t(
            "missing_preview", curve="GR", depths="1500.0000004, 1500.0000002", shown=2, total=2,
        )
    finally:
        dialog.close()


def test_observed_md_extent_distinguishes_close_depths(qapp):
    dataset = _two_curves()
    dataset.active_index.values = np.array([1500.0000006, 1500.0000004, 1500.0000002])
    dataset.depth = dataset.active_index.values
    dataset.curves["GR"].values = np.array([np.nan, 20.0, 10.0])
    dialog = GisIntervalCompareDialog(dataset, top="1500", bottom="1501")
    try:
        dialog.table.item(0, 0).setCheckState(Qt.CheckState.Checked)
        dialog.review.click()
        _wait_review(qapp, dialog)

        assert dialog.table.item(0, 4).text() == "2 / 3"
        assert dialog.table.item(0, 5).text() == "1"
        assert dialog.table.item(0, 6).text() == "1500.0000002–1500.0000004"
        assert dialog.table.item(0, 7).text() == "10–20"
        assert dialog.missing_details.text() == dialog._t(
            "missing_preview", curve="GR", depths="1500.0000006", shown=1, total=1,
        )
    finally:
        dialog.close()


def test_comparison_preserves_adjacent_observed_value_bounds(qapp):
    dataset = _two_curves()
    minimum = 20.0000002
    maximum = float(np.nextafter(minimum, np.inf))
    values = np.array([maximum, np.nan, minimum])
    dataset.curves["GR"].values[:] = values
    depths = dataset.active_index.values.copy()
    dialog = GisIntervalCompareDialog(dataset, top="100", bottom="102")
    try:
        dialog.table.item(0, 0).setCheckState(Qt.CheckState.Checked)
        dialog.review.click()
        _wait_review(qapp, dialog)

        assert dialog.table.item(0, 2).text() == "API"
        assert dialog.table.item(0, 4).text() == "2 / 3"
        assert dialog.table.item(0, 5).text() == "1"
        bounds = dialog.table.item(0, 7).text()
        assert tuple(map(float, bounds.split("–"))) == (minimum, maximum)
        np.testing.assert_array_equal(dataset.active_index.values, depths)
        np.testing.assert_array_equal(dataset.curves["GR"].values, values)
    finally:
        dialog.close()


def test_comparison_value_bounds_remain_readable_at_minimum_window_size(qapp):
    dataset = _two_curves()
    dataset.curves["GR"].values[:] = [-1.2345678901234567e100, np.nan, 1.2345678901234567e100]
    dialog = GisIntervalCompareDialog(dataset, top="100", bottom="102", language=AppLanguage.EN)
    try:
        dialog.resize(dialog.minimumSize())
        dialog.show()
        dialog.table.item(0, 0).setCheckState(Qt.CheckState.Checked)
        dialog.review.click()
        _wait_review(qapp, dialog)

        table = dialog.table
        bounds = table.item(0, 7)
        scrollbar = table.horizontalScrollBar()
        scrollbar.setValue(scrollbar.minimum())
        viewport = table.viewport().rect()
        bounds_rect = table.visualItemRect(bounds)
        assert scrollbar.maximum() > 0
        scrollbar.setValue(bounds_rect.left())
        assert viewport.contains(table.visualItemRect(bounds).topLeft())
        scrollbar.setValue(bounds_rect.right() - viewport.right())
        assert viewport.contains(table.visualItemRect(bounds).bottomRight())
    finally:
        dialog.close()


def test_missing_details_remain_readable_at_minimum_window_size(qapp):
    dataset = _two_curves()
    source_depths = [f"1500.{index:07d}" for index in range(13, 0, -1)]
    dataset.active_index.values = np.array(source_depths, dtype=float)
    dataset.depth = dataset.active_index.values
    dataset.curves["GR"].values = np.array([np.nan] * 12 + [20.0])
    dialog = GisIntervalCompareDialog(dataset, top="1499", bottom="1501", language=AppLanguage.EN)
    try:
        dialog.resize(dialog.minimumSize())
        dialog.show()
        dialog.table.item(0, 0).setCheckState(Qt.CheckState.Checked)
        dialog.review.click()
        _wait_review(qapp, dialog)

        depths = ", ".join(depth.rstrip("0") for depth in source_depths[:10])
        label = dialog.missing_details
        assert label.text() == dialog._t(
            "missing_preview", curve="GR", depths=depths, shown=10, total=12,
        )
        scroll = dialog.findChild(QScrollArea, "gis-interval-missing-details-scroll")
        assert scroll is not None and scroll.widget() is label
        height = label.heightForWidth(label.width())
        assert label.height() >= height
        bar = scroll.verticalScrollBar()
        bar.setValue(bar.maximum())
        assert scroll.viewport().height() + bar.value() >= height

        dialog.top.setText("1498")
        qapp.processEvents()
        assert label.text() == dialog._t("missing_select")
        assert bar.value() == 0
    finally:
        dialog.close()


def test_missing_values_and_outside_interval_are_distinguished(qapp):
    dataset = _two_curves()
    dataset.curves["RT"].values[:] = np.nan
    dialog = GisIntervalCompareDialog(dataset, top="100", bottom="102")
    try:
        dialog.table.item(1, 0).setCheckState(Qt.CheckState.Checked)
        dialog.review.click()
        _wait_review(qapp, dialog)
        assert dialog.table.item(1, 4).text() == "0 / 3"
        assert dialog.table.item(1, 5).text() == "3"
        assert dialog.table.item(1, 8).text() == dialog._t("no_values")
        dialog.top.setText("110")
        dialog.bottom.setText("120")
        dialog.review.click()
        _wait_review(qapp, dialog)
        assert dialog.table.item(1, 4).text() == "0 / 0"
        assert dialog.table.item(1, 8).text() == dialog._t("no_samples")
    finally:
        dialog.close()


def test_selection_limit_and_removed_curve_do_not_substitute_other_data(qapp):
    dataset = _two_curves()
    original = dataset.curves["GR"]
    for index in range(7):
        dataset.curves[f"extra-{index}"] = replace(
            original, metadata=replace(original.metadata, curve_id=f"extra-{index}"),
        )
    dialog = GisIntervalCompareDialog(dataset, top="100", bottom="102")
    try:
        assert dialog.table.rowCount() == 9
        for row in range(9):
            dialog.table.item(row, 0).setCheckState(Qt.CheckState.Checked)
        dialog.review.click()
        assert dialog.status.text() == dialog._t("selection_required", limit=8)
        for row in range(1, 9):
            dialog.table.item(row, 0).setCheckState(Qt.CheckState.Unchecked)
        del dataset.curves["GR"]
        dialog.review.click()
        _wait_review(qapp, dialog)
        assert dialog.table.item(0, 4).text() == "—"
        assert dialog.table.item(0, 8).text() == dialog._t("source_missing")
    finally:
        dialog.close()


def test_reference_dialog_opens_comparison_with_existing_bounds(qapp, monkeypatch):
    dataset = _two_curves()
    dialog = GisReferenceDialog(dataset, language=AppLanguage.EN)
    seen = []

    def inspect(compare):
        assert compare.dataset is dataset
        assert (compare.top.text(), compare.bottom.text()) == ("100.5", "102")
        assert compare.table.rowCount() == 2
        seen.append(True)
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(GisIntervalCompareDialog, "exec", inspect)
    try:
        dialog.fields["top"].setText("100.5")
        dialog.fields["base"].setText("102")
        dialog.compare_source_intervals.click()
        assert seen == [True] and dialog.sample is None
    finally:
        dialog.close()


def test_selected_gas_interval_compares_two_external_gis_curves(qapp, monkeypatch, tmp_path):
    workspace, session, receiver, combined = _with_inserted_gis(monkeypatch, tmp_path, AppLanguage.EN)
    source = make_dataset("resistivity", [100.0, 101.0, 102.0])
    source.kind = DatasetKind.GIS
    binding = SemanticChannelDictionary().resolve("RT", unit="ohm.m")
    source.curves["rt"] = CurveData(
        CurveMetadata("rt", "RT", binding.canonical_mnemonic, "ohm.m", "Resistivity",
                      source.dataset_id, "source:las", binding),
        np.array([4.0, np.nan, 12.0]),
    )
    controller = ExternalLasInsertController(session)
    monkeypatch.setattr(
        "geoworkbench.project.external_las_insert_controller.import_las_with_report",
        lambda _path: imported(source, tmp_path / "rt.las"),
    )
    controller.apply(controller.analyze_file(tmp_path / "rt.las"), (ExternalLasCurveSelection("rt", "RT"),))
    seen = []

    def inspect_comparison(dialog):
        assert (dialog.top.text(), dialog.bottom.text()) == ("100", "102")
        assert dialog.table.rowCount() == 2
        for row in range(2):
            dialog.table.item(row, 0).setCheckState(Qt.CheckState.Checked)
        dialog.review.click()
        _wait_review(qapp, dialog)
        assert {dialog.table.item(row, 2).text() for row in range(2)} == {"API", "ohm.m"}
        assert all(dialog.table.item(row, 8).text() == dialog._t("reviewed") for row in range(2))
        seen.append(True)
        return QDialog.DialogCode.Rejected

    def inspect_gis(dialog):
        assert dialog.dataset is combined and dialog.method.currentData() is None
        dialog.compare_source_intervals.click()
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(GisIntervalCompareDialog, "exec", inspect_comparison)
    monkeypatch.setattr(GisReferenceDialog, "exec", inspect_gis)
    try:
        workspace.geology_evidence_button.click()
        parent = workspace._geology_evidence_dialog
        assert parent is not None
        parent.findChild(QPushButton, "interpretation-geology-review-gis").click()
        assert seen == [True] and receiver.curves == {}
    finally:
        workspace.close()
