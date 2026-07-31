from __future__ import annotations

from PySide6.QtCore import Qt

from geoworkbench.project.interpretation_calculation_controller import (
    InterpretationCalculationController,
    NormalizedGasCalculationMode,
)
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.interpretation_report_workspace import InterpretationReportWorkspace


def test_normalized_gas_panel_is_visible_opaque_and_controls_local_inputs(qapp) -> None:
    workspace = InterpretationReportWorkspace(
        InterpretationCalculationController(ProjectSession()),
        language=AppLanguage.RU,
    )
    workspace.resize(1_200, 800)
    workspace.show()
    qapp.processEvents()

    assert workspace.testAttribute(Qt.WidgetAttribute.WA_StyledBackground)
    assert workspace.normalized_gas_panel.testAttribute(
        Qt.WidgetAttribute.WA_StyledBackground
    )
    assert workspace.normalized_gas_panel.isVisible()
    assert "QComboBox QAbstractItemView" in workspace.styleSheet()
    assert "palette(base)" in workspace.styleSheet()

    combo = workspace.normalized_gas_mode
    assert combo.objectName() == "normalizedGasMode"
    assert combo.count() == 3
    assert combo.minimumWidth() >= 520
    assert combo.currentData() == NormalizedGasCalculationMode.COMPARE.value
    assert "сопоставить оба" in combo.currentText()
    assert workspace.rop_reference.isEnabled()
    assert "Рассчитать локальный" in workspace.calculate_normalized_gas_button.text()
    assert "Показать кривые" in workspace.show_normalized_gas_button.text()

    server_index = combo.findData(NormalizedGasCalculationMode.SERVER.value)
    combo.setCurrentIndex(server_index)
    qapp.processEvents()
    assert not workspace.rop_reference.isEnabled()
    assert not workspace.bit_reference.isEnabled()
    assert not workspace.flow_reference.isEnabled()
    assert not workspace.calculate_normalized_gas_button.isEnabled()
    assert "сервер" in workspace.normalized_gas_mode_help.text().casefold()

    local_index = combo.findData(NormalizedGasCalculationMode.LOCAL.value)
    combo.setCurrentIndex(local_index)
    qapp.processEvents()
    assert workspace.rop_reference.isEnabled()
    assert workspace.bit_reference.isEnabled()
    assert workspace.flow_reference.isEnabled()
    assert "tg_norm_calc" in workspace.normalized_gas_mode_help.text().casefold()
    workspace.close()


def test_normalized_gas_panel_labels_are_retranslated(qapp) -> None:
    workspace = InterpretationReportWorkspace(
        InterpretationCalculationController(ProjectSession()),
        language=AppLanguage.RU,
    )
    workspace.show()
    qapp.processEvents()

    workspace.set_language(AppLanguage.KK)
    qapp.processEvents()
    assert workspace.normalized_gas_mode_label.text() == "Есеп режимі:"
    assert "салыстыру" in workspace.normalized_gas_mode.itemText(0)
    assert "Жергілікті нормаланған газды" in (
        workspace.calculate_normalized_gas_button.text()
    )

    workspace.set_language(AppLanguage.EN)
    qapp.processEvents()
    assert workspace.normalized_gas_mode_label.text() == "Report mode:"
    assert "compare both" in workspace.normalized_gas_mode.itemText(0)
    assert workspace.calculate_normalized_gas_button.text() == (
        "Calculate local normalized gas"
    )
    workspace.close()
