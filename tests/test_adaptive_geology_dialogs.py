from __future__ import annotations

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

    def edit_description(_parent, _title: str, _label: str, text: str) -> tuple[str, bool]:
        assert text == "Exact sample"
        return "Updated description", True

    def unexpected_warning(*args: object) -> None:
        pytest.fail(f"Saving the exact interval raised a warning: {args[-1]}")

    monkeypatch.setattr(SampleAnalysisDialog, "exec", edit_analysis)
    monkeypatch.setattr(QInputDialog, "getMultiLineText", edit_description)
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
        assert (exact.description, exact.calcite_percent) == ("Updated description", 30.0)
    else:
        assert (exact.description, exact.calcite_percent) == ("Exact sample", 40.0)


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
