from __future__ import annotations

from geoworkbench.domain.models import CuttingsSample
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.unified_cuttings_sample_dialog import UnifiedCuttingsSampleDialog


def _dialog(
    *,
    language: AppLanguage,
    sample: CuttingsSample | None = None,
) -> UnifiedCuttingsSampleDialog:
    return UnifiedCuttingsSampleDialog(
        100.0,
        105.0,
        (),
        language=language,
        sample=sample,
    )


def test_new_sample_defaults_source_language_to_ui_language(qapp) -> None:
    dialog = _dialog(language=AppLanguage.KK)

    assert dialog.description_source_language_input.currentData() == "kk"
    assert dialog.values()["description_source_language"] == "kk"


def test_existing_sample_preserves_source_language_by_default(qapp) -> None:
    sample = CuttingsSample(sample_id="sample-1", top_depth=100.0, bottom_depth=105.0)
    dialog = _dialog(language=AppLanguage.EN, sample=sample)

    assert dialog.description_source_language_input.currentData() is None
    assert dialog.values()["description_source_language"] is None


def test_existing_sample_can_explicitly_change_source_language(qapp) -> None:
    sample = CuttingsSample(sample_id="sample-1", top_depth=100.0, bottom_depth=105.0)
    dialog = _dialog(language=AppLanguage.EN, sample=sample)
    russian_index = dialog.description_source_language_input.findData("ru")

    assert russian_index >= 0
    dialog.description_source_language_input.setCurrentIndex(russian_index)
    assert dialog.values()["description_source_language"] == "ru"
