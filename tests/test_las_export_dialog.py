from PySide6.QtWidgets import QDialogButtonBox

from geoworkbench.data.las_export_plan import LasExportPlan, LasExportVersion
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.las_export_dialog import LasExportPlanDialog


def test_las_export_dialog_round_trips_plan(qapp) -> None:
    initial = LasExportPlan(
        version=LasExportVersion.V1_2,
        wrap=True,
        null_value=-999.25,
        precision=7,
        preserve_custom_sections=False,
    )

    dialog = LasExportPlanDialog(initial=initial)

    assert dialog.export_plan() == initial
    dialog.close()


def test_las_export_dialog_uses_english_catalog(qapp) -> None:
    dialog = LasExportPlanDialog(language=AppLanguage.EN)
    buttons = dialog.findChild(QDialogButtonBox)

    assert dialog.windowTitle() == "LAS export settings"
    assert dialog.version_combo.itemText(1) == "LAS 1.2 (compatibility)"
    assert dialog.preserve_check.text() == "Preserve custom sections and comments"
    assert buttons.button(QDialogButtonBox.StandardButton.Cancel).text() == "Cancel"
    dialog.close()
