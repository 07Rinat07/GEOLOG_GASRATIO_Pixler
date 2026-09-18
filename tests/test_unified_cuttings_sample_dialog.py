from __future__ import annotations

from PySide6.QtWidgets import QDialogButtonBox

from geoworkbench.domain.models import (
    CuttingsComponent,
    CuttingsSample,
    DescriptionTemplateBlock,
    Project,
    Well,
)
from geoworkbench.project.cuttings_controller import CuttingsController
from geoworkbench.project.session import ProjectSession
from geoworkbench.project.lithotype_catalog_models import CatalogLithotype
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.unified_cuttings_sample_dialog import UnifiedCuttingsSampleDialog


def test_existing_composition_is_registered_before_combo_signal_fires(qapp) -> None:
    del qapp
    lithotype = CatalogLithotype(
        lithotype_id="sandstone",
        code="SS",
        name_ru="Песчаник",
        name_en="Sandstone",
        category="sedimentary",
        color="#d6b36a",
        pattern_key="sandstone",
        system=True,
    )
    sample = CuttingsSample(
        sample_id="sample-existing",
        top_depth=1980.0,
        bottom_depth=1981.0,
        components=[CuttingsComponent(lithotype_id="sandstone", percentage=100.0)],
    )

    dialog = UnifiedCuttingsSampleDialog(
        sample.top_depth,
        sample.bottom_depth,
        (lithotype,),
        language=AppLanguage.RU,
        sample=sample,
    )

    assert dialog.rock_inputs[0].currentData() == "sandstone"
    assert dialog.percent_inputs[0].value() == 100.0
    assert dialog.components() == {"sandstone": 100.0}


def test_shared_sample_description_appends_multiple_ready_templates(qapp) -> None:
    lithotype = CatalogLithotype(
        lithotype_id="sandstone",
        code="SS",
        name_ru="Песчаник",
        name_en="Sandstone",
        category="sedimentary",
        color="#d6b36a",
        pattern_key="sandstone",
        system=True,
    )
    dialog = UnifiedCuttingsSampleDialog(
        1980.0,
        1981.0,
        (lithotype,),
        language=AppLanguage.RU,
    )

    sandstone_template_index = next(
        index
        for index in range(1, dialog.description_template_input.count())
        if dialog.description_template_input.itemData(index, 257) == "sandstone"
    )
    dialog.description_template_input.setCurrentIndex(sandstone_template_index)
    first = dialog.rich_description.editor.toPlainText().strip()
    dialog.description_template_input.setCurrentIndex(2)
    combined = dialog.rich_description.editor.toPlainText().strip()

    assert first
    assert first in combined
    assert len(combined) > len(first)
    assert dialog.description_template_input.currentIndex() == 0
    dialog.close()


def test_multilingual_description_tabs_preserve_drafts_and_insert_one_template_in_all_languages(
    qapp,
) -> None:
    lithotype = CatalogLithotype(
        lithotype_id="sandstone",
        code="SS",
        name_ru="Песчаник",
        name_en="Sandstone",
        category="sedimentary",
        color="#d6b36a",
        pattern_key="sandstone",
        system=True,
        name_kk="Құмтас",
    )
    dialog = UnifiedCuttingsSampleDialog(
        1980.0,
        1981.0,
        (lithotype,),
        language=AppLanguage.RU,
    )

    assert dialog.description_language_tabs.count() == 3
    sandstone_template_index = next(
        index
        for index in range(1, dialog.description_template_input.count())
        if dialog.description_template_input.itemData(index, 257) == "sandstone"
    )
    dialog.description_template_input.setCurrentIndex(sandstone_template_index)
    texts = {
        language: editor.editor.toPlainText()
        for language, editor in dialog.description_editors.items()
    }
    assert "Песчан" in texts["ru"]
    assert "Құмтас" in texts["kk"]
    assert "Sandstone" in texts["en"]

    dialog.description_editors["kk"].editor.append("Қолмен толықтыру")
    dialog.description_language_tabs.setCurrentIndex(2)
    dialog.description_language_tabs.setCurrentIndex(1)
    values = dialog.values()

    assert "Қолмен толықтыру" in values["description_i18n"]["kk"]
    assert set(values["description_i18n"]) == {"ru", "kk", "en"}
    blocks = values["description_template_blocks"]
    assert len(blocks) == 1
    assert blocks[0].template_id == "sandstone"
    assert blocks[0].template_version == 1
    assert set(blocks[0].text_i18n) == {"ru", "kk", "en"}
    dialog.close()


def test_controller_saves_all_description_languages_in_one_sample_update() -> None:
    well = Well("well", "Well")
    session = ProjectSession(Project("project", "Project", wells={well.well_id: well}))
    session.current_well_id = well.well_id
    controller = CuttingsController(session)

    sample = controller.create_full_sample(
        1980.0,
        1981.0,
        {"sandstone": 100.0},
        description_i18n={
            "ru": "Аргиллит",
            "kk": "Аргиллит",
            "en": "Claystone",
        },
    )

    assert sample.description_i18n == {
        "ru": "Аргиллит",
        "kk": "Аргиллит",
        "en": "Claystone",
    }
    assert sample.description == "Аргиллит"
    assert session.dirty is True


def test_unedited_legacy_fallback_is_not_promoted_to_russian_translation(qapp) -> None:
    sample = CuttingsSample(
        "sample-legacy",
        1980.0,
        1981.0,
        [CuttingsComponent("sandstone", 100.0)],
        description="Legacy description",
        description_i18n={"und": "Unclassified authored text"},
    )
    dialog = UnifiedCuttingsSampleDialog(
        sample.top_depth,
        sample.bottom_depth,
        (),
        language=AppLanguage.RU,
        sample=sample,
    )

    values = dialog.values()

    assert values["description_i18n"] == {"und": "Unclassified authored text"}
    assert "ru" not in values["description_i18n"]
    dialog.close()


def test_selected_template_block_is_removed_from_all_languages(qapp) -> None:
    dialog = UnifiedCuttingsSampleDialog(
        1980.0,
        1981.0,
        (),
        language=AppLanguage.RU,
    )
    first_index = 1
    second_index = 2
    dialog.description_template_input.setCurrentIndex(first_index)
    first_block = dialog.values()["description_template_blocks"][0]
    dialog.description_template_input.setCurrentIndex(second_index)
    second_block = dialog.values()["description_template_blocks"][1]
    before = {
        language: editor.editor.toPlainText()
        for language, editor in dialog.description_editors.items()
    }

    dialog.description_template_blocks_input.setCurrentIndex(0)
    dialog.description_template_remove_button.click()
    values = dialog.values()

    assert [block.block_id for block in values["description_template_blocks"]] == [
        second_block.block_id
    ]
    for language, editor in dialog.description_editors.items():
        assert first_block.text_i18n[language] not in editor.editor.toPlainText()
        assert len(editor.editor.toPlainText()) < len(before[language])
    dialog.close()


def test_unmarked_saved_block_is_not_removed_ambiguously(qapp) -> None:
    block = DescriptionTemplateBlock(
        "legacy-block",
        "sandstone",
        1,
        {"ru": "Песчаник", "kk": "Құмтас", "en": "Sandstone"},
    )
    sample = CuttingsSample(
        "sample",
        1980.0,
        1981.0,
        description_i18n=block.text_i18n,
        description_template_blocks=[block],
    )
    dialog = UnifiedCuttingsSampleDialog(
        sample.top_depth,
        sample.bottom_depth,
        (),
        language=AppLanguage.RU,
        sample=sample,
    )

    dialog.description_template_remove_button.click()
    values = dialog.values()

    assert values["description_template_blocks"] == [block]
    assert dialog.description_template_status.text()
    assert dialog.description_editors["ru"].editor.toPlainText() == "Песчаник"
    dialog.close()



def test_unified_cuttings_dialog_fits_work_area_with_sticky_actions(qapp) -> None:
    dialog = UnifiedCuttingsSampleDialog(
        1980.0,
        1981.0,
        (),
        language=AppLanguage.EN,
    )
    try:
        screen = dialog.screen()
        assert screen is not None
        available = screen.availableGeometry()
        assert dialog.minimumWidth() <= dialog.width() <= available.width()
        assert dialog.minimumHeight() <= dialog.height() <= available.height()
        assert dialog.content_scroll.objectName() == "unified-cuttings-scroll"

        buttons = dialog.findChild(
            QDialogButtonBox,
            "cuttings-dialog-buttons",
        )
        assert buttons is not None
        assert not dialog.content_scroll.isAncestorOf(buttons)
    finally:
        dialog.close()
