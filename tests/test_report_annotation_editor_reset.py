from __future__ import annotations

import pytest

from geoworkbench.domain.report_annotations import (
    ReportAnnotationAnchor,
    ReportAnnotationKind,
)
from geoworkbench.project.controller import ProjectController
from geoworkbench.project.report_annotation_controller import ReportAnnotationController
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.interpretation_report_annotation_dialog import (
    InterpretationReportAnnotationDialog,
)
from test_report_annotations import _session


def test_editor_new_annotation_resets_previous_track_depth_and_anchor(qapp) -> None:
    session = _session()
    controller = ReportAnnotationController(session)
    existing = controller.add(
        kind=ReportAnnotationKind.TEXT,
        anchor=ReportAnnotationAnchor.INTERVAL,
        text="Earlier interval",
        track_key="curve:TG",
        top_depth=1001.0,
        bottom_depth=1002.0,
    )
    dialog = InterpretationReportAnnotationDialog(session, language=AppLanguage.RU)
    try:
        dialog.annotation.setCurrentIndex(1)
        assert dialog._selected_id() == existing.annotation_id
        assert dialog.track.currentText() == "curve:TG"
        assert dialog.top_depth_spin.value() == 1001.0
        assert dialog.bottom_depth_spin.value() == 1002.0
        assert dialog._current_anchor() is ReportAnnotationAnchor.INTERVAL
        assert dialog._current_kind() is ReportAnnotationKind.TEXT

        dialog.annotation.setCurrentIndex(0)
        assert dialog._selected_id() is None
        assert dialog._current_kind() is ReportAnnotationKind.CALLOUT
        assert dialog._current_anchor() is ReportAnnotationAnchor.DEPTH
        assert dialog.track.currentText() == ""
        assert dialog.text.text() == ""
        assert dialog.depth_spin.value() == 0.0
        assert dialog.top_depth_spin.value() == 0.0
        assert dialog.bottom_depth_spin.value() == 0.0
        assert dialog.depth_spin.isEnabled()
        assert not dialog.top_depth_spin.isEnabled()
        assert not dialog.bottom_depth_spin.isEnabled()
        assert dialog._values().track_key is None
    finally:
        dialog.reject()


def test_editor_trackless_record_does_not_inherit_previous_column(qapp) -> None:
    session = _session()
    controller = ReportAnnotationController(session)
    tracked = controller.add(text="Tracked", track_key="curve:TG", depth=1001.0)
    unbound = controller.add(text="All chart", track_key=None, depth=1002.0)
    dialog = InterpretationReportAnnotationDialog(session, language=AppLanguage.EN)
    try:
        dialog.annotation.setCurrentIndex(1)
        assert dialog._selected_id() == tracked.annotation_id
        assert dialog.track.currentText() == "curve:TG"
        dialog.annotation.setCurrentIndex(2)
        assert dialog._selected_id() == unbound.annotation_id
        assert dialog.track.currentText() == ""
        assert dialog._values().track_key is None
        dialog.text.setText("All chart updated")
        dialog._save()
        assert dialog.controller.get(unbound.annotation_id).track_key is None
        assert dialog.controller.get(tracked.annotation_id).track_key == "curve:TG"
    finally:
        dialog.reject()
    assert controller.get(unbound.annotation_id).text == "All chart"


@pytest.mark.parametrize("suffix", (".geolog.json", ".geologpkg"))
def test_annotation_created_in_editor_survives_project_reopen(qapp, tmp_path, suffix: str) -> None:
    session = _session()
    dataset = session.current_dataset
    assert dataset is not None
    dialog = InterpretationReportAnnotationDialog(session, language=AppLanguage.RU)
    dialog.track.setCurrentText("curve:TG")
    dialog.depth_spin.setValue(1001.0)
    dialog.text.setText("Confirmed depth note")
    dialog._add()
    record = dialog.controller.available()[0]
    assert record.depth == 1001.0 and record.track_key == "curve:TG"
    dialog.accept()

    target = tmp_path / f"annotations{suffix}"
    ProjectController(session=session).save_project(target)
    reopened = ProjectController().open_project(target)
    assert reopened.report_compositions[dataset.dataset_id].annotations == (record,)
    second = InterpretationReportAnnotationDialog(reopened, language=AppLanguage.RU)
    try:
        second.annotation.setCurrentIndex(1)
        assert second.text.text() == "Confirmed depth note"
        assert second.depth_spin.value() == 1001.0
        assert second.track.currentText() == "curve:TG"
    finally:
        second.reject()
