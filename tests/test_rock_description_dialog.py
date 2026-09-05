from geoworkbench.domain.models import CuttingsSample
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.rock_description_dialog import RockDescriptionDialog
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTextEdit


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
