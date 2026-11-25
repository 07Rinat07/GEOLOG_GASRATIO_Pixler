import pytest

from geoworkbench.domain.models import CuttingsSample
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.rock_description_dialog import RockDescriptionDialog
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton, QTextEdit


def test_rock_description_dialog_allows_exact_interval_and_free_text(qapp) -> None:
    dialog = RockDescriptionDialog(70.0, 80.0, language=AppLanguage.RU)

    dialog.top_input.setValue(70.125)
    dialog.bottom_input.setValue(79.875)
    dialog.editor.set_html("Песчаник, мелкозернистый")

    assert dialog.top_depth == 70.125
    assert dialog.bottom_depth == 79.875
    assert "Песчаник" in (dialog.description_html or "")
    dialog.close()


def test_rock_description_dialog_offers_localized_ready_templates(qapp) -> None:
    dialog = RockDescriptionDialog(70.0, 80.0, language=AppLanguage.RU)

    assert dialog.template_input.count() > 1
    dialog.template_language_input.setCurrentIndex(
        dialog.template_language_input.findData(AppLanguage.KK.value)
    )
    dialog.template_input.setCurrentIndex(1)

    assert dialog.editor.editor.toPlainText().strip()
    assert dialog.template_formula.text()
    assert dialog.template_warning.text()
    dialog.close()


def test_rock_description_dialog_appends_multiple_ready_templates(qapp) -> None:
    dialog = RockDescriptionDialog(70.0, 80.0, language=AppLanguage.RU)

    dialog.template_input.setCurrentIndex(1)
    first = dialog.editor.editor.toPlainText().strip()
    dialog.template_input.setCurrentIndex(2)
    combined = dialog.editor.editor.toPlainText().strip()

    assert first
    assert first in combined
    assert len(combined) > len(first)
    assert dialog.template_input.currentIndex() == 0
    dialog.close()


def test_rock_description_dialog_preserves_existing_text_on_open(qapp) -> None:
    sample = CuttingsSample("sample", 70.0, 80.0, description="Авторский текст")

    dialog = RockDescriptionDialog(
        70.0,
        80.0,
        language=AppLanguage.RU,
        sample=sample,
    )

    assert dialog.editor.editor.toPlainText() == "Авторский текст"
    assert dialog.template_input.currentIndex() == 0
    dialog.close()


@pytest.mark.parametrize(
    ("language", "stored_language", "can_delete"),
    (
        pytest.param(AppLanguage.KK, "kk", True, id="current-language"),
        pytest.param(AppLanguage.EN, "ru", False, id="other-language-fallback"),
        pytest.param(AppLanguage.EN, "und", False, id="undetermined-fallback"),
        pytest.param(AppLanguage.RU, None, True, id="legacy-russian"),
        pytest.param(AppLanguage.KK, None, False, id="legacy-fallback"),
    ),
)
def test_rock_description_delete_requires_saved_version_in_editor_language(
    qapp, language: AppLanguage, stored_language: str | None, can_delete: bool
) -> None:
    text = "Saved rock description"
    sample = CuttingsSample(
        "sample",
        70.0,
        80.0,
        description=text if stored_language is None else None,
        description_i18n={stored_language: text} if stored_language is not None else {},
    )
    dialog = RockDescriptionDialog(70.0, 80.0, language=language, sample=sample)

    assert dialog.editor.editor.toPlainText() == text
    delete_button = dialog.findChild(QPushButton, "rock-description-delete")
    assert (delete_button is not None) is can_delete
    if delete_button is not None:
        delete_button.click()
    assert dialog.delete_requested is can_delete
    dialog.close()


@pytest.mark.parametrize("stored_language", ["en", "und", "ru"])
def test_rock_description_displays_the_saved_russian_delete_target(
    qapp, stored_language: str
) -> None:
    sample = CuttingsSample(
        "sample",
        70.0,
        80.0,
        description="Legacy text",
        description_i18n={stored_language: "Localized text"},
    )
    dialog = RockDescriptionDialog(70.0, 80.0, language=AppLanguage.RU, sample=sample)

    assert dialog.editor.editor.toPlainText() == (
        "Localized text" if stored_language == "ru" else "Legacy text"
    )
    assert dialog.findChild(QPushButton, "rock-description-delete") is not None
    dialog.close()


def test_rock_description_editor_applies_document_alignment(qapp) -> None:
    dialog = RockDescriptionDialog(70.0, 80.0, language=AppLanguage.RU)
    dialog.editor.editor.setPlainText("Первая строка\nВторая строка")

    dialog.editor.alignment_input.setCurrentIndex(1)

    block = dialog.editor.editor.document().firstBlock()
    assert block.blockFormat().alignment() & Qt.AlignmentFlag.AlignHCenter
    assert "Первая строка" in (dialog.description_html or "")
    dialog.close()


def test_rock_description_editor_defaults_to_wrap_and_preserves_disabled_choice(qapp) -> None:
    create_dialog = RockDescriptionDialog(70.0, 80.0, language=AppLanguage.RU)
    assert create_dialog.description_word_wrap is True
    assert create_dialog.editor.editor.lineWrapMode() is QTextEdit.LineWrapMode.WidgetWidth
    create_dialog.close()

    sample = CuttingsSample(
        "sample-nowrap",
        70.0,
        80.0,
        description="Описание без автоматического переноса",
        description_word_wrap=False,
    )
    edit_dialog = RockDescriptionDialog(
        70.0,
        80.0,
        language=AppLanguage.RU,
        sample=sample,
    )

    assert edit_dialog.description_word_wrap is False
    assert edit_dialog.editor.editor.lineWrapMode() is QTextEdit.LineWrapMode.NoWrap
    edit_dialog.close()
