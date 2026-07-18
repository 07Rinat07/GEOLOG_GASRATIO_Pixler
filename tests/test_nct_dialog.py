import numpy as np
from PySide6.QtWidgets import QDialogButtonBox

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.project.nct_controller import NctCalculationController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.nct_dialog import NctCalculationDialog


def make_controller() -> NctCalculationController:
    dataset = Dataset(
        "dataset", "Well", DatasetKind.GTI, DepthDomain.MD,
        np.array([1000.0, 1100.0, 1200.0, 1300.0]),
    )
    dataset.upsert_curve(
        "DEXPC", np.array([1.0, 1.1, 1.2, 0.9]), unit="dimensionless"
    )
    session = ProjectSession()
    session.add_dataset(dataset)
    return NctCalculationController(session)


def test_nct_dialog_calculates_and_localizes(qapp) -> None:
    dialog = NctCalculationDialog(
        make_controller(), 1000.0, 1300.0, language=AppLanguage.EN
    )
    dialog.bottom_input.setValue(1200.0)

    dialog._calculate()

    assert dialog.calculation_result is not None
    assert dialog.calculation_result.calibration_points == 3
    assert dialog.windowTitle() == "Calibrate NCT from DEXPC"
    assert "3 points" in dialog.summary.text()
    assert dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).text() == "Build NCT"
