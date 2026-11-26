from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from functools import partial
from pathlib import Path

import numpy as np
import pytest
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QInputDialog,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
)

from geoworkbench.domain.models import CuttingsSample, Dataset, DatasetKind, DepthDomain
from geoworkbench.domain.translation_status import TranslationState
from geoworkbench.project.cuttings_controller import CuttingsController
from geoworkbench.project.lithotype_catalog_controller import LithotypeCatalogController
from geoworkbench.project.nct_controller import NctCalculationController
from geoworkbench.project.session import ProjectSession
from geoworkbench.project.stratigraphy_catalog_controller import (
    StratigraphyCatalogController,
)
from geoworkbench.project.stratigraphy_controller import StratigraphyController
from geoworkbench.project.translation_status_controller import TranslationStatusController
from geoworkbench.services.localization import AppLanguage
from geoworkbench.storage.package_project_repository import PackageProjectRepository
from geoworkbench.storage.project_codec import ProjectDocument
from geoworkbench.ui.main_window import MainWindow
from geoworkbench.ui.masterlog_preview_dialog import MasterlogPreviewDialog
from geoworkbench.ui.nct_dialog import NctCalculationDialog
from geoworkbench.ui.rock_description_dialog import RockDescriptionDialog
from geoworkbench.ui.sample_analysis_dialog import SampleAnalysisDialog
from geoworkbench.ui.stratigraphy_dialog import (
    StratigraphyCatalogDialog,
    StratigraphyDialog,
    StratigraphyIntervalDialog,
)
from geoworkbench.ui.unified_cuttings_sample_dialog import UnifiedCuttingsSampleDialog


def _session() -> ProjectSession:
    session = ProjectSession()
    dataset = Dataset(
        "adaptive-geology",
        "Well",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 200.0, 300.0, 400.0]),
    )
    dataset.upsert_curve(
        "DEXPC",
        np.array([1.0, 1.1, 1.2, 1.3]),
        unit="dimensionless",
    )
    session.add_dataset(dataset)
    return session


@pytest.mark.parametrize("entry", ["tablet-analysis", "masterlog-analysis", "masterlog-description"])
def test_geology_fill_prefers_exact_sample_over_earlier_close_interval(
    qapp, monkeypatch: pytest.MonkeyPatch, entry: str
) -> None:
    session = _session()
    controller = CuttingsController(session)
    neighbor = controller.create_full_sample(
        101.0, 101.0000005, {"sandstone": 100.0}, description="Neighbor", calcite_percent=20.0
    )
    top, bottom = 101.0000005, 101.000001
    exact = controller.create_full_sample(
        top, bottom, {"clay": 100.0}, description="Exact sample", calcite_percent=30.0
    )

    def edit_analysis(dialog: SampleAnalysisDialog) -> QDialog.DialogCode:
        assert (dialog.top_depth, dialog.bottom_depth) == (top, bottom)
        assert dialog.calcite_input.value() == 30.0
        dialog.calcite_input.setValue(40.0)
        return QDialog.DialogCode.Accepted

    def edit_description(dialog: QInputDialog) -> QDialog.DialogCode:
        assert dialog.textValue() == "Exact sample"
        dialog.setTextValue("Updated description")
        return QDialog.DialogCode.Accepted

    def unexpected_warning(*args: object) -> None:
        pytest.fail(f"Saving the exact interval raised a warning: {args[-1]}")

    monkeypatch.setattr(SampleAnalysisDialog, "exec", edit_analysis)
    monkeypatch.setattr(QInputDialog, "exec", edit_description)
    monkeypatch.setattr(QMessageBox, "warning", unexpected_warning)

    window = QMainWindow()
    try:
        window.session = session
        window.cuttings_controller = controller
        window.language = AppLanguage.EN
        window.description_button = QPushButton("Cuttings description", window)
        window._t = lambda key, **_values: key
        window._refresh_cuttings_after_edit = lambda: None
        if entry == "tablet-analysis":
            MainWindow._create_analysis_interval_from_tablet(window, top, bottom)
        elif entry == "masterlog-analysis":
            MasterlogPreviewDialog._fill_analysis(window, top, bottom)
        else:
            MasterlogPreviewDialog._fill_cuttings_description(window, top, bottom)
    finally:
        window.close()

    assert tuple(controller.available()) == (neighbor, exact)
    assert (neighbor.top_depth, neighbor.bottom_depth) == (101.0, 101.0000005)
    assert (neighbor.description, neighbor.calcite_percent) == ("Neighbor", 20.0)
    assert (exact.top_depth, exact.bottom_depth) == (top, bottom)
    if entry == "masterlog-description":
        assert (exact.description, exact.calcite_percent) == ("Exact sample", 30.0)
        assert exact.description_i18n == {"en": "Updated description"}
    else:
        assert (exact.description, exact.calcite_percent) == ("Exact sample", 40.0)


def _fill_tablet_analysis(
    monkeypatch: pytest.MonkeyPatch,
    controller: CuttingsController,
    selected: tuple[float, float],
    edits: tuple[tuple[float | None, float | None] | None, ...],
    initial_calcite: float,
) -> list[tuple[str, tuple[CuttingsSample, ...], bool]]:
    submissions = iter(edits)
    warnings: list[tuple[str, tuple[CuttingsSample, ...], bool]] = []

    def fill(dialog: SampleAnalysisDialog) -> QDialog.DialogCode:
        try:
            edited = next(submissions)
        except StopIteration:
            return QDialog.DialogCode.Rejected
        expected_calcite = 42.0 if warnings else initial_calcite
        assert dialog.calcite_input.value() == expected_calcite
        if edited is not None:
            top, bottom = edited
            if top is not None:
                dialog.top_input.setValue(top)
            if bottom is not None:
                dialog.bottom_input.setValue(bottom)
        dialog.calcite_input.setValue(42.0)
        buttons = dialog.findChild(QDialogButtonBox)
        assert buttons is not None
        ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        assert ok is not None
        ok.click()
        assert dialog.result() == QDialog.DialogCode.Accepted
        return QDialog.DialogCode.Accepted

    def warn(_parent: object, _title: str, message: str) -> None:
        warnings.append((message, deepcopy(controller.available()), controller.session.dirty))

    monkeypatch.setattr(SampleAnalysisDialog, "exec", fill)
    monkeypatch.setattr(QMessageBox, "warning", warn)
    window = QMainWindow()
    try:
        window.session = controller.session
        window.cuttings_controller = controller
        window.language = AppLanguage.EN
        window._t = lambda key, **_values: key
        window._refresh_cuttings_after_edit = lambda: None
        MainWindow._create_analysis_interval_from_tablet(window, *selected)
    finally:
        window.close()
    assert not list(submissions)
    return warnings


def test_tablet_analysis_warns_before_opening_for_ambiguous_interval(
    qapp, monkeypatch: pytest.MonkeyPatch
) -> None:
    controller = CuttingsController(_session())
    controller.set_analysis(150.0, 151.0, calcite_percent=10.0, absolute_tolerance=0.0)
    controller.set_analysis(150.002, 151.002, calcite_percent=20.0, absolute_tolerance=0.0)
    before = deepcopy(controller.available())
    controller.session.dirty = False
    warnings: list[str] = []

    def unexpected_dialog(_dialog: SampleAnalysisDialog) -> None:
        pytest.fail("An ambiguous interval opened the analysis dialog")

    def warn(_parent: object, _title: str, message: str) -> None:
        warnings.append(message)

    monkeypatch.setattr(SampleAnalysisDialog, "exec", unexpected_dialog)
    monkeypatch.setattr(QMessageBox, "warning", warn)
    window = QMainWindow()
    try:
        window.session = controller.session
        window.cuttings_controller = controller
        window.language = AppLanguage.EN
        window._t = lambda key, **_values: key
        MainWindow._create_analysis_interval_from_tablet(window, 150.001, 151.001)
    finally:
        window.close()

    assert warnings == ["cuttings.ambiguous_interval"]
    assert controller.available() == before
    assert not controller.session.dirty


@pytest.mark.parametrize("occupied", [False, True], ids=["free-move", "occupied-then-retry"])
def test_tablet_filling_analysis_moves_the_prefilled_sample(
    qapp, monkeypatch: pytest.MonkeyPatch, occupied: bool
) -> None:
    session = _session()
    controller = CuttingsController(session)
    selected = (150.0004, 151.1234)
    destination = (152.0, 153.0)
    sample = controller.create_full_sample(
        *selected, {"sandstone": 100.0}, calcite_percent=30.0, description="Existing description"
    )
    neighbor = controller.set_analysis(*destination, calcite_percent=12.5) if occupied else None
    before = deepcopy(controller.available())
    session.dirty = False
    corrected = (154.0, 155.0)
    edits = (destination, corrected) if occupied else (destination,)

    warnings = _fill_tablet_analysis(monkeypatch, controller, selected, edits, 30.0)

    if occupied:
        ((message, samples, dirty),) = warnings
        assert "уже существует другая проба" in message
        assert samples == before
        assert not dirty
        assert neighbor == before[1]
        assert controller.available() == (neighbor, sample)
    else:
        assert warnings == []
        assert controller.available() == (sample,)
    assert controller.get(sample.sample_id) is sample
    assert (sample.top_depth, sample.bottom_depth) == edits[-1]
    assert sample.components == before[0].components
    assert sample.description == "Existing description"
    assert sample.calcite_percent == 42.0
    assert session.dirty


@pytest.mark.parametrize("tight_match", [False, True], ids=["broad-prefill", "tight-priority"])
def test_tablet_filling_analysis_preserves_prefilled_data_for_near_selection(
    qapp, monkeypatch: pytest.MonkeyPatch, tight_match: bool
) -> None:
    controller = CuttingsController(_session())
    stored = (150.0008, 151.1238)
    selected = (150.0008005, 151.1238005) if tight_match else (150.0004, 151.1234)
    if tight_match:
        controller.set_analysis(150.0001, 151.1231, calcite_percent=22.0)
    earlier_samples = deepcopy(controller.available())
    sample = controller.set_analysis(
        *stored,
        calcite_percent=12.5,
        dolomite_percent=11.321,
        lba_color="Tan",
        lba_description_i18n={"en": "Recorded LBA"},
        analysis_interpretation_i18n={"ru": "Recorded conclusion"},
        absolute_tolerance=0.0,
    )
    expected = deepcopy(sample)
    expected.calcite_percent = 42.0

    assert _fill_tablet_analysis(monkeypatch, controller, selected, (None,), 12.5) == []

    assert controller.get(sample.sample_id) is sample
    assert controller.available() == (*earlier_samples, expected)


def test_tablet_filling_new_analysis_matches_edited_bounds_exactly(
    qapp, monkeypatch: pytest.MonkeyPatch
) -> None:
    controller = CuttingsController(_session())
    selected = (150.0, 151.0)
    edited = (150.499, 151.0)
    neighbor = controller.set_analysis(150.5, 151.0, calcite_percent=12.5)
    neighbor_before = deepcopy(neighbor)

    assert _fill_tablet_analysis(monkeypatch, controller, selected, (edited,), -1.0) == []

    saved, unchanged = controller.available()
    assert unchanged is neighbor
    assert unchanged == neighbor_before
    assert (saved.top_depth, saved.bottom_depth) == edited
    assert saved.calcite_percent == 42.0


@pytest.mark.parametrize(
    ("selected", "edited_top"),
    [
        pytest.param((170.0001, 170.0004), None, id="unchanged-submillimeter-range"),
        pytest.param((160.0004, 161.1234), 160.125, id="edit-one-boundary"),
    ],
)
def test_tablet_filling_new_analysis_preserves_original_depth_precision(
    qapp, monkeypatch: pytest.MonkeyPatch, selected: tuple[float, float], edited_top: float | None
) -> None:
    controller = CuttingsController(_session())
    edited = None if edited_top is None else (edited_top, None)

    assert _fill_tablet_analysis(monkeypatch, controller, selected, (edited,), -1.0) == []

    (saved,) = controller.available()
    expected_top = selected[0] if edited_top is None else edited_top
    assert (saved.top_depth, saved.bottom_depth) == (expected_top, selected[1])
    assert saved.calcite_percent == 42.0


@pytest.mark.parametrize(
    ("edited_top", "neighbor_top", "reuse_neighbor"),
    [
        pytest.param(150.499, 150.5, False, id="edited-near-after-retry"),
        pytest.param(150.5, 150.5, True, id="edited-exact"),
        pytest.param(None, 150.001, True, id="untouched-near"),
    ],
)
def test_tablet_description_matches_confirmed_depths(
    qapp,
    monkeypatch: pytest.MonkeyPatch,
    edited_top: float | None,
    neighbor_top: float,
    reuse_neighbor: bool,
) -> None:
    session = _session()
    controller = CuttingsController(session)
    selected = (150.0004, 151.1234)
    neighbor = controller.create_full_sample(
        neighbor_top,
        selected[1],
        {"sandstone": 100.0},
        calcite_percent=12.5,
        description_i18n={"ru": "Исходное описание", "en": "Reviewed description"},
        description_source_language="ru",
        analysis_interpretation_i18n={"ru": "Исходное заключение", "en": "Reviewed conclusion"},
        analysis_interpretation_source_language="ru",
    )
    well = session.current_well
    assert well is not None
    description_id = f"cuttings/{neighbor.sample_id}/description"
    conclusion_id = f"cuttings/{neighbor.sample_id}/analysis_interpretation"
    tracking = TranslationStatusController(session)
    tracking.review_current(field_id=description_id, language="en")
    tracking.review_current(field_id=conclusion_id, language="en")
    neighbor_before = deepcopy(neighbor)
    statuses_before = deepcopy(well.translation_statuses)
    revisions_before = dict(well.authored_field_revisions)
    sources_before = dict(well.authored_field_source_languages)
    session.dirty = False
    warnings: list[str] = []
    description = "New tablet description"

    def fill(dialog: RockDescriptionDialog) -> QDialog.DialogCode:
        if warnings:
            assert dialog.editor.editor.toPlainText() == description
            assert not dialog.description_word_wrap
            assert dialog.bottom_depth == selected[1]
        else:
            assert (dialog.top_depth, dialog.bottom_depth) == selected
            assert dialog.description_html is None
            dialog.editor.editor.setPlainText(description)
            dialog.editor.set_word_wrap(False)
        if not reuse_neighbor and not warnings:
            dialog.top_input.setValue(99.999)
        elif edited_top is not None:
            dialog.top_input.setValue(edited_top)
        buttons = dialog.findChild(QDialogButtonBox)
        assert buttons is not None
        buttons.button(QDialogButtonBox.StandardButton.Ok).click()
        assert dialog.result() == QDialog.DialogCode.Accepted
        return QDialog.DialogCode.Accepted

    def warn(_parent: object, _title: str, message: str) -> None:
        assert not reuse_neighbor and not warnings, message
        assert "выходит за диапазон" in message
        assert controller.available() == (neighbor_before,)
        assert well.translation_statuses == statuses_before
        assert not session.dirty
        warnings.append(message)

    monkeypatch.setattr(RockDescriptionDialog, "exec", fill)
    monkeypatch.setattr(QMessageBox, "warning", warn)
    window = QMainWindow()
    try:
        window.session = session
        window.cuttings_controller = controller
        window.language = AppLanguage.EN
        window._t = lambda key, **_values: key
        window._refresh_cuttings_after_edit = lambda: None
        MainWindow._create_rock_description_from_tablet(window, *selected)
    finally:
        window.close()

    if reuse_neighbor:
        (saved,) = controller.available()
        assert saved is neighbor
        assert (saved.top_depth, saved.bottom_depth) == (
            neighbor_before.top_depth, neighbor_before.bottom_depth
        )
        assert saved.components == neighbor_before.components
        assert saved.calcite_percent == neighbor_before.calcite_percent
        assert saved.description_i18n["ru"] == neighbor_before.description_i18n["ru"]
        assert saved.analysis_interpretation_i18n == neighbor_before.analysis_interpretation_i18n
        assert well.translation_statuses[description_id]["en"].state is TranslationState.DRAFT
        assert well.translation_statuses[conclusion_id] == statuses_before[conclusion_id]
        assert well.authored_field_revisions == revisions_before
        assert well.authored_field_source_languages == sources_before
    else:
        assert len(warnings) == 1
        saved, unchanged = controller.available()
        assert unchanged is neighbor
        assert unchanged == neighbor_before
        assert well.translation_statuses == statuses_before
        assert well.authored_field_revisions == revisions_before
        assert well.authored_field_source_languages == sources_before
        assert saved.sample_id != neighbor.sample_id
        expected_top = selected[0] if edited_top is None else edited_top
        assert (saved.top_depth, saved.bottom_depth) == (expected_top, selected[1])
    assert description in saved.description_i18n["en"]
    assert not saved.description_word_wrap


def test_tablet_description_retries_ambiguous_selection_at_exact_bounds(
    qapp, monkeypatch: pytest.MonkeyPatch
) -> None:
    controller = CuttingsController(_session())
    first = controller.set_analysis(150.0, 151.0, calcite_percent=10.0, absolute_tolerance=0.0)
    second = controller.set_analysis(150.002, 151.002, calcite_percent=20.0, absolute_tolerance=0.0)
    before = deepcopy(controller.available())
    controller.session.dirty = False
    warnings: list[str] = []
    dialogs: list[RockDescriptionDialog] = []

    def fill(dialog: RockDescriptionDialog) -> QDialog.DialogCode:
        assert len(dialogs) < 2
        if dialogs:
            assert dialog is dialogs[0]
            assert dialog.editor.editor.toPlainText() == "Selected sample description"
            dialog.top_input.setValue(second.top_depth)
            dialog.bottom_input.setValue(second.bottom_depth)
        else:
            dialog.editor.editor.setPlainText("Selected sample description")
        dialogs.append(dialog)
        buttons = dialog.findChild(QDialogButtonBox)
        assert buttons is not None
        buttons.button(QDialogButtonBox.StandardButton.Ok).click()
        assert dialog.result() == QDialog.DialogCode.Accepted
        return QDialog.DialogCode.Accepted

    def warn(_parent: object, _title: str, message: str) -> None:
        assert controller.available() == before
        assert not controller.session.dirty
        warnings.append(message)

    monkeypatch.setattr(RockDescriptionDialog, "exec", fill)
    monkeypatch.setattr(QMessageBox, "warning", warn)
    window = QMainWindow()
    try:
        window.session = controller.session
        window.cuttings_controller = controller
        window.language = AppLanguage.EN
        window._t = lambda key, **_values: key
        window._refresh_cuttings_after_edit = lambda: None
        MainWindow._create_rock_description_from_tablet(window, 150.001, 151.001)
    finally:
        window.close()

    assert warnings == ["cuttings.ambiguous_interval"]
    assert len(dialogs) == 2
    assert controller.available() == (first, second)
    assert first == before[0]
    assert (second.top_depth, second.bottom_depth) == (150.002, 151.002)
    assert second.calcite_percent == 20.0
    assert "Selected sample description" in second.description_i18n["en"]


def _save_tablet_description_edit(
    monkeypatch: pytest.MonkeyPatch,
    controller: CuttingsController,
    sample_id: str,
    language: AppLanguage,
    edit: Callable[[RockDescriptionDialog], None],
    package: Path,
) -> None:
    def accept(dialog: RockDescriptionDialog) -> QDialog.DialogCode:
        edit(dialog)
        buttons = dialog.findChild(QDialogButtonBox)
        assert buttons is not None
        buttons.button(QDialogButtonBox.StandardButton.Ok).click()
        assert dialog.result() == QDialog.DialogCode.Accepted
        return QDialog.DialogCode.Accepted

    def warn(_parent: object, _title: str, message: str) -> None:
        pytest.fail(f"Editing the rock description raised a warning: {message}")

    monkeypatch.setattr(RockDescriptionDialog, "exec", accept)
    monkeypatch.setattr(QMessageBox, "warning", warn)
    window = QMainWindow()
    try:
        window.session = controller.session
        window.cuttings_controller = controller
        window.language = language
        window._t = lambda key, **_values: key
        window._refresh_cuttings_after_edit = lambda: None
        MainWindow._edit_rock_description_from_tablet(window, sample_id)
    finally:
        window.close()

    well = controller.session.current_well
    assert well is not None
    repository = PackageProjectRepository()
    repository.save(ProjectDocument(project=controller.session.project), package)
    restored = repository.load(package).project.wells[well.well_id]
    assert restored.cuttings == well.cuttings
    assert restored.translation_statuses == well.translation_statuses
    assert restored.authored_field_revisions == well.authored_field_revisions
    assert restored.authored_field_source_languages == well.authored_field_source_languages
    assert restored.language_revisions == well.language_revisions


def test_tablet_description_depth_edit_preserves_fallback_language(
    qapp, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    session = _session()
    controller = CuttingsController(session)
    sample = controller.create_full_sample(
        150.0004,
        160.0004,
        {"sandstone": 100.0},
        calcite_percent=22.543,
        description_i18n={"ru": "<p><b>Исходное описание</b></p>", "en": "Reviewed description"},
        description_source_language="ru",
        analysis_interpretation_i18n={"ru": "Заключение", "en": "Reviewed conclusion"},
        analysis_interpretation_source_language="ru",
    )
    field_ids = [
        f"cuttings/{sample.sample_id}/{field}"
        for field in ("description", "analysis_interpretation")
    ]
    reviewer = TranslationStatusController(session)
    for field_id in field_ids:
        reviewer.review_current(field_id=field_id, language="en")
    well = session.current_well
    assert well is not None
    language_revisions = dict(well.language_revisions)
    revisions = dict(well.authored_field_revisions)
    expected = deepcopy(sample)
    expected.top_depth = 150.125
    session.dirty = False

    def move(dialog: RockDescriptionDialog) -> None:
        assert dialog.editor.editor.toPlainText() == "Исходное описание"
        dialog.top_input.setValue(expected.top_depth)

    _save_tablet_description_edit(
        monkeypatch, controller, sample.sample_id, AppLanguage.KK, move, tmp_path / "move.geologpkg"
    )

    assert controller.get(sample.sample_id) is sample
    assert sample == expected
    assert well.language_revisions == language_revisions
    assert session.dirty
    for field_id in field_ids:
        assert well.authored_field_revisions[field_id] == revisions[field_id]
        assert well.translation_statuses[field_id]["kk"].state is TranslationState.MISSING
        assert well.translation_statuses[field_id]["en"].state is TranslationState.STALE


@pytest.mark.parametrize("toggle_wrap", [False, True], ids=["tracked-noop", "legacy-wrap"])
def test_tablet_description_unchanged_text_keeps_exact_saved_content(
    qapp, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, toggle_wrap: bool
) -> None:
    session = _session()
    controller = CuttingsController(session)
    if toggle_wrap:
        sample = controller.set_description(150, 160, "Legacy plain description")
        language = AppLanguage.RU
    else:
        sample = controller.set_description(
            150, 160, "Authored plain description", language="en", source_language="en"
        )
        language = AppLanguage.EN
    well = session.current_well
    assert well is not None
    expected = deepcopy(sample)
    language_revisions = dict(well.language_revisions)
    content_revision = well.content_revision
    statuses = deepcopy(well.translation_statuses)
    session.dirty = False

    def edit(dialog: RockDescriptionDialog) -> None:
        if toggle_wrap:
            dialog.editor.set_word_wrap(False)
            expected.description_word_wrap = False

    _save_tablet_description_edit(
        monkeypatch, controller, sample.sample_id, language, edit, tmp_path / "text.geologpkg"
    )

    assert sample == expected
    assert well.language_revisions == language_revisions
    assert well.translation_statuses == statuses
    assert session.dirty is toggle_wrap
    assert well.content_revision == content_revision + int(toggle_wrap)


@pytest.mark.parametrize("clear", [False, True], ids=["format-only", "clear"])
def test_tablet_description_edit_writes_only_active_language(
    qapp, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, clear: bool
) -> None:
    session = _session()
    controller = CuttingsController(session)
    sample = controller.set_description(
        150, 160, "Исходное описание", language="ru", source_language="ru"
    )
    controller.update_description(
        sample.sample_id,
        top_depth=150,
        bottom_depth=160,
        description="Reviewed description",
        language="en",
    )
    field_id = f"cuttings/{sample.sample_id}/description"
    TranslationStatusController(session).review_current(field_id=field_id, language="en")
    well = session.current_well
    assert well is not None
    revision = well.authored_field_revisions[field_id]

    def edit(dialog: RockDescriptionDialog) -> None:
        text = dialog.editor.editor
        if clear:
            text.clear()
        else:
            text.selectAll()
            text.setFontItalic(True)
            assert text.toPlainText() == "Reviewed description"

    _save_tablet_description_edit(
        monkeypatch, controller, sample.sample_id, AppLanguage.EN, edit, tmp_path / "write.geologpkg"
    )

    assert sample.description == sample.description_i18n["ru"] == "Исходное описание"
    assert well.authored_field_revisions[field_id] == revision
    if clear:
        assert "en" not in sample.description_i18n
        assert well.translation_statuses[field_id]["en"].state is TranslationState.MISSING
    else:
        assert "font-style:italic" in sample.description_i18n["en"]
        assert "Reviewed description" in sample.description_i18n["en"]
        assert well.translation_statuses[field_id]["en"].state is TranslationState.DRAFT


def _create_tablet_cuttings_sample(
    controller: CuttingsController, selected: tuple[float, float]
) -> None:
    window = QMainWindow()
    try:
        window.session = controller.session
        window.cuttings_controller = controller
        window.lithotype_catalog_controller = LithotypeCatalogController(controller.session)
        window.language = AppLanguage.EN
        window._t = lambda key, **_values: key
        window._refresh_cuttings_after_edit = lambda: None
        window._edit_cuttings_sample_from_tablet = partial(
            MainWindow._edit_cuttings_sample_from_tablet, window
        )
        MainWindow._create_cuttings_sample_from_tablet(window, *selected)
    finally:
        window.close()


def _select_sandstone_for_tablet_cuttings(dialog: UnifiedCuttingsSampleDialog) -> None:
    sandstone = dialog.rock_inputs[0].findData("sandstone")
    assert sandstone >= 0
    dialog.rock_inputs[0].setCurrentIndex(sandstone)
    dialog.percent_inputs[0].setValue(100.0)


def _accept_tablet_cuttings(dialog: UnifiedCuttingsSampleDialog) -> QDialog.DialogCode:
    buttons = dialog.findChild(QDialogButtonBox, "cuttings-dialog-buttons")
    assert buttons is not None
    buttons.button(QDialogButtonBox.StandardButton.Ok).click()
    assert dialog.result() == QDialog.DialogCode.Accepted
    return QDialog.DialogCode.Accepted


@pytest.mark.parametrize(
    ("localized_ru", "edit_ru_lba"),
    [
        pytest.param(False, False, id="legacy-description-only"),
        pytest.param(True, False, id="preserve-distinct-legacy-texts"),
        pytest.param(True, True, id="edit-russian-lba-only"),
    ],
)
def test_tablet_filling_composition_loads_exact_sample_and_retains_its_analysis_and_description(
    qapp, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, localized_ru: bool, edit_ru_lba: bool
) -> None:
    session = _session()
    controller = CuttingsController(session)
    top, bottom = selected = (150.0004, 151.1234)
    neighbor = controller.set_analysis(150.0, 151.123, calcite_percent=12.5)
    sample = controller.set_analysis(
        top,
        bottom,
        absolute_tolerance=0.0,
        calcite_percent=32.543,
        lba_type_id="legacy-LBA",
        lba_odour="Faint",
        analysis_interpretation_i18n={"en": "Conclusion", "ru": "Заключение"},
        analysis_interpretation_source_language="en",
    )
    legacy_description = "<p><b>Legacy rock description</b></p>"
    assert controller.set_description(
        top, bottom, legacy_description, description_word_wrap=False
    ) is sample
    description_on_screen = "Legacy rock description"
    if localized_ru:
        # Older packages can store distinct legacy and localized Russian texts.
        sample.lba_description = "Legacy LBA description"
        sample.lba_description_i18n["ru"] = "Localized LBA description"
        sample.analysis_interpretation = "Legacy conclusion"
        description_on_screen = "Localized rock description"
        sample.description_i18n["ru"] = f"<p>{description_on_screen}</p>"
    field_id = f"cuttings/{sample.sample_id}/analysis_interpretation"
    TranslationStatusController(session).review_current(field_id=field_id, language="ru")
    well = session.current_well
    assert well is not None
    reviewed = well.translation_statuses[field_id]["ru"]
    before = deepcopy(sample)
    neighbor_before = deepcopy(neighbor)

    def fill(dialog: UnifiedCuttingsSampleDialog) -> QDialog.DialogCode:
        assert (dialog.top_depth, dialog.bottom_depth) == selected
        assert dialog.calcite_input.percentage() == before.calcite_percent
        assert dialog.description_editors["ru"].editor.toPlainText() == description_on_screen
        if edit_ru_lba:
            assert dialog.lba_description_inputs["ru"].text() == "Localized LBA description"
            dialog.lba_description_inputs["ru"].setText("Edited Russian LBA")
        assert dialog.findChild(QPushButton, "cuttings-delete-button") is None
        assert dialog.components() == {}
        _select_sandstone_for_tablet_cuttings(dialog)
        return _accept_tablet_cuttings(dialog)

    def warn(_parent: object, _title: str, message: str) -> None:
        pytest.fail(f"Filling the saved sample raised a warning: {message}")

    monkeypatch.setattr(UnifiedCuttingsSampleDialog, "exec", fill)
    monkeypatch.setattr(QMessageBox, "warning", warn)
    _create_tablet_cuttings_sample(controller, selected)

    assert controller.available() == (neighbor, sample)
    assert controller.get(before.sample_id) is sample
    assert neighbor == neighbor_before
    assert [(rock.lithotype_id, rock.percentage) for rock in sample.components] == [
        ("sandstone", 100.0)
    ]
    before.components = deepcopy(sample.components)
    if edit_ru_lba:
        before.lba_description = before.lba_description_i18n["ru"] = "Edited Russian LBA"
    assert sample == before

    repository = PackageProjectRepository()
    path = tmp_path / "filled-cuttings.geologpkg"
    repository.save(ProjectDocument(project=session.project), path)
    restored_well = repository.load(path).project.wells[well.well_id]
    assert restored_well.cuttings == [neighbor, sample]
    assert restored_well.translation_statuses[field_id]["ru"] == reviewed


@pytest.mark.parametrize("ambiguous", [False, True], ids=["edited-onto-sample", "legacy-duplicates"])
def test_tablet_filling_new_composition_retries_exact_collision_with_entered_values(
    qapp, monkeypatch: pytest.MonkeyPatch, ambiguous: bool
) -> None:
    session = _session()
    controller = CuttingsController(session)
    occupied_top = 150.001
    selected = (occupied_top if ambiguous else 150.0004, 151.1234)
    free_top = 150.0 if ambiguous else selected[0]
    neighbor = controller.set_analysis(occupied_top, selected[1], calcite_percent=12.5)
    if ambiguous:
        well = session.current_well
        assert well is not None
        legacy_duplicate = deepcopy(neighbor)
        legacy_duplicate.sample_id = "legacy-duplicate"
        well.cuttings.append(legacy_duplicate)
    before = deepcopy(controller.available())
    session.dirty = False
    warnings: list[str] = []
    dialogs: list[UnifiedCuttingsSampleDialog] = []

    def fill(dialog: UnifiedCuttingsSampleDialog) -> QDialog.DialogCode:
        dialogs.append(dialog)
        if len(dialogs) == 1:
            assert (dialog.top_depth, dialog.bottom_depth) == selected
            assert dialog.calcite_input.percentage() is None
            _select_sandstone_for_tablet_cuttings(dialog)
            dialog.calcite_input.setValue(42.0)
            dialog.top_input.setValue(occupied_top)
        else:
            assert len(dialogs) == 2 and dialog is dialogs[0]
            assert dialog.components() == {"sandstone": 100.0}
            assert dialog.calcite_input.percentage() == 42.0
            dialog.top_input.setValue(free_top)
        return _accept_tablet_cuttings(dialog)

    def warn(_parent: object, _title: str, message: str) -> None:
        warnings.append(message)
        assert controller.available() == before
        assert not session.dirty

    monkeypatch.setattr(UnifiedCuttingsSampleDialog, "exec", fill)
    monkeypatch.setattr(QMessageBox, "warning", warn)
    _create_tablet_cuttings_sample(controller, selected)

    (message,) = warnings
    assert "уже существует другая проба" in message
    saved, *unchanged = controller.available()
    assert tuple(unchanged) == before
    assert controller.get(neighbor.sample_id) is neighbor
    assert (saved.top_depth, saved.bottom_depth) == (free_top, selected[1])
    assert saved.calcite_percent == 42.0
    assert [(rock.lithotype_id, rock.percentage) for rock in saved.components] == [
        ("sandstone", 100.0)
    ]
    assert session.dirty


def _assert_footer_visible(dialog, qapp) -> None:
    dialog.show()
    qapp.processEvents()

    screen = dialog.screen()
    assert screen is not None
    available = screen.availableGeometry()
    geometry = dialog.geometry()
    assert geometry.left() >= available.left()
    assert geometry.top() >= available.top()
    assert geometry.right() <= available.right()
    assert geometry.bottom() <= available.bottom()

    button_boxes = dialog.findChildren(QDialogButtonBox)
    assert button_boxes
    footer = button_boxes[-1]
    assert footer.isVisibleTo(dialog)
    assert dialog.contentsRect().contains(footer.geometry().center())

    dialog.close()


def test_geology_editors_keep_action_footers_inside_work_area(qapp) -> None:
    session = _session()
    stratigraphy_controller = StratigraphyController(session)
    catalog_controller = StratigraphyCatalogController(session)

    dialogs = (
        SampleAnalysisDialog(100.0, 120.0, language=AppLanguage.RU),
        RockDescriptionDialog(100.0, 120.0, language=AppLanguage.RU),
        StratigraphyIntervalDialog(
            100.0,
            120.0,
            language=AppLanguage.RU,
            catalog_controller=catalog_controller,
        ),
        StratigraphyDialog(
            stratigraphy_controller,
            language=AppLanguage.RU,
            catalog_controller=catalog_controller,
        ),
        StratigraphyCatalogDialog(
            catalog_controller,
            language=AppLanguage.RU,
        ),
        NctCalculationDialog(
            NctCalculationController(session),
            100.0,
            400.0,
            language=AppLanguage.RU,
        ),
    )

    for dialog in dialogs:
        _assert_footer_visible(dialog, qapp)


def test_stratigraphy_long_editors_scroll_separately_from_footer(qapp) -> None:
    session = _session()
    controller = StratigraphyController(session)
    catalog_controller = StratigraphyCatalogController(session)

    dialog = StratigraphyDialog(
        controller,
        language=AppLanguage.EN,
        catalog_controller=catalog_controller,
    )
    catalog = StratigraphyCatalogDialog(
        catalog_controller,
        language=AppLanguage.EN,
    )

    editor_scroll = dialog.findChild(QScrollArea, "stratigraphy-editor-scroll")
    assert editor_scroll is not None
    assert editor_scroll.widgetResizable()
    assert dialog.findChildren(QDialogButtonBox)[-1].parentWidget() is dialog

    catalog_scrolls = catalog.findChildren(QScrollArea)
    assert catalog_scrolls
    assert catalog_scrolls[0].widgetResizable()
    assert catalog.findChildren(QDialogButtonBox)[-1].parentWidget() is catalog

    dialog.close()
    catalog.close()


def _sample_editor(
    editor: str,
    session: ProjectSession,
    top: float,
    bottom: float,
    sample: CuttingsSample | None = None,
) -> UnifiedCuttingsSampleDialog | SampleAnalysisDialog | RockDescriptionDialog:
    if editor == "unified":
        return UnifiedCuttingsSampleDialog(
            top,
            bottom,
            LithotypeCatalogController(session).available(),
            language=AppLanguage.EN,
            sample=sample,
        )
    if editor == "analysis":
        return SampleAnalysisDialog(top, bottom, language=AppLanguage.EN, sample=sample)
    return RockDescriptionDialog(top, bottom, language=AppLanguage.EN, sample=sample)


@pytest.mark.parametrize("editor", ["unified", "analysis", "description"])
@pytest.mark.parametrize(
    ("edited_top", "edited_bottom"),
    [
        pytest.param(None, None, id="unchanged"),
        pytest.param(100.999, None, id="edit-top"),
        pytest.param(None, 101.001, id="edit-bottom"),
    ],
)
def test_existing_sample_editor_saves_precise_interval(
    qapp, tmp_path: Path, editor: str, edited_top: float | None, edited_bottom: float | None
) -> None:
    top, bottom = 101.0001, 101.0004
    session = _session()
    controller = CuttingsController(session)
    sample = controller.create_full_sample(
        top,
        bottom,
        {"sandstone": 100.0},
        calcite_percent=30.0,
        description_i18n={"en": "Rock description"},
        analysis_interpretation_i18n={"ru": "Заключение", "en": "Conclusion"},
        analysis_interpretation_source_language="ru",
    )
    field_id = f"cuttings/{sample.sample_id}/analysis_interpretation"
    TranslationStatusController(session).review_current(field_id=field_id, language="en")
    well = session.current_well
    assert well is not None
    reviewed = well.translation_statuses[field_id]["en"]

    dialog = _sample_editor(editor, session, top, bottom, sample)
    try:
        # The interval is shorter than the resolution of the on-screen inputs.
        assert dialog.top_input.value() == dialog.bottom_input.value() == 101.0
        if edited_top is not None:
            dialog.top_input.setValue(edited_top)
        if edited_bottom is not None:
            dialog.bottom_input.setValue(edited_bottom)

        footer = dialog.findChild(QDialogButtonBox)
        assert footer is not None
        footer.button(QDialogButtonBox.StandardButton.Ok).click()
        assert dialog.result() == QDialog.DialogCode.Accepted

        if isinstance(dialog, UnifiedCuttingsSampleDialog):
            saved = controller.update_full_sample(
                sample.sample_id,
                top_depth=dialog.top_depth,
                bottom_depth=dialog.bottom_depth,
                components=dialog.components(),
                content_language=AppLanguage.EN.value,
                **dialog.values(),
            )
        elif isinstance(dialog, SampleAnalysisDialog):
            saved = controller.update_analysis(
                sample.sample_id,
                top_depth=dialog.top_depth,
                bottom_depth=dialog.bottom_depth,
                content_language=AppLanguage.EN.value,
                **dialog.values(),
            )
        else:
            saved = controller.update_description(
                sample.sample_id,
                top_depth=dialog.top_depth,
                bottom_depth=dialog.bottom_depth,
                description=dialog.description_html,
                description_word_wrap=dialog.description_word_wrap,
                language=AppLanguage.EN,
            )
    finally:
        dialog.close()

    expected = (
        edited_top if edited_top is not None else top,
        edited_bottom if edited_bottom is not None else bottom,
    )
    assert saved is sample
    assert (saved.top_depth, saved.bottom_depth) == expected
    repository = PackageProjectRepository()
    path = tmp_path / "precise-interval.geologpkg"
    repository.save(ProjectDocument(project=session.project), path)
    restored_well = repository.load(path).project.wells[well.well_id]
    restored = restored_well.cuttings[0]
    assert restored.sample_id == sample.sample_id
    assert (restored.top_depth, restored.bottom_depth) == expected
    status = restored_well.translation_statuses[field_id]["en"]
    if edited_top is None and edited_bottom is None:
        assert status == reviewed
    else:
        assert status.state is TranslationState.STALE


@pytest.mark.parametrize("editor", ["unified", "analysis", "description"])
def test_new_sample_editor_uses_millimeter_input_precision(qapp, editor: str) -> None:
    dialog = _sample_editor(editor, _session(), 101.1234, 102.4567)
    try:
        assert (dialog.top_depth, dialog.bottom_depth) == (101.123, 102.457)
        dialog.top_input.setValue(101.1256)
        assert (dialog.top_depth, dialog.bottom_depth) == (101.126, 102.457)
    finally:
        dialog.close()


def test_analysis_save_on_existing_sample_uses_authoritative_interval(qapp) -> None:
    session = _session()
    controller = CuttingsController(session)
    sample = controller.set_analysis(101.0001, 101.0004, calcite_percent=30.0)
    session.dirty = False
    dialog = SampleAnalysisDialog(
        101.0001005, 101.0003995, language=AppLanguage.EN, sample=sample
    )
    try:
        saved = controller.set_analysis(dialog.top_depth, dialog.bottom_depth, **dialog.values())
    finally:
        dialog.close()
    assert saved is sample
    assert (saved.top_depth, saved.bottom_depth) == (101.0001, 101.0004)
    assert not session.dirty
