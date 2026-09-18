import numpy as np
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QTableWidget

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    CustomFormulaDefinition,
    Dataset,
    DatasetKind,
    DepthDomain,
)
from geoworkbench.project.custom_formula_controller import CustomFormulaController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.custom_formula_dialog import (
    CustomFormulaDialog,
    CustomFormulaPassportDialog,
    FormulaBatchPreviewDialog,
)


def make_controller() -> CustomFormulaController:
    dataset = Dataset("dataset", "Dataset", DatasetKind.GTI, DepthDomain.MD, np.array([0.0, 1.0]))
    dataset.curves["c1"] = CurveData(
        CurveMetadata("c1", "C1", "C1", "%", None, dataset.dataset_id),
        np.array([1.0, 2.0]),
    )
    session = ProjectSession()
    session.add_dataset(dataset)
    session.project.custom_formulas["double"] = CustomFormulaDefinition(
        "double", "Double", "C1 * 2", "DOUBLE", "%"
    )
    return CustomFormulaController(session)


def test_batch_preview_shows_calculated_statistics(qapp) -> None:
    controller = make_controller()
    plan = controller.analyze_batch()
    dialog = FormulaBatchPreviewDialog(plan, language=AppLanguage.EN)
    table = dialog.findChild(QTableWidget, "formula-batch-preview")

    assert dialog.windowTitle() == "Formula batch preview"
    assert table is not None
    assert table.rowCount() == 1
    assert table.item(0, 0).text() == "Double"
    assert table.item(0, 1).text() == "DOUBLE"
    assert table.item(0, 5).text() == "2"
    dialog.close()


def test_custom_formula_dialog_applies_accepted_batch_preview(qapp, monkeypatch) -> None:
    controller = make_controller()
    dialog = CustomFormulaDialog(controller, language=AppLanguage.EN)
    monkeypatch.setattr(
        "geoworkbench.ui.custom_formula_dialog.FormulaBatchPreviewDialog.exec",
        lambda self: QDialog.DialogCode.Accepted,
    )

    dialog._calculate_all()

    curve = controller.session.current_dataset.curve_by_mnemonic("DOUBLE")
    assert curve is not None
    np.testing.assert_allclose(curve.values, [2.0, 4.0])
    assert dialog.calculated_mnemonic == "DOUBLE"
    assert dialog.dataset_changed
    assert dialog.undo_batch_button.isEnabled()

    dialog._undo_batch()
    assert controller.session.current_dataset.curve_by_mnemonic("DOUBLE") is None
    assert dialog.redo_batch_button.isEnabled()

    dialog._redo_batch()
    restored = controller.session.current_dataset.curve_by_mnemonic("DOUBLE")
    assert restored is not None
    np.testing.assert_allclose(restored.values, [2.0, 4.0])
    assert dialog.undo_batch_button.isEnabled()
    dialog.close()


def test_custom_formula_passport_dialog_shows_missing_and_provenance(qapp) -> None:
    controller = make_controller()
    passport = controller.calculation_passport("double")
    dialog = CustomFormulaPassportDialog(passport, language=AppLanguage.EN)
    table = dialog.findChild(QTableWidget, "custom-formula-passport-curves")

    assert dialog.windowTitle() == "Calculation passport"
    assert table is not None
    assert table.rowCount() == 2
    assert table.item(0, 0).text() == "C1"
    assert table.item(0, 3).text() == "source"
    assert table.item(1, 0).text() == "DOUBLE"
    assert table.item(1, 1).text() == "missing"
    dialog.close()



def test_custom_formula_dialog_uses_adaptive_toolbar_and_sticky_close(qapp) -> None:
    dialog = CustomFormulaDialog(make_controller(), language=AppLanguage.EN)
    try:
        screen = dialog.screen()
        assert screen is not None
        available = screen.availableGeometry()
        assert dialog.minimumWidth() <= dialog.width() <= available.width()
        assert dialog.minimumHeight() <= dialog.height() <= available.height()

        assert dialog.actions_toolbar.objectName() == "custom-formula-actions"
        assert len(dialog.actions_toolbar.actions()) == 8
        buttons = dialog.findChild(QDialogButtonBox)
        assert buttons is not None
        close_button = buttons.button(QDialogButtonBox.StandardButton.Close)
        assert close_button is not None
        assert close_button.text() == "Close"
    finally:
        dialog.close()


def test_custom_formula_passport_and_batch_preview_fit_current_work_area(qapp) -> None:
    controller = make_controller()
    passport_dialog = CustomFormulaPassportDialog(
        controller.calculation_passport("double"),
        language=AppLanguage.EN,
    )
    batch_dialog = FormulaBatchPreviewDialog(
        controller.analyze_batch(),
        language=AppLanguage.EN,
    )
    try:
        for dialog in (passport_dialog, batch_dialog):
            screen = dialog.screen()
            assert screen is not None
            available = screen.availableGeometry()
            assert dialog.minimumWidth() <= dialog.width() <= available.width()
            assert dialog.minimumHeight() <= dialog.height() <= available.height()
    finally:
        passport_dialog.close()
        batch_dialog.close()
