from geoworkbench.domain.models import CuttingsSample
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.rock_description_dialog import RockDescriptionDialog


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
