from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QDialogButtonBox

from geoworkbench.data.las_adapter import import_las_with_report
from geoworkbench.domain.models import Project
from geoworkbench.project.daily_las_growth_controller import DailyLasGrowthController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.daily_las_growth_dialog import DailyLasGrowthDialog


FIXTURES = Path(__file__).parent / "fixtures" / "las_sync"


def _controller() -> DailyLasGrowthController:
    imported = import_las_with_report(FIXTURES / "01_initial.las")
    session = ProjectSession(project=Project("daily-dialog", "Daily dialog"))
    session.add_dataset(
        imported.dataset,
        source_document=imported.source_document,
        import_report=imported.report,
        create_new_well=True,
    )
    return DailyLasGrowthController(session)


@pytest.mark.parametrize(
    ("language", "assistant_text", "analyze_text", "append_text", "autosave_text"),
    (
        (AppLanguage.RU, "Помощник", "Проверить прирост", "Нарастить", "автоматически"),
        (AppLanguage.KK, "Көмекші", "Өсімді тексеру", "Өсіру", "автоматты"),
        (AppLanguage.EN, "Assistant", "Analyze growth", "Append", "automatically"),
    ),
)
def test_daily_las_dialog_explains_safe_workflow_in_each_language(
    qapp,
    language: AppLanguage,
    assistant_text: str,
    analyze_text: str,
    append_text: str,
    autosave_text: str,
) -> None:
    dialog = DailyLasGrowthDialog(_controller(), language=language)
    append_button = dialog.buttons.button(QDialogButtonBox.StandardButton.Ok)

    assert ".geologpkg" in dialog.info_label.text()
    assert assistant_text in dialog.workflow_help_button.text()
    assert dialog.workflow_help_button.toolTip()
    assert dialog.target_combo.toolTip()
    assert dialog.file_input.toolTip()
    assert dialog.folder_input.toolTip()
    assert dialog.folder_files.toolTip()
    assert dialog.analyze_button.text() == analyze_text
    assert dialog.analyze_button.toolTip()
    assert append_button.text() == append_text
    assert autosave_text in append_button.toolTip()
    assert dialog.preview.toPlainText().startswith("1.")
    assert append_button.isEnabled() is False
    dialog.close()


def test_controller_rejects_unreviewed_old_value_and_allows_fresh_preview() -> None:
    from geoworkbench.services.daily_las_growth import DailyLasGrowthError

    controller = _controller()
    session = controller.session
    target = session.current_dataset
    assert target is not None
    source = FIXTURES / "02_daily_append.las"
    plan = controller.analyze(source, target.dataset_id)
    curve = next(iter(target.curves.values()))
    curve.values[0] += 1
    before = curve.values.copy()
    source_documents = dict(session.source_documents)
    source_revisions = tuple(target.source_revisions)
    session.dirty = True

    with pytest.raises(DailyLasGrowthError, match="после предварительного анализа"):
        controller.apply(plan)
    assert (curve.values == before).all()
    assert session.source_documents == source_documents
    assert tuple(target.source_revisions) == source_revisions
    assert session.dirty
    assert not target.append_history
    with pytest.raises(RuntimeError, match="повторно проанализируйте"):
        controller.apply(plan)

    fresh_plan = controller.analyze(source, target.dataset_id)
    assert controller.apply(fresh_plan).record is not None
    assert curve.values[0] == before[0]


def test_daily_las_dialog_assistant_opens_project_help(qapp, monkeypatch) -> None:
    calls: list[tuple[object, str]] = []
    monkeypatch.setattr(
        "geoworkbench.ui.daily_las_growth_dialog.open_help_for_widget",
        lambda widget, section: calls.append((widget, section)),
    )
    dialog = DailyLasGrowthDialog(_controller(), language=AppLanguage.RU)

    dialog.workflow_help_button.click()

    assert calls == [(dialog, "project")]
    dialog.close()


@pytest.mark.parametrize("action", ["missing_file", "failed_analysis", "file_edit", "cancel"])
def test_invalid_or_cancelled_preview_cannot_reuse_previous_confirmation(
    qapp, monkeypatch, tmp_path: Path, action: str,
) -> None:
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "warning", lambda *args: QMessageBox.StandardButton.Ok)
    controller = _controller()
    dialog = DailyLasGrowthDialog(controller)
    source = tmp_path / "daily.las"
    source.write_bytes((FIXTURES / "02_daily_append.las").read_bytes())
    dialog.file_input.setText(str(source))
    dialog._analyze()
    previous_plan = dialog.plan
    assert previous_plan is not None
    assert dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled()
    target = controller.session.current_dataset
    assert target is not None
    before = target.depth.copy()
    if action == "missing_file":
        source.unlink()
        dialog._analyze()
    elif action == "failed_analysis":
        # Explicit strict mode must still reject conflicting historical cells.
        # The default cumulative mode intentionally retains old values.
        dialog.preserve_overlap.setChecked(False)
        source.write_bytes((FIXTURES / "03_conflict.las").read_bytes())
        dialog._analyze()
    elif action == "file_edit":
        dialog.file_input.setText(str(tmp_path / "other.las"))
    else:
        dialog.reject()

    assert dialog.plan is None
    assert not dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled()
    with pytest.raises(RuntimeError, match="повторно проанализируйте"):
        controller.apply(previous_plan)
    assert (target.depth == before).all()
    assert not target.append_history
    dialog.close()



def test_daily_las_dialog_fits_work_area_with_sticky_actions(qapp) -> None:
    dialog = DailyLasGrowthDialog(_controller(), language=AppLanguage.EN)
    try:
        screen = dialog.screen()
        assert screen is not None
        available = screen.availableGeometry()
        assert dialog.minimumWidth() <= dialog.width() <= available.width()
        assert dialog.minimumHeight() <= dialog.height() <= available.height()
        assert dialog.body_scroll.objectName() == "daily-las-growth-scroll"
        assert not dialog.body_scroll.isAncestorOf(dialog.buttons)

        dialog.numerical_mode.setChecked(True)
        qapp.processEvents()
        assert dialog.width() <= available.width()
        assert dialog.height() <= available.height()
        assert not dialog.change_table.isHidden()
    finally:
        dialog.close()


def test_cumulative_preview_reports_conflicts_and_strict_toggle_revokes_plan(
    qapp, monkeypatch,
) -> None:
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(
        QMessageBox, "warning",
        lambda *args: QMessageBox.StandardButton.Ok,
    )
    controller = _controller()
    target = controller.session.current_dataset
    assert target is not None
    old = target.depth.copy()
    dialog = DailyLasGrowthDialog(controller, language=AppLanguage.RU)
    try:
        assert dialog.preserve_overlap.isChecked()
        dialog.file_input.setText(str(FIXTURES / "03_conflict.las"))
        dialog._analyze()
        reviewed = dialog.plan
        assert reviewed is not None
        assert reviewed.historical_policy == "keep_existing"
        assert reviewed.historical_conflict_rows > 0
        assert "Ни одно прежнее значение" in dialog.preview.toPlainText()
        dialog.preserve_overlap.setChecked(False)
        assert dialog.plan is None
        assert not dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled()
        with pytest.raises(RuntimeError, match="повторно проанализируйте"):
            controller.apply(reviewed)
        dialog._analyze()
        assert dialog.plan is None
        assert (target.depth == old).all()
    finally:
        dialog.close()


@pytest.mark.parametrize("accept_safe_growth", [False, True])
def test_failed_numeric_review_offers_safe_partial_append_without_applying(
    qapp, monkeypatch, tmp_path: Path, accept_safe_growth: bool,
) -> None:
    import numpy as np
    from PySide6.QtWidgets import QMessageBox
    from geoworkbench.services.daily_las_growth import DailyLasGrowthPlan

    controller = _controller()
    target = controller.session.current_dataset
    assert target is not None
    before_depth = target.depth.copy()
    before_values = {key: curve.values.copy() for key, curve in target.curves.items()}
    # A cumulative daily export omits ROP and corrects an old C1 measurement.
    lines = (FIXTURES / "02_daily_append.las").read_text().splitlines()
    output = []
    in_data = False
    for line in lines:
        if line.startswith(" ROP."):
            continue
        if line.startswith("~Ascii"):
            in_data = True
        elif in_data:
            depth, _rop, methane = line.split()
            line = f"{depth} {9.0 if depth == '1002.0' else methane}"
        output.append(line)
    source = tmp_path / "partial.las"
    source.write_text("\n".join(output) + "\n")
    questions = []

    def choose(*args):
        questions.append(args[2])
        return QMessageBox.StandardButton.Yes if accept_safe_growth else QMessageBox.StandardButton.No

    monkeypatch.setattr(QMessageBox, "question", choose)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: pytest.fail(str(args)))
    dialog = DailyLasGrowthDialog(controller, language=AppLanguage.RU)
    dialog.numerical_mode.setChecked(True)
    dialog.file_input.setText(str(source))
    dialog._analyze()
    assert len(questions) == 1
    assert "Старые значения не изменятся" in questions[0]
    np.testing.assert_array_equal(target.depth, before_depth)
    for key, curve in target.curves.items():
        np.testing.assert_array_equal(curve.values, before_values[key])
    if not accept_safe_growth:
        assert dialog.plan is None
        assert not dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled()
        return
    assert not dialog.numerical_mode.isChecked()
    assert isinstance(dialog.plan, DailyLasGrowthPlan)
    assert dialog.plan.historical_conflict_cells > 0
    assert dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled()
    controller.apply(dialog.plan)
    assert target.depth[-1] == 1004.0
    for key, curve in target.curves.items():
        np.testing.assert_array_equal(curve.values[:len(before_depth)], before_values[key])
        if curve.metadata.original_mnemonic == "ROP":
            assert np.isnan(curve.values[len(before_depth):]).all()
