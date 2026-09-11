from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialogButtonBox

from geoworkbench.domain.analysis_update import AnalysisField
from geoworkbench.domain.models import CuttingsSample, Project, Well
from geoworkbench.project.session import ProjectSession
from geoworkbench.project.well_analysis_update_controller import WellAnalysisUpdateController
from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.well_analysis_update import AnalysisSourceSample, AnalysisSourceValue
from geoworkbench.ui.late_analysis_review_dialog import LateAnalysisReviewDialog


_SOURCE_SHA = "a" * 64


def _controller() -> WellAnalysisUpdateController:
    well = Well(
        "well-1",
        "Well 1",
        cuttings=[
            CuttingsSample("sample-1", 100.0, 101.0),
            CuttingsSample("sample-2", 101.0, 102.0, calcite_percent=10.0),
        ],
    )
    session = ProjectSession(
        project=Project("project-1", "Project", wells={well.well_id: well}),
        current_well_id=well.well_id,
    )
    return WellAnalysisUpdateController(session)


def _source() -> tuple[AnalysisSourceSample, ...]:
    return (
        AnalysisSourceSample(
            100.0,
            101.0,
            (
                AnalysisSourceValue(AnalysisField.CALCITE_PERCENT, 35.0),
                AnalysisSourceValue(AnalysisField.ANALYSIS_INTERPRETATION, "oil show"),
            ),
            "sample-1",
        ),
        AnalysisSourceSample(
            101.0,
            102.0,
            (AnalysisSourceValue(AnalysisField.CALCITE_PERCENT, 25.0),),
            "sample-2",
        ),
    )


def test_review_dialog_shows_fill_and_protected_conflict(qapp) -> None:
    dialog = LateAnalysisReviewDialog(
        _controller(),
        _source(),
        source_name="late.csv",
        source_sha256=_SOURCE_SHA,
    )

    dialog._analyze()

    assert dialog.plan is not None
    assert dialog.plan.fill_count == 2
    assert dialog.plan.conflict_count == 1
    assert dialog.table.rowCount() == 3
    assert "Заполнений: 2" in dialog.counts_label.text()
    assert dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled()

    conflict_rows = [
        row
        for row in range(dialog.table.rowCount())
        if "Конфликт" in dialog.table.item(row, 5).text()
    ]
    assert len(conflict_rows) == 1
    conflict_choice = dialog.table.item(conflict_rows[0], 0)
    assert not (conflict_choice.flags() & Qt.ItemFlag.ItemIsUserCheckable)
    dialog.close()


def test_review_dialog_applies_only_checked_fill(qapp) -> None:
    controller = _controller()
    dialog = LateAnalysisReviewDialog(
        controller,
        _source(),
        source_name="late.csv",
        source_sha256=_SOURCE_SHA,
    )
    dialog._analyze()
    assert dialog.plan is not None
    first = dialog.table.item(0, 0)
    first.setCheckState(Qt.CheckState.Checked)

    dialog._accept()

    well = controller.session.current_well
    assert well is not None
    assert dialog.result() == dialog.DialogCode.Accepted
    assert well.cuttings[0].calcite_percent == 35.0
    assert well.cuttings[0].analysis_interpretation is None
    assert well.cuttings[1].calcite_percent == 10.0
    assert len(well.analysis_update_history) == 1
    assert len(well.analysis_update_history[0].changes) == 1


def test_review_dialog_field_toggle_invalidates_preview(qapp) -> None:
    controller = _controller()
    dialog = LateAnalysisReviewDialog(
        controller,
        _source(),
        source_name="late.csv",
        source_sha256=_SOURCE_SHA,
    )
    dialog._analyze()
    assert dialog.plan is not None

    dialog.field_checks[AnalysisField.CALCITE_PERCENT].setChecked(False)

    assert dialog.plan is None
    assert dialog.table.rowCount() == 0
    assert not dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled()


def test_review_dialog_cancel_consumes_preview(qapp) -> None:
    controller = _controller()
    dialog = LateAnalysisReviewDialog(
        controller,
        _source(),
        source_name="late.csv",
        source_sha256=_SOURCE_SHA,
    )
    dialog._analyze()
    plan = dialog.plan
    assert plan is not None

    dialog.reject()

    assert dialog.result() == dialog.DialogCode.Rejected
    assert controller.session.current_well is not None
    assert not controller.session.current_well.analysis_update_history


def test_review_dialog_uses_selected_language(qapp) -> None:
    dialog = LateAnalysisReviewDialog(
        _controller(),
        _source(),
        source_name="late.csv",
        source_sha256=_SOURCE_SHA,
        language=AppLanguage.EN,
    )

    assert dialog.windowTitle() == "Late analyses"
    assert dialog.analyze_button.text() == "Preview changes"
    assert dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).text() == "Apply selected"
    dialog.close()
