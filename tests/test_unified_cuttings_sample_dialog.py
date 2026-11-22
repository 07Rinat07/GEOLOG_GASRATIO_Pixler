from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QDialogButtonBox

from geoworkbench.domain.models import (
    CuttingsComponent,
    CuttingsSample,
    DescriptionTemplateBlock,
    Project,
    Well,
)
from geoworkbench.domain.translation_status import TranslationState
from geoworkbench.project.cuttings_controller import CuttingsController
from geoworkbench.project.lithotype_catalog_controller import LithotypeCatalogController
from geoworkbench.project.lithotype_catalog_models import CatalogLithotype
from geoworkbench.project.session import ProjectSession
from geoworkbench.project.translation_status_controller import TranslationStatusController
from geoworkbench.services.lba_standard import LBA_STANDARD_GROUPS
from geoworkbench.services.localization import AppLanguage
from geoworkbench.storage.package_project_repository import PackageProjectRepository
from geoworkbench.storage.project_codec import ProjectDocument
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


def _edit_existing_sample(
    sample: CuttingsSample, language: AppLanguage,
) -> tuple[CuttingsController, UnifiedCuttingsSampleDialog]:
    well = Well("well", "Well", cuttings=[sample])
    session = ProjectSession(
        Project("project", "Project", wells={well.well_id: well}),
        current_well_id=well.well_id,
    )
    dialog = UnifiedCuttingsSampleDialog(
        sample.top_depth,
        sample.bottom_depth,
        LithotypeCatalogController(session).available(),
        language=language,
        sample=sample,
    )
    return CuttingsController(session), dialog


@pytest.mark.parametrize("language", tuple(AppLanguage))
def test_depth_only_edit_preserves_existing_legacy_text_after_package_reopen(
    qapp,
    tmp_path: Path,
    language: AppLanguage,
) -> None:
    sample = CuttingsSample(
        "sample-legacy",
        1980.0,
        1981.0,
        [CuttingsComponent("sandstone", 100.0)],
        description="<b>Legacy description</b>",
        description_i18n={"und": "Unclassified description"},
        lba_description="Legacy LBA",
        analysis_interpretation="Legacy conclusion",
        analysis_interpretation_i18n={"kk": "Қорытынды", "en": "Conclusion"},
    )
    controller, dialog = _edit_existing_sample(sample, language)
    try:
        dialog.top_input.setValue(1982.0)
        dialog.bottom_input.setValue(1983.0)
        controller.update_full_sample(
            sample.sample_id,
            top_depth=dialog.top_depth,
            bottom_depth=dialog.bottom_depth,
            components=dialog.components(),
            content_language=language.value,
            **dialog.values(),
        )
    finally:
        dialog.close()

    repository = PackageProjectRepository()
    path = tmp_path / "cuttings.geologpkg"
    repository.save(ProjectDocument(project=controller.session.project), path)
    restored = repository.load(path).project.wells["well"].cuttings[0]

    assert restored.sample_id == sample.sample_id
    assert (restored.top_depth, restored.bottom_depth) == (1982.0, 1983.0)
    assert restored.description == "<b>Legacy description</b>"
    assert restored.description_i18n == {"und": "Unclassified description"}
    assert restored.lba_description == "Legacy LBA"
    assert restored.lba_description_i18n == {}
    assert restored.analysis_interpretation == "Legacy conclusion"
    assert restored.analysis_interpretation_i18n == {"kk": "Қорытынды", "en": "Conclusion"}


@pytest.mark.parametrize("localized_ru", [False, True], ids=["legacy-ru", "localized-ru"])
def test_explicit_clear_removes_russian_text_only(qapp, localized_ru: bool) -> None:
    sample = CuttingsSample(
        "sample",
        1980.0,
        1981.0,
        [CuttingsComponent("sandstone", 100.0)],
        description="Russian description",
        description_i18n={"kk": "Сипаттама"},
        lba_description="Russian LBA",
        lba_description_i18n={"kk": "Люминесценция"},
        analysis_interpretation="Russian conclusion",
        analysis_interpretation_i18n={"kk": "Қорытынды"},
    )
    if localized_ru:
        sample.description_i18n["ru"] = "Russian description"
        sample.lba_description_i18n["ru"] = "Russian LBA"
        sample.analysis_interpretation_i18n["ru"] = "Russian conclusion"

    language = AppLanguage.EN
    controller, dialog = _edit_existing_sample(sample, language)
    try:
        dialog.description_editors["ru"].editor.clear()
        dialog.lba_description_inputs["ru"].clear()
        dialog.interpretation_inputs["ru"].clear()
        controller.update_full_sample(
            sample.sample_id,
            top_depth=dialog.top_depth,
            bottom_depth=dialog.bottom_depth,
            components=dialog.components(),
            content_language=language.value,
            **dialog.values(),
        )
    finally:
        dialog.close()

    assert sample.description is None
    assert sample.description_i18n == {"kk": "Сипаттама"}
    assert sample.lba_description is None
    assert sample.lba_description_i18n == {"kk": "Люминесценция"}
    assert sample.analysis_interpretation is None
    assert sample.analysis_interpretation_i18n == {"kk": "Қорытынды"}


@pytest.mark.parametrize("edit_lba", [False, True], ids=["description-only", "explicit-lba-edit"])
def test_full_sample_edit_persists_detailed_lba_observations(
    qapp, tmp_path: Path, edit_lba: bool
) -> None:
    well = Well("well", "Well")
    session = ProjectSession(
        Project("project", "Project", wells={well.well_id: well}),
        current_well_id=well.well_id,
    )
    controller = CuttingsController(session)
    initial = controller.add(1980.0, 1981.0, {"sandstone": 100.0})
    details: dict[str, str | None] = {
        "lba_distribution": "Even",
        "lba_cut": "Streaming",
        "lba_cut_speed": "Fast",
        "lba_cut_color": "Straw",
        "lba_residue_type": "Good",
        "lba_residue_color": "Amber",
        "lba_odour": "Moderate",
        "lba_stain": "Spotty",
    }
    sample = controller.set_analysis(
        initial.top_depth,
        initial.bottom_depth,
        calcite_percent=0.0,
        lba_group=1,
        lba_type_id=LBA_STANDARD_GROUPS[0].code,
        lba_intensity=2,
        lba_color="yellow",
        lba_description_i18n={"ru": "Описание ЛБА", "kk": "ЛБА сипаттамасы"},
        lba_description_source_language="ru",
        analysis_interpretation_i18n={"ru": "Заключение", "kk": "Қорытынды"},
        analysis_interpretation_source_language="ru",
        **details,
    )
    field_ids = (
        f"cuttings/{sample.sample_id}/lba_description",
        f"cuttings/{sample.sample_id}/analysis_interpretation",
    )
    reviewer = TranslationStatusController(session)
    for field_id in field_ids:
        reviewer.review_current(field_id=field_id, language="kk")
    initial_statuses = {field_id: dict(well.translation_statuses[field_id]) for field_id in field_ids}

    dialog = UnifiedCuttingsSampleDialog(
        sample.top_depth,
        sample.bottom_depth,
        LithotypeCatalogController(session).available(),
        language=AppLanguage.EN,
        sample=sample,
    )
    try:
        dialog.description_editors["en"].editor.setPlainText("Fine-grained sandstone")
        values = dialog.values()
        if edit_lba:
            values.update(lba_distribution=None, lba_cut_speed="  Slow  ")
            details.update(lba_distribution=None, lba_cut_speed="Slow")
        controller.update_full_sample(
            sample.sample_id,
            top_depth=dialog.top_depth,
            bottom_depth=dialog.bottom_depth,
            components=dialog.components(),
            content_language=AppLanguage.EN.value,
            **values,
        )
    finally:
        dialog.close()

    repository = PackageProjectRepository()
    path = tmp_path / "lba-details.geologpkg"
    repository.save(ProjectDocument(project=session.project), path)
    restored_well = repository.load(path).project.wells[well.well_id]
    restored = restored_well.cuttings[0]

    assert restored.sample_id == sample.sample_id
    assert restored.calcite_percent == 0.0
    assert "Fine-grained sandstone" in restored.description_i18n["en"]
    assert {field: getattr(sample, field) for field in details} == details
    assert {field: getattr(restored, field) for field in details} == details
    for field_id in field_ids:
        statuses = restored_well.translation_statuses[field_id]
        if edit_lba:
            assert statuses["ru"].state is TranslationState.REVIEWED
            assert statuses["kk"].state is TranslationState.STALE
        else:
            assert statuses == initial_statuses[field_id]


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
