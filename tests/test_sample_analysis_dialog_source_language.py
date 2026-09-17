from __future__ import annotations

from PySide6.QtWidgets import QApplication, QWidget

from geoworkbench.domain.models import CuttingsSample
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.sample_analysis_dialog import SampleAnalysisDialog


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


class _CuttingsControllerStub:
    def __init__(self, source_language: str | None) -> None:
        self.source_language = source_language
        self.requested_sample_ids: list[str] = []

    def analysis_interpretation_source_language(self, sample_id: str) -> str | None:
        self.requested_sample_ids.append(sample_id)
        return self.source_language


class _Parent(QWidget):
    def __init__(self, source_language: str | None) -> None:
        super().__init__()
        self.cuttings_controller = _CuttingsControllerStub(source_language)


def _sample() -> CuttingsSample:
    sample = CuttingsSample("sample-1", 100.0, 110.0)
    sample.analysis_interpretation = "Заключение"
    sample.analysis_interpretation_i18n = {"ru": "Заключение"}
    return sample


def test_new_analysis_tracks_ui_language_only_when_conclusion_has_text() -> None:
    _app()
    dialog = SampleAnalysisDialog(100.0, 110.0, language=AppLanguage.KK)

    assert dialog.interpretation_source_language_input.current_language_code() == "kk"
    assert dialog.values()["analysis_interpretation_source_language"] is None

    dialog.interpretation_inputs["kk"].setPlainText("Геолог қорытындысы")

    assert dialog.values()["analysis_interpretation_source_language"] == "kk"
    dialog.close()


def test_existing_analysis_displays_persisted_source_without_resubmitting_it() -> None:
    _app()
    parent = _Parent("ru")
    dialog = SampleAnalysisDialog(
        100.0,
        110.0,
        language=AppLanguage.EN,
        sample=_sample(),
        parent=parent,
    )

    assert parent.cuttings_controller.requested_sample_ids == ["sample-1"]
    assert dialog.interpretation_source_language_input.current_language_code() == "ru"
    assert dialog.values()["analysis_interpretation_source_language"] is None
    dialog.close()
    parent.close()


def test_existing_analysis_submits_explicit_source_language_change() -> None:
    _app()
    parent = _Parent("ru")
    dialog = SampleAnalysisDialog(
        100.0,
        110.0,
        language=AppLanguage.RU,
        sample=_sample(),
        parent=parent,
    )

    dialog.interpretation_source_language_input.set_language_code("kk")

    assert dialog.values()["analysis_interpretation_source_language"] == "kk"
    dialog.close()
    parent.close()


def test_existing_legacy_analysis_keeps_absent_provenance_until_user_selects_language() -> None:
    _app()
    parent = _Parent(None)
    dialog = SampleAnalysisDialog(
        100.0,
        110.0,
        language=AppLanguage.EN,
        sample=_sample(),
        parent=parent,
    )

    assert dialog.interpretation_source_language_input.selected_language_code() is None
    assert dialog.values()["analysis_interpretation_source_language"] is None

    dialog.interpretation_source_language_input.set_language_code("en")

    assert dialog.values()["analysis_interpretation_source_language"] == "en"
    dialog.close()
    parent.close()
