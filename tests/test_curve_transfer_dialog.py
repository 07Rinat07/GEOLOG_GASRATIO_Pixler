import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialogButtonBox

from geoworkbench.domain.models import CurveData, CurveMetadata, Dataset, DatasetKind, DepthDomain
from geoworkbench.project.curve_transfer_controller import CurveTransferController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.curve_transfer_dialog import CurveTransferDialog


def make_controller() -> CurveTransferController:
    session = ProjectSession()
    source = Dataset(
        "source", "GIS", DatasetKind.GIS, DepthDomain.MD, np.array([100.0, 101.0])
    )
    for curve_id, mnemonic in (("gr-source", "GR"), ("rop-source", "ROP")):
        source.curves[curve_id] = CurveData(
            CurveMetadata(curve_id, mnemonic, mnemonic, "API", None, source.dataset_id),
            np.array([10.0, 20.0]),
        )
    target = Dataset(
        "target", "GTI", DatasetKind.GTI, DepthDomain.MD, np.array([100.0, 101.0])
    )
    target.curves["gr-target"] = CurveData(
        CurveMetadata("gr-target", "GR", "GR", "API", None, target.dataset_id),
        np.array([11.0, 21.0]),
    )
    session.add_dataset(source)
    session.add_dataset(target)
    return CurveTransferController(session)


def test_dialog_previews_conflicts_and_selects_only_transferable_curves(qapp) -> None:
    dialog = CurveTransferDialog(make_controller(), language=AppLanguage.EN)
    ok_button = dialog.buttons.button(QDialogButtonBox.StandardButton.Ok)

    assert dialog.analysis is not None
    assert dialog.table.rowCount() == 2
    assert dialog.table.item(0, 0).flags() == Qt.ItemFlag.NoItemFlags
    assert "occupied" in dialog.table.item(0, 4).text().lower()
    assert dialog.table.item(1, 0).checkState() == Qt.CheckState.Checked
    assert dialog.selected_curve_ids == ("rop-source",)
    assert ok_button.isEnabled()
    assert "exact depth grid" in dialog.preview.text()
    dialog.close()


def test_dialog_disables_apply_without_other_dataset(qapp) -> None:
    session = ProjectSession()
    session.add_dataset(
        Dataset(
            "only", "Only", DatasetKind.GTI, DepthDomain.MD, np.array([0.0, 1.0])
        )
    )
    dialog = CurveTransferDialog(CurveTransferController(session))

    assert dialog.analysis is None
    assert not dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled()
    dialog.close()
