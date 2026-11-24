from pathlib import Path

import pytest
from PySide6.QtWidgets import QTabWidget

from geoworkbench.domain.models import CuttingsSample, Project, Well
from geoworkbench.domain.translation_status import TranslationState
from geoworkbench.project.cuttings_controller import CuttingsController
from geoworkbench.project.session import ProjectSession
from geoworkbench.project.translation_status_controller import TranslationStatusController
from geoworkbench.services.localization import AppLanguage
from geoworkbench.storage.package_project_repository import PackageProjectRepository
from geoworkbench.storage.project_codec import ProjectDocument
from geoworkbench.ui.sample_analysis_dialog import SampleAnalysisDialog


def test_sample_analysis_dialog_keeps_absent_values_unset(qapp) -> None:
    dialog = SampleAnalysisDialog(500.0, 510.0, language=AppLanguage.EN)

    values = dialog.values()

    assert dialog.windowTitle() == "Sample analysis — 500–510 м"
    assert values["calcite_percent"] is None
    assert values["dolomite_percent"] is None
    assert values["lba_group"] is None
    assert values["lba_intensity"] is None
    assert values["lba_description_i18n"] == {}
    assert values["analysis_interpretation_i18n"] == {}
    dialog.close()


def test_sample_analysis_dialog_loads_existing_interval(qapp) -> None:
    sample = CuttingsSample(
        "sample",
        500.0,
        510.0,
        calcite_percent=65.5,
        dolomite_percent=20.0,
        lba_group=3,
        lba_type_id="Oil show",
        lba_intensity=4,
        lba_color="yellow-white",
        lba_distribution="spotted",
        lba_cut="Streaming",
        lba_cut_speed="Fast",
        lba_cut_color="Straw",
        lba_residue_type="Good",
        lba_residue_color="Amber",
        lba_odour="Moderate",
        lba_stain="Spotty",
        lba_description="bright fluorescence",
        analysis_interpretation="Manual geologist conclusion",
    )

    dialog = SampleAnalysisDialog(
        500.0,
        510.0,
        language=AppLanguage.RU,
        sample=sample,
    )

    assert dialog.values() == {
        "calcite_percent": 65.5,
        "dolomite_percent": 20.0,
        "lba_group": 3,
        "lba_type_id": "Oil show",
        "lba_intensity": 4,
        "lba_color": "yellow-white",
        "lba_distribution": "spotted",
        "lba_cut": "Streaming",
        "lba_cut_speed": "Fast",
        "lba_cut_color": "Straw",
        "lba_residue_type": "Good",
        "lba_residue_color": "Amber",
        "lba_odour": "Moderate",
        "lba_stain": "Spotty",
        "show_observations": [],
        "lba_description": "bright fluorescence",
        "lba_description_i18n": {},
        "analysis_interpretation": "Manual geologist conclusion",
        "analysis_interpretation_i18n": {},
        "analysis_interpretation_source_language": None,
    }
    dialog.close()


def test_sample_analysis_dialog_edits_all_author_text_languages(qapp) -> None:
    dialog = SampleAnalysisDialog(500.0, 510.0, language=AppLanguage.EN)

    assert dialog.findChild(QTabWidget, "lba-description-language-tabs").count() == 3
    assert dialog.findChild(QTabWidget, "analysis-interpretation-language-tabs").count() == 3
    dialog.lba_description_inputs["ru"].setText("Яркая флуоресценция")
    dialog.lba_description_inputs["kk"].setText("Жарқын флуоресценция")
    dialog.lba_description_inputs["en"].setText("Bright fluorescence")
    dialog.interpretation_inputs["ru"].setPlainText("Признаки нефти")
    dialog.interpretation_inputs["kk"].setPlainText("Мұнай белгілері")
    dialog.interpretation_inputs["en"].setPlainText("Oil show")

    values = dialog.values()
    assert values["lba_description_i18n"] == {
        "ru": "Яркая флуоресценция",
        "kk": "Жарқын флуоресценция",
        "en": "Bright fluorescence",
    }
    assert values["analysis_interpretation_i18n"]["kk"] == "Мұнай белгілері"
    dialog.close()


def test_sample_analysis_dialog_does_not_promote_legacy_fallback(qapp) -> None:
    sample = CuttingsSample(
        "sample",
        500.0,
        510.0,
        lba_description="Legacy LBA",
        analysis_interpretation="Legacy conclusion",
    )
    dialog = SampleAnalysisDialog(
        500.0,
        510.0,
        language=AppLanguage.RU,
        sample=sample,
    )

    values = dialog.values()
    assert values["lba_description_i18n"] == {}
    assert values["analysis_interpretation_i18n"] == {}
    dialog.close()


def _tracked_analysis(
    calcite: float, dolomite: float
) -> tuple[CuttingsController, Well, CuttingsSample, str]:
    well = Well("well", "Well")
    session = ProjectSession(
        Project("project", "Project", wells={well.well_id: well}),
        current_well_id=well.well_id,
    )
    controller = CuttingsController(session)
    sample = controller.set_analysis(
        500.0,
        510.0,
        calcite_percent=calcite,
        dolomite_percent=dolomite,
        analysis_interpretation_i18n={"ru": "Заключение", "kk": "Қорытынды"},
        analysis_interpretation_source_language="ru",
    )
    field_id = f"cuttings/{sample.sample_id}/analysis_interpretation"
    TranslationStatusController(session).review_current(field_id=field_id, language="kk")
    session.dirty = False
    return controller, well, sample, field_id


@pytest.mark.parametrize("use_set_analysis", [True, False], ids=["set-analysis", "update-analysis"])
def test_untouched_calcimetry_keeps_precision_and_review(
    qapp, tmp_path: Path, use_set_analysis: bool
) -> None:
    calcite, dolomite = 34.1264, 20.5689
    controller, well, sample, field_id = _tracked_analysis(calcite, dolomite)
    content_revision = well.content_revision
    reviewed = well.translation_statuses[field_id]["kk"]
    dialog = SampleAnalysisDialog(
        sample.top_depth, sample.bottom_depth, language=AppLanguage.EN, sample=sample
    )
    try:
        values = dialog.values()
        assert (values["calcite_percent"], values["dolomite_percent"]) == (calcite, dolomite)
        if use_set_analysis:
            saved = controller.set_analysis(dialog.top_depth, dialog.bottom_depth, **values)
        else:
            saved = controller.update_analysis(
                sample.sample_id,
                top_depth=dialog.top_depth,
                bottom_depth=dialog.bottom_depth,
                **values,
            )
    finally:
        dialog.close()

    assert saved is sample
    assert (sample.calcite_percent, sample.dolomite_percent) == (calcite, dolomite)
    assert well.content_revision == content_revision
    assert well.translation_statuses[field_id]["kk"] == reviewed
    assert not controller.session.dirty

    repository = PackageProjectRepository()
    path = tmp_path / "calcimetry.geologpkg"
    repository.save(ProjectDocument(project=controller.session.project), path)
    restored = repository.load(path).project.wells[well.well_id]
    assert restored.cuttings == [sample]
    assert restored.translation_statuses[field_id]["kk"] == reviewed


@pytest.mark.parametrize("replacement", [42.4, 0.0, None], ids=["change", "zero", "clear"])
def test_editing_one_calcimetry_value_preserves_the_other(
    qapp, replacement: float | None
) -> None:
    dolomite = 20.5689
    controller, well, sample, field_id = _tracked_analysis(34.1264, dolomite)
    dialog = SampleAnalysisDialog(
        sample.top_depth, sample.bottom_depth, language=AppLanguage.EN, sample=sample
    )
    try:
        dialog.calcite_input.setValue(-1.0 if replacement is None else replacement)
        controller.update_analysis(
            sample.sample_id,
            top_depth=dialog.top_depth,
            bottom_depth=dialog.bottom_depth,
            **dialog.values(),
        )
    finally:
        dialog.close()

    assert (sample.calcite_percent, sample.dolomite_percent) == (replacement, dolomite)
    assert well.translation_statuses[field_id]["kk"].state is TranslationState.STALE
    assert controller.session.dirty


def test_set_analysis_accepts_a_precise_total_that_display_rounding_exceeds(qapp) -> None:
    calcite, dolomite = 0.05, 99.95
    controller, well, sample, _ = _tracked_analysis(calcite, dolomite)
    content_revision = well.content_revision
    dialog = SampleAnalysisDialog(
        sample.top_depth, sample.bottom_depth, language=AppLanguage.EN, sample=sample
    )
    try:
        saved = controller.set_analysis(dialog.top_depth, dialog.bottom_depth, **dialog.values())
    finally:
        dialog.close()
    assert saved is sample
    assert (sample.calcite_percent, sample.dolomite_percent) == (calcite, dolomite)
    assert well.content_revision == content_revision
    assert not controller.session.dirty


def test_set_analysis_rejects_an_edit_exceeding_the_precise_total(qapp) -> None:
    calcite, dolomite = 60.0, 35.149
    controller, well, sample, field_id = _tracked_analysis(calcite, dolomite)
    content_revision = well.content_revision
    reviewed = well.translation_statuses[field_id]["kk"]
    dialog = SampleAnalysisDialog(
        sample.top_depth, sample.bottom_depth, language=AppLanguage.EN, sample=sample
    )
    try:
        dialog.calcite_input.setValue(64.9)
        with pytest.raises(ValueError, match="100%"):
            controller.set_analysis(dialog.top_depth, dialog.bottom_depth, **dialog.values())
    finally:
        dialog.close()

    assert (sample.calcite_percent, sample.dolomite_percent) == (calcite, dolomite)
    assert well.content_revision == content_revision
    assert well.translation_statuses[field_id]["kk"] == reviewed
    assert not controller.session.dirty
