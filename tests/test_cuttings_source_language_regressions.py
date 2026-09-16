from __future__ import annotations

from PySide6.QtWidgets import QWidget

from geoworkbench.domain.models import CuttingsSample
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.unified_cuttings_sample_dialog import UnifiedCuttingsSampleDialog


class _CuttingsControllerStub:
    def __init__(self, source_language: str | None) -> None:
        self._source_language = source_language

    def description_source_language(self, sample_id: str) -> str | None:
        assert sample_id
        return self._source_language


class _ParentStub(QWidget):
    def __init__(self, source_language: str | None) -> None:
        super().__init__()
        self.cuttings_controller = _CuttingsControllerStub(source_language)


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


def test_new_sample_without_description_does_not_start_tracking(qapp) -> None:
    dialog = _dialog(language=AppLanguage.KK)

    assert dialog.description_source_language_input.currentData() == "kk"
    assert dialog.values()["description_source_language"] is None


def test_existing_sample_shows_persisted_source_without_resubmitting_it(qapp) -> None:
    sample = CuttingsSample(sample_id="sample-1", top_depth=100.0, bottom_depth=105.0)
    parent = _ParentStub("kk")
    dialog = _dialog(language=AppLanguage.EN, sample=sample, parent=parent)

    assert dialog.description_source_language_input.currentData() == "kk"
    assert dialog.values()["description_source_language"] is None

    russian_index = dialog.description_source_language_input.findData("ru")
    assert russian_index >= 0
    dialog.description_source_language_input.setCurrentIndex(russian_index)
    assert dialog.values()["description_source_language"] == "ru"


def test_legacy_visible_description_is_promoted_when_selected_as_source(qapp) -> None:
    sample = CuttingsSample(
        sample_id="sample-1",
        top_depth=100.0,
        bottom_depth=105.0,
        description="legacy description",
    )
    dialog = _dialog(language=AppLanguage.EN, sample=sample)
    russian_index = dialog.description_source_language_input.findData("ru")

    assert russian_index >= 0
    dialog.description_source_language_input.setCurrentIndex(russian_index)
    values = dialog.values()

    assert values["description_source_language"] == "ru"
    assert "legacy description" in values["description_i18n"]["ru"]
