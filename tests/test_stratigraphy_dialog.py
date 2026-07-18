import numpy as np
from PySide6.QtWidgets import QDialogButtonBox, QPushButton, QTableWidget

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.project.session import ProjectSession
from geoworkbench.project.stratigraphy_controller import StratigraphyController
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.stratigraphy_dialog import (
    StratigraphyDialog,
    StratigraphyIntervalDialog,
)


def _controller() -> StratigraphyController:
    session = ProjectSession()
    session.add_dataset(
        Dataset("dataset", "Well", DatasetKind.GTI, DepthDomain.MD, np.array([100.0, 300.0]))
    )
    return StratigraphyController(session)


def test_stratigraphy_dialog_adds_project_interval(qapp) -> None:
    controller = _controller()
    dialog = StratigraphyDialog(controller, language=AppLanguage.EN)
    dialog.top_input.setValue(100.0)
    dialog.bottom_input.setValue(200.0)
    dialog.rank_input.setCurrentText("System / Period")
    dialog.code_input.setText("K")
    dialog.name_input.setText("Cretaceous")
    dialog.color_input.setText("#7fc64e")

    dialog._add()

    table = dialog.findChild(QTableWidget, "stratigraphy-intervals-table")
    assert table is not None and table.rowCount() == 1
    assert table.horizontalHeaderItem(2).text() == "Rank"
    assert table.item(0, 3).text() == "K"
    assert dialog.findChild(QPushButton, "stratigraphy-add-button").text() == "Add"
    buttons = dialog.findChild(QDialogButtonBox)
    assert buttons is not None
    assert buttons.button(QDialogButtonBox.StandardButton.Close).text() == "Close"
    dialog.close()


def test_interval_dialog_returns_mouse_selected_depths(qapp) -> None:
    dialog = StratigraphyIntervalDialog(150.0, 175.0, language=AppLanguage.RU)
    dialog.rank_input.setCurrentText("Stage / Age")
    dialog.code_input.setText("K1a")
    dialog.name_input.setText("Альб")

    values = dialog.values()

    assert values["top_depth"] == 150.0
    assert values["bottom_depth"] == 175.0
    assert values["rank"] == "Stage / Age"
    assert values["code"] == "K1a"
    dialog.close()
