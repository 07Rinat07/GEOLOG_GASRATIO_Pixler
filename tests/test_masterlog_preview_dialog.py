from collections.abc import Callable
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QInputDialog,
    QMessageBox,
    QPlainTextEdit,
)

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain, MasterlogTemplate
from geoworkbench.domain.translation_status import TranslationState
from geoworkbench.printing.masterlog_output import MasterlogOutputSettings
from geoworkbench.project.cuttings_controller import CuttingsController
from geoworkbench.project.session import ProjectSession
from geoworkbench.project.translation_status_controller import TranslationStatusController
from geoworkbench.services.localization import AppLanguage
from geoworkbench.storage.package_project_repository import PackageProjectRepository
from geoworkbench.storage.project_codec import ProjectDocument
from geoworkbench.ui.adaptive_toolbar import AdaptiveActionToolBar
from geoworkbench.ui.masterlog_interval_fill_dialog import CuttingsCompositionDialog
from geoworkbench.ui.masterlog_preview_dialog import MasterlogPreviewDialog
from geoworkbench.ui.sample_analysis_dialog import SampleAnalysisDialog


def test_masterlog_preview_dialog_uses_selected_template(qapp) -> None:
    template = MasterlogTemplate("standard", "Daily form")
    settings = MasterlogOutputSettings(100.0, 200.0, AppLanguage.EN)

    dialog = MasterlogPreviewDialog(
        template, ProjectSession(), language=AppLanguage.EN, settings=settings
    )

    assert dialog.windowTitle() == "Masterlog preview — Daily form"
    assert dialog.preview.template is template
    assert dialog.preview.settings is settings
    assert dialog.inspect_button.text() == "Inspect"
    assert dialog.lithology_button.text() == "Fill lithology"
    assert dialog.cuttings_button.text() == "Fill cuttings"
    assert dialog.description_button.text() == "Cuttings description"
    assert dialog.analysis_button.text() == "Calcimetry / LBA"
    assert dialog.stratigraphy_button.text() == "Stratigraphy"
    assert dialog.pin_button.text() == "Pin for PDF"
    assert not dialog.pin_button.isEnabled()
    assert dialog.callouts_button.text() == "Callouts..."
    dialog._set_mode("lithology")
    assert dialog.preview.selection_mode == "lithology"
    assert dialog.lithology_button.isChecked()
    dialog._set_mode("analysis")
    assert dialog.preview.selection_mode == "analysis"
    assert dialog.analysis_button.isChecked()
    dialog._set_mode("cuttings_description")
    assert dialog.preview.selection_mode == "cuttings_description"
    assert dialog.description_button.isChecked()
    dialog._set_mode("stratigraphy")
    assert dialog.preview.selection_mode == "stratigraphy"
    assert dialog.stratigraphy_button.isChecked()
    dialog.close()


def test_masterlog_preview_dialog_fits_work_area_and_uses_overflow_toolbar(qapp) -> None:
    dialog = MasterlogPreviewDialog(
        MasterlogTemplate("standard", "Adaptive"),
        ProjectSession(),
        language=AppLanguage.EN,
    )
    try:
        screen = dialog.screen()
        assert screen is not None
        available = screen.availableGeometry()
        assert dialog.minimumWidth() <= dialog.width() <= available.width()
        assert dialog.minimumHeight() <= dialog.height() <= available.height()

        toolbar = dialog.findChild(AdaptiveActionToolBar, "masterlog-preview-actions")
        assert toolbar is not None
        assert [action.text() for action in toolbar.actions() if action.text()] == [
            "Inspect",
            "Fill lithology",
            "Fill cuttings",
            "Cuttings description",
            "Calcimetry / LBA",
            "Stratigraphy",
            "Pin for PDF",
            "Callouts...",
        ]
        assert dialog.preview.minimumWidth() <= 320
        assert dialog.preview.minimumHeight() <= 240

        buttons = dialog.findChild(QDialogButtonBox)
        assert buttons is not None
        assert not toolbar.isAncestorOf(buttons)
    finally:
        dialog.close()


@pytest.mark.parametrize(
    ("selected", "edited_top", "analysis_bounds"),
    [
        pytest.param((150.0004, 151.1234), 150.125, None, id="edit-one-boundary"),
        pytest.param((150.0001, 150.0004), None, None, id="unchanged-submillimeter-range"),
        pytest.param((150.0, 151.0), 150.001, (150.0, 151.0), id="edit-near-analysis-record"),
        pytest.param(
            (150.0004, 151.0004), None, (150.0, 151.0), id="unchanged-near-analysis-record"
        ),
    ],
)
def test_masterlog_fill_cuttings_saves_precise_or_edited_bounds(
    qapp,
    monkeypatch: pytest.MonkeyPatch,
    selected: tuple[float, float],
    edited_top: float | None,
    analysis_bounds: tuple[float, float] | None,
) -> None:
    session = ProjectSession()
    session.add_dataset(
        Dataset("dataset", "Well", DatasetKind.GTI, DepthDomain.MD, np.array([100.0, 200.0]))
    )
    controller = CuttingsController(session)
    overlay = (
        controller.set_analysis(*analysis_bounds, calcite_percent=12.5)
        if analysis_bounds is not None
        else None
    )
    overlay_before = deepcopy(overlay)

    def fill(dialog: CuttingsCompositionDialog) -> QDialog.DialogCode:
        if edited_top is not None:
            dialog.top_input.setValue(edited_top)
        sandstone = dialog.findChild(QDoubleSpinBox, "cuttings-percentage-sandstone")
        assert sandstone is not None
        sandstone.setValue(100.0)
        ok = dialog.buttons.button(QDialogButtonBox.StandardButton.Ok)
        assert ok is not None
        ok.click()
        assert dialog.result() == QDialog.DialogCode.Accepted
        return QDialog.DialogCode.Accepted

    def unexpected_warning(*args: object) -> None:
        pytest.fail(f"Filling cuttings raised a warning: {args[-1]}")

    monkeypatch.setattr(CuttingsCompositionDialog, "exec", fill)
    monkeypatch.setattr(QMessageBox, "warning", unexpected_warning)
    preview = MasterlogPreviewDialog(
        MasterlogTemplate("standard", "Daily form"), session, language=AppLanguage.EN
    )
    try:
        preview._fill_interval(*selected, "cuttings")
    finally:
        preview.close()

    samples = controller.available()
    (saved,) = (sample for sample in samples if sample.components)
    if overlay is not None and edited_top is None:
        assert samples == (overlay,)
        assert saved is overlay
        assert saved.calcite_percent == 12.5
        assert (saved.top_depth, saved.bottom_depth) == analysis_bounds
    else:
        assert len(samples) == (2 if overlay is not None else 1)
        if overlay is not None:
            assert controller.get(overlay.sample_id) is overlay
            assert overlay == overlay_before
        expected_top = selected[0] if edited_top is None else edited_top
        assert (saved.top_depth, saved.bottom_depth) == (expected_top, selected[1])
    assert [(item.lithotype_id, item.percentage) for item in saved.components] == [
        ("sandstone", 100.0)
    ]


def _masterlog_geology_session() -> ProjectSession:
    session = ProjectSession()
    session.add_dataset(
        Dataset("dataset", "Well", DatasetKind.GTI, DepthDomain.MD, np.array([100.0, 200.0]))
    )
    return session


def _fill_masterlog_description(
    monkeypatch: pytest.MonkeyPatch,
    session: ProjectSession,
    selected: tuple[float, float],
    language: AppLanguage,
    initial_text: str,
    replacement: str | None = None,
) -> None:
    def fill(dialog: QInputDialog) -> QDialog.DialogCode:
        editor = dialog.findChild(QPlainTextEdit)
        assert editor is not None
        assert editor.toPlainText() == dialog.textValue() == initial_text
        if replacement is not None:
            editor.setPlainText(replacement)
        buttons = dialog.findChild(QDialogButtonBox)
        assert buttons is not None
        buttons.button(QDialogButtonBox.StandardButton.Ok).click()
        assert dialog.result() == QDialog.DialogCode.Accepted
        return QDialog.DialogCode.Accepted

    def unexpected_warning(*args: object) -> None:
        pytest.fail(f"Filling the description raised a warning: {args[-1]}")

    monkeypatch.setattr(QInputDialog, "exec", fill)
    monkeypatch.setattr(QMessageBox, "warning", unexpected_warning)
    preview = MasterlogPreviewDialog(
        MasterlogTemplate("standard", "Daily form"), session, language=language
    )
    try:
        preview._fill_interval(*selected, "cuttings_description")
    finally:
        preview.close()


def test_masterlog_description_updates_active_language_at_stored_interval(
    qapp, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    session = _masterlog_geology_session()
    controller = CuttingsController(session)
    sample = controller.create_full_sample(
        150.0004,
        151.1234,
        {"sandstone": 100.0},
        calcite_percent=22.543,
        description_i18n={"en": "English source", "kk": "Kazakh text"},
        description_source_language="en",
    )
    sample.description = "Legacy description without a Russian language entry"
    field_id = f"cuttings/{sample.sample_id}/description"
    TranslationStatusController(session).review_current(field_id=field_id, language="kk")
    well = session.current_well
    assert well is not None
    statuses = deepcopy(well.translation_statuses[field_id])
    source_revision = well.authored_field_revisions[field_id]
    expected = deepcopy(sample)
    expected.description_i18n["kk"] = "Edited Kazakh text"
    session.dirty = False

    _fill_masterlog_description(
        monkeypatch, session, (150.001, 151.124), AppLanguage.KK, "Kazakh text", "Edited Kazakh text"
    )

    assert controller.get(sample.sample_id) is sample
    assert controller.available() == (expected,)
    assert session.dirty
    assert well.authored_field_revisions[field_id] == source_revision
    assert well.translation_statuses[field_id]["en"] == statuses["en"]
    assert well.translation_statuses[field_id]["ru"] == statuses["ru"]
    assert well.translation_statuses[field_id]["kk"].state is TranslationState.DRAFT

    repository = PackageProjectRepository()
    path = tmp_path / "masterlog-description.geologpkg"
    repository.save(ProjectDocument(project=session.project), path)
    restored = repository.load(path).project.wells[well.well_id]
    assert restored.cuttings == [expected]
    assert restored.translation_statuses == well.translation_statuses
    assert restored.authored_field_source_languages[field_id] == "en"


def test_masterlog_description_unchanged_fallback_keeps_raw_markup_and_review(
    qapp, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = _masterlog_geology_session()
    controller = CuttingsController(session)
    raw_markup = "<p><b>Russian text</b></p>\r\n<p>Next paragraph</p>"
    sample = controller.create_full_sample(
        150.0,
        151.0,
        {"sandstone": 100.0},
        description_i18n={"en": "English source", "ru": raw_markup},
        description_source_language="en",
    )
    field_id = f"cuttings/{sample.sample_id}/description"
    TranslationStatusController(session).review_current(field_id=field_id, language="ru")
    well = session.current_well
    assert well is not None
    before = deepcopy(well)
    session.dirty = False

    _fill_masterlog_description(
        monkeypatch, session, (150.0, 151.0), AppLanguage.KK, raw_markup.replace("\r\n", "\n")
    )

    assert not session.dirty
    assert well.cuttings == before.cuttings
    assert sample.description_i18n == {"en": "English source", "ru": raw_markup}
    assert well.translation_statuses == before.translation_statuses
    assert well.authored_field_revisions == before.authored_field_revisions
    assert well.language_revisions == before.language_revisions
    assert well.content_revision == before.content_revision


def test_masterlog_description_creates_precise_interval_in_active_language(
    qapp, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = _masterlog_geology_session()
    controller = CuttingsController(session)
    selected = (150.0004, 150.0005)

    _fill_masterlog_description(monkeypatch, session, selected, AppLanguage.EN, "", "New text")

    (sample,) = controller.available()
    assert (sample.top_depth, sample.bottom_depth) == selected
    assert sample.description is None
    assert sample.description_i18n == {"en": "New text"}


def _fill_masterlog_analysis(
    monkeypatch: pytest.MonkeyPatch,
    session: ProjectSession,
    selected: tuple[float, float],
    edited: tuple[float | None, float | None],
    expected_calcite: float,
    *,
    calcite: float | None = 42.0,
    inspect_dialog: Callable[[SampleAnalysisDialog], None] | None = None,
) -> list[str]:
    warnings: list[str] = []

    def fill(dialog: SampleAnalysisDialog) -> QDialog.DialogCode:
        assert dialog.calcite_input.value() == expected_calcite
        if inspect_dialog is not None:
            inspect_dialog(dialog)
        edited_top, edited_bottom = edited
        if edited_top is not None:
            dialog.top_input.setValue(edited_top)
        if edited_bottom is not None:
            dialog.bottom_input.setValue(edited_bottom)
        if calcite is not None:
            dialog.calcite_input.setValue(calcite)
        buttons = dialog.findChild(QDialogButtonBox)
        assert buttons is not None
        ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        assert ok is not None
        ok.click()
        assert dialog.result() == QDialog.DialogCode.Accepted
        return QDialog.DialogCode.Accepted

    def record_warning(_parent: object, _title: str, message: str) -> None:
        warnings.append(message)

    monkeypatch.setattr(SampleAnalysisDialog, "exec", fill)
    monkeypatch.setattr(QMessageBox, "warning", record_warning)
    preview = MasterlogPreviewDialog(
        MasterlogTemplate("standard", "Daily form"), session, language=AppLanguage.EN
    )
    try:
        preview._fill_interval(*selected, "analysis")
    finally:
        preview.close()
    return warnings


@pytest.mark.parametrize(
    ("selected", "edited_top", "neighbor_bounds"),
    [
        pytest.param((150.0004, 151.1234), 150.125, None, id="edit-one-boundary"),
        pytest.param((150.0001, 150.0004), None, None, id="unchanged-submillimeter-range"),
        pytest.param(
            (150.0, 151.1234), 150.499, (150.5, 151.1234), id="edit-near-analysis-record"
        ),
    ],
)
def test_masterlog_fill_new_analysis_saves_precise_or_edited_bounds(
    qapp,
    monkeypatch: pytest.MonkeyPatch,
    selected: tuple[float, float],
    edited_top: float | None,
    neighbor_bounds: tuple[float, float] | None,
) -> None:
    session = _masterlog_geology_session()
    controller = CuttingsController(session)
    neighbor = (
        controller.set_analysis(*neighbor_bounds, calcite_percent=12.5)
        if neighbor_bounds is not None
        else None
    )
    neighbor_before = deepcopy(neighbor)

    assert _fill_masterlog_analysis(monkeypatch, session, selected, (edited_top, None), -1.0) == []

    samples = controller.available()
    assert len(samples) == (2 if neighbor is not None else 1)
    if neighbor is not None:
        assert controller.get(neighbor.sample_id) is neighbor
        assert neighbor == neighbor_before
    (saved,) = (sample for sample in samples if sample is not neighbor)
    expected_top = selected[0] if edited_top is None else edited_top
    assert (saved.top_depth, saved.bottom_depth) == (expected_top, selected[1])
    assert saved.calcite_percent == 42.0


@pytest.mark.parametrize("destination_occupied", [False, True], ids=["move", "occupied"])
def test_masterlog_fill_existing_analysis_moves_only_selected_sample(
    qapp, monkeypatch: pytest.MonkeyPatch, destination_occupied: bool
) -> None:
    session = _masterlog_geology_session()
    controller = CuttingsController(session)
    selected = (150.0004, 151.1234)
    destination = (152.0, 153.0)
    sample = controller.create_full_sample(
        *selected, {"sandstone": 100.0}, calcite_percent=30.0, description="Original description"
    )
    if destination_occupied:
        controller.set_analysis(*destination, calcite_percent=25.0)
    samples_before = deepcopy(controller.available())
    session.dirty = False

    warnings = _fill_masterlog_analysis(monkeypatch, session, selected, destination, 30.0)

    assert controller.get(sample.sample_id) is sample
    if destination_occupied:
        assert len(warnings) == 1 and "уже существует другая проба" in warnings[0]
        assert controller.available() == samples_before
        assert not session.dirty
    else:
        assert warnings == []
        assert controller.available() == (sample,)
        assert (sample.top_depth, sample.bottom_depth) == destination
        assert sample.calcite_percent == 42.0
        assert sample.components == samples_before[0].components
        assert sample.description == "Original description"
        assert session.dirty


def test_masterlog_fill_existing_analysis_keeps_precise_bounds_for_near_selection(
    qapp, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = _masterlog_geology_session()
    controller = CuttingsController(session)
    stored = (150.0004, 151.1234)
    selected = (stored[0] + 5e-7, stored[1] + 5e-7)
    neighbor = controller.set_analysis(150.001, 151.124, calcite_percent=25.0)
    neighbor_before = deepcopy(neighbor)
    sample = controller.set_analysis(*stored, calcite_percent=30.0, absolute_tolerance=0.0)

    assert _fill_masterlog_analysis(monkeypatch, session, selected, (None, None), 30.0) == []

    assert controller.available() == (sample, neighbor)
    assert controller.get(sample.sample_id) is sample
    assert neighbor == neighbor_before
    assert (sample.top_depth, sample.bottom_depth) == stored
    assert sample.calcite_percent == 42.0


@pytest.mark.parametrize(
    ("calcite", "edit_russian", "expected_state"),
    [
        pytest.param(None, False, TranslationState.REVIEWED, id="no-op"),
        pytest.param(42.0, False, TranslationState.STALE, id="calcimetry-only"),
        pytest.param(None, True, TranslationState.DRAFT, id="change-russian-text"),
    ],
)
def test_masterlog_approximate_analysis_loads_and_preserves_existing_data(
    qapp,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    calcite: float | None,
    edit_russian: bool,
    expected_state: TranslationState,
) -> None:
    session = _masterlog_geology_session()
    controller = CuttingsController(session)
    stored = (150.0005, 151.1235)
    selected = (150.0, 151.123)
    sample = controller.set_analysis(
        *stored,
        calcite_percent=30.0,
        dolomite_percent=11.321,
        lba_color="Tan",
        lba_description_i18n={"ru": "Localized LBA"},
        analysis_interpretation_i18n={"kk": "Original conclusion", "ru": "Localized conclusion"},
        analysis_interpretation_source_language="kk",
    )
    sample.lba_description = "Legacy LBA"
    sample.analysis_interpretation = "Legacy conclusion"
    field_id = f"cuttings/{sample.sample_id}/analysis_interpretation"
    TranslationStatusController(session).review_current(field_id=field_id, language="ru")
    well = session.current_well
    assert well is not None
    language_revisions = dict(well.language_revisions)
    source_revision = well.authored_field_revisions[field_id]
    content_revision = well.content_revision
    expected = deepcopy(sample)
    session.dirty = False

    def inspect_dialog(dialog: SampleAnalysisDialog) -> None:
        assert (dialog.top_depth, dialog.bottom_depth) == stored
        assert dialog.dolomite_input.percentage() == 11.321
        assert dialog.interpretation_source_language_input.current_language_code() == "kk"
        assert dialog.values()["analysis_interpretation_source_language"] is None
        assert dialog.lba_description_inputs["ru"].text() == "Localized LBA"
        assert dialog.interpretation_inputs["ru"].toPlainText() == "Localized conclusion"
        if edit_russian:
            dialog.lba_description_inputs["ru"].setText("Updated LBA")
            dialog.interpretation_inputs["ru"].setPlainText("Updated conclusion")

    assert _fill_masterlog_analysis(
        monkeypatch, session, selected, (None, None), 30.0,
        calcite=calcite, inspect_dialog=inspect_dialog,
    ) == []

    if calcite is not None:
        expected.calcite_percent = calcite
    if edit_russian:
        expected.lba_description = expected.lba_description_i18n["ru"] = "Updated LBA"
        expected.analysis_interpretation = expected.analysis_interpretation_i18n["ru"] = (
            "Updated conclusion"
        )
        language_revisions["ru"] += 1
    changed = calcite is not None or edit_russian
    assert controller.get(sample.sample_id) is sample
    assert controller.available() == (expected,)
    assert session.dirty is changed
    assert well.content_revision == content_revision + int(changed)
    assert well.language_revisions == language_revisions
    assert well.authored_field_revisions[field_id] == source_revision
    assert well.translation_statuses[field_id]["ru"].state is expected_state

    if calcite is not None:
        repository = PackageProjectRepository()
        path = tmp_path / "masterlog-analysis.geologpkg"
        repository.save(ProjectDocument(project=session.project), path)
        restored = repository.load(path).project.wells[well.well_id]
        assert restored.cuttings == [expected]
        assert restored.translation_statuses == well.translation_statuses
        assert restored.authored_field_source_languages[field_id] == "kk"


@pytest.mark.parametrize(
    ("source_language", "clear_russian"),
    [
        pytest.param(None, False, id="unchanged-unset"),
        pytest.param("ru", False, id="assign-legacy-russian"),
        pytest.param("kk", False, id="missing-kazakh"),
        pytest.param("ru", True, id="cleared-russian"),
    ],
)
def test_masterlog_analysis_assigns_only_explicit_legacy_conclusion_source(
    qapp,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    source_language: str | None,
    clear_russian: bool,
) -> None:
    session = _masterlog_geology_session()
    controller = CuttingsController(session)
    stored = (150.0005, 151.1235)
    localized = {"und": "Undetermined text", "en": "English version"}
    sample = controller.set_analysis(
        *stored, calcite_percent=30.0, analysis_interpretation_i18n=localized,
    )
    legacy = "Legacy conclusion\r\nwith\u00a0spacing"
    sample.analysis_interpretation = legacy
    well = session.current_well
    assert well is not None
    before = deepcopy(sample)
    language_revisions = dict(well.language_revisions)
    content_revision = well.content_revision
    field_id = f"cuttings/{sample.sample_id}/analysis_interpretation"
    session.dirty = False

    def inspect_dialog(dialog: SampleAnalysisDialog) -> None:
        assert dialog.interpretation_source_language_input.selected_language_code() is None
        russian = dialog.interpretation_inputs["ru"]
        assert russian.toPlainText() == "Legacy conclusion\nwith spacing"
        assert dialog.interpretation_inputs["en"].toPlainText() == localized["en"]
        if clear_russian:
            russian.clear()
        if source_language is not None:
            dialog.interpretation_source_language_input.set_language_code(source_language)

    warnings = _fill_masterlog_analysis(
        monkeypatch, session, stored, (None, None), 30.0,
        calcite=None, inspect_dialog=inspect_dialog,
    )

    assert controller.get(sample.sample_id) is sample
    if source_language != "ru" or clear_russian:
        assert warnings == (
            ["Выбранный язык оригинала не содержит авторского текста"]
            if source_language is not None
            else []
        )
        assert controller.available() == (before,)
        assert not session.dirty
        assert well.language_revisions == language_revisions
        assert well.content_revision == content_revision
        assert field_id not in well.authored_field_source_languages
        assert field_id not in well.authored_field_revisions
        assert field_id not in well.translation_statuses
        return

    assert warnings == []
    before.analysis_interpretation_i18n["ru"] = legacy
    assert controller.available() == (before,)
    assert session.dirty
    assert well.authored_field_source_languages[field_id] == "ru"
    assert well.translation_statuses[field_id]["ru"].state is TranslationState.REVIEWED
    assert well.translation_statuses[field_id]["en"].state is TranslationState.DRAFT
    assert well.translation_statuses[field_id]["kk"].state is TranslationState.MISSING

    repository = PackageProjectRepository()
    path = tmp_path / "legacy-conclusion.geologpkg"
    repository.save(ProjectDocument(project=session.project), path)
    restored = repository.load(path).project.wells[well.well_id]
    assert restored.cuttings == [before]
    assert restored.authored_field_source_languages == well.authored_field_source_languages
    assert restored.translation_statuses == well.translation_statuses


@pytest.mark.parametrize("field", ["lba_description", "analysis_interpretation"])
def test_masterlog_clears_only_selected_legacy_analysis_text(
    qapp, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, field: str
) -> None:
    session = _masterlog_geology_session()
    controller = CuttingsController(session)
    stored = (150.0005, 151.1235)
    sample = controller.set_analysis(
        *stored,
        calcite_percent=30.0,
        dolomite_percent=11.321,
        lba_description_i18n={"en": "English LBA", "und": "Undetermined LBA"},
        analysis_interpretation_i18n={"en": "English conclusion", "und": "Undetermined conclusion"},
        lba_description_source_language="en",
        analysis_interpretation_source_language="en",
    )
    sample.lba_description = "Legacy LBA"
    sample.analysis_interpretation = "Legacy conclusion"
    well = session.current_well
    assert well is not None
    expected = deepcopy(sample)
    setattr(expected, field, None)
    statuses = deepcopy(well.translation_statuses)
    field_revisions = dict(well.authored_field_revisions)
    language_revisions = dict(well.language_revisions)
    content_revision = well.content_revision
    session.dirty = False

    def clear(dialog: SampleAnalysisDialog) -> None:
        assert dialog.lba_description_inputs["ru"].text() == "Legacy LBA"
        assert dialog.interpretation_inputs["ru"].toPlainText() == "Legacy conclusion"
        if field == "lba_description":
            dialog.lba_description_inputs["ru"].clear()
        else:
            dialog.interpretation_inputs["ru"].clear()

    assert _fill_masterlog_analysis(
        monkeypatch, session, stored, (None, None), 30.0, calcite=None, inspect_dialog=clear
    ) == []

    assert controller.get(sample.sample_id) is sample
    assert controller.available() == (expected,)
    assert session.dirty
    assert well.translation_statuses == statuses
    assert well.authored_field_revisions == field_revisions
    assert well.language_revisions == language_revisions
    assert well.content_revision == content_revision + 1

    repository = PackageProjectRepository()
    path = tmp_path / "legacy-cleared-analysis.geologpkg"
    repository.save(ProjectDocument(project=session.project), path)
    restored = repository.load(path).project.wells[well.well_id]
    assert restored.cuttings == [expected]
    assert restored.translation_statuses == statuses


@pytest.mark.parametrize("clear", [False, True], ids=["no-op", "remove-last-legacy-text"])
def test_masterlog_edits_existing_standalone_legacy_only_analysis(
    qapp, monkeypatch: pytest.MonkeyPatch, clear: bool
) -> None:
    session = _masterlog_geology_session()
    controller = CuttingsController(session)
    stored = (150.0005, 151.1235)
    sample = controller.set_analysis(*stored, lba_description="Legacy LBA")
    well = session.current_well
    assert well is not None
    content_revision = well.content_revision
    language_revisions = dict(well.language_revisions)
    session.dirty = False

    def inspect(dialog: SampleAnalysisDialog) -> None:
        assert dialog.lba_description_input.text() == ""
        assert dialog.lba_description_inputs["ru"].text() == "Legacy LBA"
        if clear:
            dialog.lba_description_inputs["ru"].clear()

    assert _fill_masterlog_analysis(
        monkeypatch, session, stored, (None, None), -1.0, calcite=None, inspect_dialog=inspect
    ) == []

    assert controller.available() == (() if clear else (sample,))
    assert session.dirty is clear
    assert well.content_revision == content_revision + int(clear)
    assert well.language_revisions == language_revisions
