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
