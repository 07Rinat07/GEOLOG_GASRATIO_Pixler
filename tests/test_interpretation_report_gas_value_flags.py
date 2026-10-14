"""Gas VALUE authoring accepts only factual source samples."""

from dataclasses import replace

import numpy as np
import pytest
from PySide6.QtWidgets import QDialogButtonBox

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.project.controller import ProjectController
from geoworkbench.project.report_annotation_controller import ReportAnnotationController
from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.semantic_channels import SemanticChannelDictionary
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
        dialog.depth_spin.setValue(1001.)
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


def test_report_gas_flags_include_ratios_opus_and_extended_source_aliases() -> None:
    dataset = Dataset(
        "all-gas", "Gas interpretation", DatasetKind.GTI,
        DepthDomain.MD, np.array([3500., 3501., 3502.]),
    )
    for mnemonic in (
        "TG", "WH", "BH", "CH", "OPUS3", "OPUS4",
        "C1_C2", "IC4_NC4", "PIXLER_C1_C2", "OPUS_RATIO_C1_C2",
        "TG_NORM", "OPUS_TG_PCT",
    ):
        dataset.upsert_curve(mnemonic, np.array([2., 3., 4.]), unit="%")
    dataset.upsert_curve("WOB", np.array([9., 10., 11.]), unit="т")
    dataset.upsert_curve("ROP", np.array([1., 2., 3.]), unit="м/ч")
    assert set(report_gas_channels(dataset)) == {
        "TG", "WH", "BH", "CH", "OPUS3", "OPUS4",
        "C1_C2", "IC4_NC4", "PIXLER_C1_C2", "OPUS_RATIO_C1_C2",
        "TG_NORM", "OPUS_TG_PCT",
    }
    sample = report_gas_value_at_depth(dataset, "OPUS3", 3501.)
    assert sample is not None
    assert sample.value == 3.
    assert sample.caption == "OPUS3: 3 % · MD 3501 m"
    assert report_gas_value_at_depth(dataset, "WOB", 3501.) is None
    assert report_gas_value_at_depth(dataset, "ROP", 3501.) is None


def test_vendor_gas_uses_resolved_semantic_binding_without_guessing_sensor_units() -> None:
    dataset = Dataset(
        "gas-semantic", "Semantic channels", DatasetKind.GTI,
        DepthDomain.MD, np.array([100., 101.]),
    )
    vendor = dataset.upsert_curve("VENDOR_CH4", np.array([1., 2.]), unit="%")
    vendor.metadata = replace(
        vendor.metadata,
        semantic=SemanticChannelDictionary().resolve(
            "C1", source_mnemonic="VENDOR_CH4", unit="%"
        ),
    )
    # A percentage alone is not proof that a channel measures gas.
    dataset.upsert_curve("VENDOR_UNKNOWN", np.array([4., 5.]), unit="%")
    wrongly_named = dataset.upsert_curve("C3", np.array([8., 9.]), unit="т")
    wrongly_named.metadata = replace(
        wrongly_named.metadata,
        semantic=SemanticChannelDictionary().resolve("WOB", unit="т"),
    )
    assert report_gas_channels(dataset) == ("VENDOR_CH4",)
    selected = report_gas_value_at_depth(dataset, "VENDOR_CH4", 101.)
    assert selected is not None
    assert selected.caption == "VENDOR_CH4: 2 % · MD 101 m"
    assert report_gas_value_at_depth(dataset, "C3", 101.) is None


def test_tvd_depth_cannot_be_silently_labelled_as_measured_md() -> None:
    dataset = Dataset(
        "tvd-gas", "TVD-only", DatasetKind.GTI,
        DepthDomain.TVD, np.array([1000., 1001.]),
    )
    dataset.upsert_curve("TG", np.array([1., 2.]), unit="%")
    assert report_gas_value_at_depth(dataset, "TG", 1001.) is None
