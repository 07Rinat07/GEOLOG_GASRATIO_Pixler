from copy import deepcopy

import numpy as np
import pytest
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QDoubleSpinBox, QMessageBox

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain, MasterlogTemplate
from geoworkbench.printing.masterlog_output import MasterlogOutputSettings
from geoworkbench.project.cuttings_controller import CuttingsController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage
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


def _masterlog_analysis_session() -> ProjectSession:
    session = ProjectSession()
    session.add_dataset(
        Dataset("dataset", "Well", DatasetKind.GTI, DepthDomain.MD, np.array([100.0, 200.0]))
    )
    return session


def _fill_masterlog_analysis(
    monkeypatch: pytest.MonkeyPatch,
    session: ProjectSession,
    selected: tuple[float, float],
    edited: tuple[float | None, float | None],
    expected_calcite: float,
) -> list[str]:
    warnings: list[str] = []

    def fill(dialog: SampleAnalysisDialog) -> QDialog.DialogCode:
        assert dialog.calcite_input.value() == expected_calcite
        edited_top, edited_bottom = edited
        if edited_top is not None:
            dialog.top_input.setValue(edited_top)
        if edited_bottom is not None:
            dialog.bottom_input.setValue(edited_bottom)
        dialog.calcite_input.setValue(42.0)
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
    session = _masterlog_analysis_session()
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
    session = _masterlog_analysis_session()
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
    session = _masterlog_analysis_session()
    controller = CuttingsController(session)
    stored = (150.0004, 151.1234)
    selected = (stored[0] + 5e-7, stored[1] + 5e-7)
    sample = controller.set_analysis(*stored, calcite_percent=30.0)

    assert _fill_masterlog_analysis(monkeypatch, session, selected, (None, None), 30.0) == []

    assert controller.available() == (sample,)
    assert controller.get(sample.sample_id) is sample
    assert (sample.top_depth, sample.bottom_depth) == stored
    assert sample.calcite_percent == 42.0
