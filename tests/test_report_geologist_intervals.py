from geoworkbench.project.interpretation_calculation_controller import InterpretationCalculationController
from geoworkbench.project.interpretation_controller import InterpretationController
from geoworkbench.ui.interpretation_report_workspace import InterpretationReportWorkspace
from test_hydrocarbon_interpretation import _session


def test_editor_request_refreshes_report_from_project_intervals(qapp):
    session = _session()
    session.current_well.interpretations.clear()
    workspace = InterpretationReportWorkspace(InterpretationCalculationController(session))
    workspace.refresh()
    assert not workspace.report.manual_intervals

    def enter_interval():
        editor = InterpretationController(session)
        editor.add_interpretation("Геолог")
        editor.add_interval(top_depth=1040, bottom_depth=1042, interval_type="show",
                            label="Проверенный пласт", comment="Комментарий")

    workspace.edit_manual_intervals_requested.connect(enter_interval)
    workspace.edit_manual_intervals_button.click()
    assert workspace.report.manual_intervals[0].label == "Проверенный пласт"
    assert "Проверенный пласт" in workspace.preview.toHtml()
    assert session.current_well.interpretations
    workspace.close()
