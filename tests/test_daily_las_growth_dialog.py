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
