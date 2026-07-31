from __future__ import annotations

from PySide6.QtCore import Qt

from geoworkbench.project.interpretation_calculation_controller import (
    InterpretationCalculationController,
)
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.interpretation_report_workspace import InterpretationReportWorkspace


def _grid_position(workspace, widget) -> tuple[int, int, int, int]:
    layout = workspace._configuration_grid
    for index in range(layout.count()):
        item = layout.itemAt(index)
        if item.widget() is widget:
            return layout.getItemPosition(index)
    raise AssertionError(f"Widget {widget.objectName()} is absent from configuration grid")


def test_interpretation_workspace_separates_controls_preview_and_log(qapp) -> None:
    workspace = InterpretationReportWorkspace(
        InterpretationCalculationController(ProjectSession()),
        language=AppLanguage.RU,
    )
    workspace.resize(1_600, 900)
    workspace.show()
    qapp.processEvents()

    assert workspace.page_header.isVisible()
    assert workspace.main_splitter.orientation() == Qt.Orientation.Vertical
    assert workspace.main_splitter.widget(0) is workspace.configuration_scroll
    assert workspace.main_splitter.widget(1) is workspace.report_panel
    assert workspace.configuration_scroll.widgetResizable()
    assert workspace.report_panel.isAncestorOf(workspace.preview)
    assert workspace.log_panel.isAncestorOf(workspace.status)
    assert workspace.log_scroll.maximumHeight() <= 150
    assert not workspace.methodology_panel.isVisible()
    assert not workspace.log_panel.isVisible()
    assert workspace.normalized_gas_mode.minimumWidth() == 0
    assert workspace._configuration_columns == 2
    assert _grid_position(workspace, workspace.normalized_gas_panel) == (0, 0, 2, 1)
    assert _grid_position(workspace, workspace.settings_panel) == (0, 1, 1, 1)
    assert _grid_position(workspace, workspace.dexp_quality_panel) == (1, 1, 1, 1)

    workspace.methodology_toggle.setChecked(True)
    qapp.processEvents()
    assert workspace.methodology_panel.isVisible()
    assert workspace.methodology_toggle.arrowType() == Qt.ArrowType.DownArrow
    workspace.close()


def test_interpretation_workspace_switches_to_one_column_on_narrow_window(qapp) -> None:
    workspace = InterpretationReportWorkspace(
        InterpretationCalculationController(ProjectSession()),
        language=AppLanguage.EN,
    )
    workspace.resize(1_050, 820)
    workspace.show()
    qapp.processEvents()

    assert workspace._configuration_columns == 1
    assert _grid_position(workspace, workspace.normalized_gas_panel) == (0, 0, 1, 1)
    assert _grid_position(workspace, workspace.dexp_quality_panel) == (1, 0, 1, 1)
    assert _grid_position(workspace, workspace.settings_panel) == (2, 0, 1, 1)
    assert workspace.configuration_content.maximumWidth() == 940
    assert workspace.page_title.text() == "Gas logging interpretation"
    assert workspace.report_title.text() == "Report preview"
    workspace.close()
