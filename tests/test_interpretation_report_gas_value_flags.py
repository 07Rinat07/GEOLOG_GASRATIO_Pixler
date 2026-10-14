"""Gas VALUE authoring accepts only factual source samples."""

import numpy as np
import pytest
from PySide6.QtWidgets import QDialogButtonBox

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.project.controller import ProjectController
from geoworkbench.project.report_annotation_controller import ReportAnnotationController
from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.report_gas_value_flags import (
    report_gas_channels, report_gas_value_at_depth,
)
from geoworkbench.ui.interpretation_gas_value_flag_dialog import ReportGasValueFlagDialog
from test_report_annotations import _session


def _dataset() -> Dataset:
    dataset = Dataset(
        "gas-flags", "Gas flags", DatasetKind.GTI, DepthDomain.MD,
        np.array([1000., 1001., 1002., 1100.]),
    )
    dataset.upsert_curve("C1", np.array([10., np.nan, 12., 18.]), unit="%")
    dataset.upsert_curve("NC4", np.array([0.1, 0.2, 0.3, 0.4]), unit="ppm")
    dataset.upsert_curve("TG", np.array([8., 9., 10., 11.]), unit="%")
    dataset.upsert_curve("ROP", np.array([1., 2., 3., 4.]), unit="m/h")
    return dataset


def test_report_gas_value_source_not_interpolated_or_substituted() -> None:
    dataset = _dataset()
    before = dataset.curve_by_mnemonic("C1").values.copy()
    assert report_gas_channels(dataset) == ("C1", "NC4", "TG")
    assert report_gas_value_at_depth(dataset, "ROP", 1001.) is None
    assert report_gas_value_at_depth(dataset, "C1", 1001.) is None
    assert report_gas_value_at_depth(dataset, "C1", 1050.) is None
    assert report_gas_value_at_depth(dataset, "C1", 950.) is None
    assert report_gas_value_at_depth(dataset, "C1", float("nan")) is None
    selected = report_gas_value_at_depth(dataset, "NC4", 1001.1)
    assert selected is not None
    assert selected.mnemonic == "NC4"
    assert selected.depth == 1001.
    assert selected.value == 0.2
    assert selected.row_index == 1
    assert selected.caption == "NC4: 0.2 ppm · MD 1001 m"
    np.testing.assert_array_equal(dataset.curve_by_mnemonic("C1").values, before)


def test_report_gas_value_repeated_depth_does_not_pick_arbitrary_source_row() -> None:
    dataset = Dataset(
        "repeated", "Repeated", DatasetKind.GTI, DepthDomain.MD,
        np.array([1000., 1001., 1001., 1002.]),
    )
    dataset.upsert_curve("TG", np.array([9., 12., 20., 13.]), unit="%")
    assert report_gas_value_at_depth(dataset, "TG", 1001.) is None
    dataset.curve_by_mnemonic("TG").values[2] = 12.
    sample = report_gas_value_at_depth(dataset, "TG", 1001.)
    assert sample is not None
    assert sample.value == 12.


@pytest.mark.parametrize("language", list(AppLanguage))
def test_report_gas_value_dialog_disables_missing_source(qapp, language) -> None:
    dialog = ReportGasValueFlagDialog(_dataset(), language=language)
    try:
        button = dialog.buttons.button(QDialogButtonBox.StandardButton.Ok)
        dialog.channel.setCurrentIndex(dialog.channel.findData("C1"))
        dialog.depth.setValue(1001.)
        assert not button.isEnabled()
        assert dialog.selected_sample() is None
        dialog.accept()
        assert dialog.result() == 0
        dialog.channel.setCurrentIndex(dialog.channel.findData("NC4"))
        assert button.isEnabled()
        assert dialog.selected_sample().caption == "NC4: 0.2 ppm · MD 1001 m"
    finally:
        dialog.close()


@pytest.mark.parametrize("extension", [".json", ".geologpkg"])
def test_source_gas_callout_remains_report_scoped_after_reopen(tmp_path, extension) -> None:
    session = _session()
    dataset = session.current_dataset
    dataset.upsert_curve("C2", np.array([2., 3., 4.]), unit="%")
    before = dataset.curve_by_mnemonic("C2").values.copy()
    sample = report_gas_value_at_depth(dataset, "C2", 1001.)
    assert sample is not None
    controller = ReportAnnotationController(session)
    annotation = controller.add(
        kind="callout", anchor="depth", depth=sample.depth,
        text=sample.caption, track_key=None,
    )
    target = tmp_path / ("report-gas-flag" + extension)
    ProjectController(session=session).save_project(target)
    reopened = ProjectController().open_project(target)
    record = ReportAnnotationController(reopened).available()[0]
    assert record.annotation_id == annotation.annotation_id
    assert record.text == "C2: 3 % · MD 1001 m"
    assert record.depth == 1001.
    assert record.track_key is None
    np.testing.assert_array_equal(dataset.curve_by_mnemonic("C2").values, before)
    np.testing.assert_array_equal(reopened.current_dataset.curve_by_mnemonic("C2").values, before)
