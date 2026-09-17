from __future__ import annotations

from PySide6.QtWidgets import QWidget

from geoworkbench.domain.models import CuttingsSample
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.unified_cuttings_sample_dialog import UnifiedCuttingsSampleDialog


class _CuttingsControllerStub:
    def __init__(self, source_language: str | None) -> None:
        self.source_language = source_language
        self.requested_sample_ids: list[str] = []

    def analysis_interpretation_source_language(
        self, sample_id: str
    ) -> str | None:
        self.requested_sample_ids.append(sample_id)
        return self.source_language

    def description_source_language(self, _sample_id: str) -> str | None:
        return None


class _Parent(QWidget):
    def __init__(self, source_language: str | None) -> None:
        super().__init__()
        self.cuttings_controller = _CuttingsControllerStub(source_language)


def _sample(
    *,
    legacy: str = "Заключение",
    localized: dict[str, str] | None = None,
) -> CuttingsSample:
    sample = CuttingsSample("sample-1", 100.0, 110.0)
    sample.analysis_interpretation = legacy
    sample.analysis_interpretation_i18n = dict(localized or {})
    return sample


def test_new_unified_sample_tracks_ui_language_only_after_interpretation_text(
    qapp,
) -> None:
    del qapp
    dialog = UnifiedCuttingsSampleDialog(
        100.0,
        110.0,
        (),
        language=AppLanguage.KK,
    )

    assert (
        dialog.interpretation_source_language_input.current_language_code()
        == "kk"
    )
    assert dialog.values()["analysis_interpretation_source_language"] is None

    dialog.interpretation_input.setPlainText("Геолог қорытындысы")
    values = dialog.values()

    assert values["analysis_interpretation_source_language"] == "kk"
    assert values["analysis_interpretation_i18n"] == {
        "kk": "Геолог қорытындысы"
    }
    dialog.close()


def test_existing_unified_sample_displays_persisted_source_without_resubmitting(
    qapp,
) -> None:
    parent = _Parent("ru")
    sample = _sample(localized={"ru": "Заключение"})
    dialog = UnifiedCuttingsSampleDialog(
        100.0,
        110.0,
        (),
        language=AppLanguage.EN,
        sample=sample,
        parent=parent,
    )

    assert parent.cuttings_controller.requested_sample_ids == ["sample-1"]
    assert (
        dialog.interpretation_source_language_input.current_language_code()
        == "ru"
    )
    values = dialog.values()
    assert values["analysis_interpretation_source_language"] is None
    assert values["analysis_interpretation_i18n"] == {"ru": "Заключение"}

    dialog.close()
    parent.close()


def test_legacy_untracked_interpretation_is_not_promoted_until_source_selected(
    qapp,
) -> None:
    parent = _Parent(None)
    sample = _sample(
        legacy="Legacy conclusion",
        localized={"und": "Legacy conclusion"},
    )
    dialog = UnifiedCuttingsSampleDialog(
        100.0,
        110.0,
        (),
        language=AppLanguage.RU,
        sample=sample,
        parent=parent,
    )

    assert (
        dialog.interpretation_source_language_input.selected_language_code()
        is None
    )
    values = dialog.values()
    assert values["analysis_interpretation_source_language"] is None
    assert values["analysis_interpretation_i18n"] == {
        "und": "Legacy conclusion"
    }

    dialog.interpretation_source_language_input.set_language_code("kk")
    changed = dialog.values()

    assert changed["analysis_interpretation_source_language"] == "kk"
    assert changed["analysis_interpretation_i18n"] == {
        "und": "Legacy conclusion",
        "kk": "Legacy conclusion",
    }
    dialog.close()
    parent.close()


def test_existing_translation_edit_preserves_source_and_updates_current_language(
    qapp,
) -> None:
    parent = _Parent("ru")
    sample = _sample(
        localized={
            "ru": "Заключение",
            "en": "Old conclusion",
        }
    )
    dialog = UnifiedCuttingsSampleDialog(
        100.0,
        110.0,
        (),
        language=AppLanguage.EN,
        sample=sample,
        parent=parent,
    )

    dialog.interpretation_input.setPlainText("Updated conclusion")
    values = dialog.values()

    assert values["analysis_interpretation_source_language"] is None
    assert values["analysis_interpretation_i18n"] == {
        "ru": "Заключение",
        "en": "Updated conclusion",
    }
    dialog.close()
    parent.close()


def test_explicit_source_change_promotes_visible_text_into_selected_language(
    qapp,
) -> None:
    parent = _Parent("ru")
    sample = _sample(localized={"ru": "Заключение"})
    dialog = UnifiedCuttingsSampleDialog(
        100.0,
        110.0,
        (),
        language=AppLanguage.EN,
        sample=sample,
        parent=parent,
    )

    dialog.interpretation_source_language_input.set_language_code("kk")
    values = dialog.values()

    assert values["analysis_interpretation_source_language"] == "kk"
    assert values["analysis_interpretation_i18n"] == {
        "ru": "Заключение",
        "kk": "Заключение",
    }
    dialog.close()
    parent.close()
