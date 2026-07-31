from __future__ import annotations

import numpy as np
from PySide6.QtWidgets import QTableWidgetItem

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.project.interpretation_calculation_controller import (
    InterpretationCalculationController,
)
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.drilling_input_plan import InputSourceMode
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.drilling_calculation_dialog import DrillingCalculationDialog
from geoworkbench.ui.interpretation_report_workspace import InterpretationReportWorkspace


def _controller() -> InterpretationCalculationController:
    session = ProjectSession()
    session.add_dataset(
        Dataset(
            "dataset",
            "Well data",
            DatasetKind.GTI,
            DepthDomain.MD,
            np.array([1000.0, 1001.0, 1002.0]),
        )
    )
    return InterpretationCalculationController(session)


def test_dialog_builds_interval_bit_plan(qapp) -> None:
    controller = _controller()
    dialog = DrillingCalculationDialog(controller, language=AppLanguage.RU)

    assert dialog.objectName() == "drillingCalculationDialog"
    assert dialog.bit_table.objectName() == "bitSectionTable"
    section_index = dialog.bit_mode.findData(InputSourceMode.SECTIONS.value)
    dialog.bit_mode.setCurrentIndex(section_index)
    dialog.bit_table.setItem(0, 0, QTableWidgetItem("1000"))
    dialog.bit_table.setItem(0, 1, QTableWidgetItem("1002"))
    dialog.bit_table.setItem(0, 2, QTableWidgetItem("155.6"))

    dialog.accept()

    request = dialog.request()
    assert request.plan.bit.mode is InputSourceMode.SECTIONS
    assert request.plan.bit_sections[0].value == 155.6
    assert request.plan.bit_sections[0].unit == "mm"
    dialog.close()


def test_interpretation_workspace_exposes_shared_drilling_dialog(qapp) -> None:
    workspace = InterpretationReportWorkspace(_controller(), language=AppLanguage.RU)
    workspace.show()
    qapp.processEvents()

    assert workspace.configure_drilling_inputs_button.isVisible()
    assert "BIT" in workspace.configure_drilling_inputs_button.text()
    assert "общие входы" in workspace.drilling_input_status.text().casefold()
    workspace.close()
