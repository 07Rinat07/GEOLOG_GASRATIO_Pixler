import numpy as np
from PySide6.QtWidgets import QComboBox, QDialog, QDialogButtonBox

from geoworkbench.calculations.controller import FormulaExecutionController
from geoworkbench.calculations.pixler import build_all_sourced_formula_registry
from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.formula_dialog import FormulaExecutionDialog


def make_dialog(
    language: AppLanguage = AppLanguage.RU,
) -> tuple[FormulaExecutionDialog, ProjectSession]:
    dataset = Dataset("dataset", "Drilling", DatasetKind.GTI, DepthDomain.MD, np.array([1.0]))
    for mnemonic, unit, value in (
        ("ROP", "ft/h", 60.0),
        ("RPM", "rpm", 100.0),
        ("WOB", "lbf", 50_000.0),
        ("BS", "in", 10.0),
    ):
        dataset.upsert_curve(mnemonic, np.array([value]), unit=unit, provenance="source")
    session = ProjectSession()
    session.add_dataset(dataset)
    registry = build_all_sourced_formula_registry()
    return FormulaExecutionDialog(
        dataset,
        registry,
        FormulaExecutionController(session, registry),
        language=language,
    ), session


def test_formula_dialog_shows_passport_and_builds_mapping(qapp) -> None:
    dialog, _ = make_dialog()
    index = dialog.profile_selector.findData("dexp.jorden_shirley")
    dialog.profile_selector.setCurrentIndex(index)

    assert "10.2118/1407-PA" in dialog.passport_label.text()
    assert set(dialog.input_selectors) == {"ROP_FPH", "RPM", "WOB_LBF", "BIT_IN"}
    assert dialog.findChild(QComboBox, "formula-input-RPM") is not None
    dialog.close()


def test_formula_dialog_executes_selected_profile(qapp) -> None:
    dialog, session = make_dialog()
    dialog.profile_selector.setCurrentIndex(dialog.profile_selector.findData("dexp.jorden_shirley"))
    for input_name, mnemonic in {
        "ROP_FPH": "ROP",
        "RPM": "RPM",
        "WOB_LBF": "WOB",
        "BIT_IN": "BS",
    }.items():
        dialog.input_selectors[input_name].setCurrentText(mnemonic)

    dialog._execute()

    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.execution_result is not None
    assert session.current_dataset is not None
    assert session.current_dataset.curve_by_mnemonic("DEXP") is not None
    dialog.close()


def test_formula_dialog_uses_english_catalog(qapp) -> None:
    dialog, _ = make_dialog(AppLanguage.EN)
    buttons = dialog.findChild(QDialogButtonBox)
    dialog.profile_selector.setCurrentIndex(
        dialog.profile_selector.findData("dexp.jorden_shirley")
    )

    assert dialog.windowTitle() == "Calculation formula profiles"
    assert "Output:" in dialog.passport_label.text()
    assert "Source:" in dialog.passport_label.text()
    assert "Normalized indicator of the rate of penetration" in dialog.passport_label.text()
    assert buttons.button(QDialogButtonBox.StandardButton.Ok).text() == "Calculate"
    assert buttons.button(QDialogButtonBox.StandardButton.Cancel).text() == "Cancel"
    normalized_index = dialog.profile_selector.findData(
        "gas.normalized_c1_us20140379265"
    )
    assert dialog.profile_selector.itemText(normalized_index) == "Drilling-normalized methane C1"
    reference_index = dialog.profile_selector.findData(
        "gas.normalized_total_reference_us20150060054"
    )
    assert dialog.profile_selector.itemText(reference_index) == "Reference-normalized total gas"
    dialog.profile_selector.setCurrentIndex(reference_index)
    assert set(dialog.parameter_editors) == {
        "ROP_REF_FPH", "BIT_REF_IN", "FLOW_REF_GPM", "GAS_SYSTEM_EFFICIENCY"
    }
    dialog.close()
