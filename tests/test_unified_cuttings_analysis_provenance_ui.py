from __future__ import annotations

from PySide6.QtWidgets import QWidget

from geoworkbench.domain.models import CuttingsSample, Project, Well
from geoworkbench.project.cuttings_controller import CuttingsController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.unified_cuttings_sample_dialog import UnifiedCuttingsSampleDialog


class _CuttingsControllerStub:
    def __init__(
        self,
        *,
        lba_source_language: str | None = None,
        interpretation_source_language: str | None = None,
    ) -> None:
        self._lba_source_language = lba_source_language
        self._interpretation_source_language = interpretation_source_language

    def description_source_language(self, sample_id: str) -> str | None:
        assert sample_id
        return None

    def lba_description_source_language(self, sample_id: str) -> str | None:
        assert sample_id
        return self._lba_source_language

    def analysis_interpretation_source_language(self, sample_id: str) -> str | None:
        assert sample_id
        return self._interpretation_source_language


class _ParentStub(QWidget):
    def __init__(self, controller: object) -> None:
        super().__init__()
        self.cuttings_controller = controller


def _dialog(
    *,
    language: AppLanguage,
    sample: CuttingsSample | None = None,
    parent: QWidget | None = None,
) -> UnifiedCuttingsSampleDialog:
    return UnifiedCuttingsSampleDialog(
        100.0,
        105.0,
        (),
        language=language,
        sample=sample,
        parent=parent,
    )


def test_new_analysis_text_uses_ui_language_as_source_and_localized_payload(qapp) -> None:
    dialog = _dialog(language=AppLanguage.KK)

    blank = dialog.values()
    assert blank["lba_description_source_language"] is None
    assert blank["analysis_interpretation_source_language"] is None

    dialog.lba_description_inputs["kk"].setText("Біркелкі қоңыр люминесценция")
    dialog.interpretation_inputs["kk"].setPlainText("Мұнай белгілері расталды")
    values = dialog.values()

    assert values["lba_description_source_language"] == "kk"
    assert values["analysis_interpretation_source_language"] == "kk"
    assert values["lba_description_i18n"] == {
        "kk": "Біркелкі қоңыр люминесценция"
    }
    assert values["analysis_interpretation_i18n"] == {
        "kk": "Мұнай белгілері расталды"
    }


def test_existing_tracked_analysis_shows_persisted_sources_without_resubmitting(qapp) -> None:
    sample = CuttingsSample(
        "sample-1",
        100.0,
        105.0,
        lba_description_i18n={"ru": "Свечение", "kk": "Люминесценция"},
        analysis_interpretation_i18n={"ru": "Заключение", "kk": "Қорытынды"},
    )
    parent = _ParentStub(
        _CuttingsControllerStub(
            lba_source_language="kk",
            interpretation_source_language="kk",
        )
    )
    dialog = _dialog(language=AppLanguage.EN, sample=sample, parent=parent)

    assert dialog.lba_description_source_language_input.selected_language_code() == "kk"
    assert dialog.interpretation_source_language_input.selected_language_code() == "kk"

    values = dialog.values()
    assert values["lba_description_source_language"] is None
    assert values["analysis_interpretation_source_language"] is None
    assert values["lba_description_i18n"] == sample.lba_description_i18n
    assert values["analysis_interpretation_i18n"] == sample.analysis_interpretation_i18n


def test_legacy_analysis_text_is_promoted_only_after_explicit_source_selection(qapp) -> None:
    sample = CuttingsSample(
        "sample-legacy",
        100.0,
        105.0,
        lba_description="Legacy LBA",
        analysis_interpretation="Legacy interpretation",
    )
    dialog = _dialog(language=AppLanguage.EN, sample=sample)

    unchanged = dialog.values()
    assert unchanged["lba_description_i18n"] == {}
    assert unchanged["analysis_interpretation_i18n"] == {}
    assert unchanged["lba_description_source_language"] is None
    assert unchanged["analysis_interpretation_source_language"] is None

    dialog.lba_description_source_language_input.set_language_code("ru")
    dialog.interpretation_source_language_input.set_language_code("ru")
    promoted = dialog.values()

    assert promoted["lba_description_source_language"] == "ru"
    assert promoted["analysis_interpretation_source_language"] == "ru"
    assert promoted["lba_description_i18n"] == {"ru": "Legacy LBA"}
    assert promoted["analysis_interpretation_i18n"] == {
        "ru": "Legacy interpretation"
    }


def test_unified_dialog_payload_creates_tracked_analysis_through_full_save(qapp) -> None:
    well = Well("well", "Well")
    session = ProjectSession(Project("project", "Project", wells={well.well_id: well}))
    session.current_well_id = well.well_id
    controller = CuttingsController(session)
    parent = _ParentStub(controller)
    dialog = _dialog(language=AppLanguage.RU, parent=parent)
    dialog.lba_description_inputs["ru"].setText("Коричневое свечение")
    dialog.interpretation_inputs["ru"].setPlainText("Признаки нефтенасыщения")

    sample = controller.create_full_sample(
        100.0,
        105.0,
        {"sandstone": 100.0},
        **dialog.values(),
    )

    assert sample.lba_description_i18n == {"ru": "Коричневое свечение"}
    assert sample.analysis_interpretation_i18n == {
        "ru": "Признаки нефтенасыщения"
    }
    assert controller.lba_description_source_language(sample.sample_id) == "ru"
    assert controller.analysis_interpretation_source_language(sample.sample_id) == "ru"
