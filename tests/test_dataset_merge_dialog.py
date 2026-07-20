import numpy as np
from PySide6.QtWidgets import QDialogButtonBox

from geoworkbench.domain.models import CurveData, CurveMetadata, Dataset, DatasetKind, DepthDomain
from geoworkbench.project.dataset_merge_controller import DatasetMergeController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.dataset_merge_dialog import DatasetMergeDialog


def make_controller(*, conflict: bool = False) -> DatasetMergeController:
    session = ProjectSession()
    source = Dataset("source", "Source", DatasetKind.GIS, DepthDomain.MD, np.array([100.0, 101.0]))
    source.curves["gr-source"] = CurveData(
        CurveMetadata("gr-source", "GR", "GR", "API", None, source.dataset_id),
        np.array([10.0, 11.0]),
    )
    target = Dataset("target", "Target", DatasetKind.GTI, DepthDomain.MD, np.array([101.0, 102.0]))
    target_mnemonic = "GR" if conflict else "ROP"
    target.curves["target-curve"] = CurveData(
        CurveMetadata(
            "target-curve",
            target_mnemonic,
            target_mnemonic,
            "m/h",
            None,
            target.dataset_id,
        ),
        np.array([20.0, 21.0]),
    )
    session.add_dataset(source)
    session.add_dataset(target)
    return DatasetMergeController(session)


def test_merge_dialog_previews_safe_union(qapp) -> None:
    dialog = DatasetMergeDialog(make_controller(), language=AppLanguage.EN)
    ok_button = dialog.buttons.button(QDialogButtonBox.StandardButton.Ok)

    assert dialog.analysis is not None
    assert dialog.analysis.merged_sample_count == 3
    assert dialog.analysis.overlap_sample_count == 1
    assert "result samples: 3" in dialog.preview.text()
    assert dialog.conflicts.item(0).text() == "No conflicts"
    assert ok_button.isEnabled()
    dialog.close()


def test_merge_dialog_blocks_mnemonic_conflicts(qapp) -> None:
    dialog = DatasetMergeDialog(make_controller(conflict=True), language=AppLanguage.EN)

    assert dialog.analysis is not None
    assert dialog.conflicts.item(0).text() == "GR"
    assert not dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled()
    dialog.close()


def test_merge_dialog_disables_apply_without_source(qapp) -> None:
    session = ProjectSession()
    session.add_dataset(
        Dataset("only", "Only", DatasetKind.GTI, DepthDomain.MD, np.array([0.0, 1.0]))
    )
    dialog = DatasetMergeDialog(DatasetMergeController(session))

    assert dialog.analysis is None
    assert not dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled()
    dialog.close()
