from geoworkbench.project.masterlog_template_controller import MasterlogTemplateController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.masterlog_columns_dialog import (
    ColumnPropertiesDialog,
    MasterlogColumnsDialog,
)


def test_masterlog_columns_dialog_lists_column_properties(qapp) -> None:
    controller = MasterlogTemplateController(ProjectSession())
    template = controller.create("Standard")
    controller.add_column(
        template.template_id,
        title="Gas",
        column_type="curves",
        width_mm=35.0,
        curve_mnemonics=["C1", "C2"],
    )

    dialog = MasterlogColumnsDialog(
        controller, template.template_id, language=AppLanguage.EN
    )

    assert dialog.windowTitle() == "Masterlog columns"
    assert dialog.list.item(0).text() == "Gas | curves | 35 mm | C1, C2"
    dialog.close()


def test_column_properties_dialog_returns_normalized_curve_list(qapp) -> None:
    dialog = ColumnPropertiesDialog(language=AppLanguage.EN)
    dialog.title_input.setText("Gas")
    dialog.type_input.setCurrentText("curves")
    dialog.width_input.setValue(40.0)
    dialog.curves_input.setText(" C1, C2 ,, ")

    dialog.auto_range_input.setChecked(False)
    dialog.minimum_input.setValue(0.1)
    dialog.maximum_input.setValue(100.0)
    dialog.legend_input.setChecked(False)
    dialog.color_input.setText("#112233")
    dialog.line_width_input.setValue(2.5)
    dialog.line_style_input.setCurrentIndex(
        dialog.line_style_input.findData("dash")
    )

    assert dialog.windowTitle() == "Column properties"
    assert dialog.values() == (
        "Gas",
        "curves",
        40.0,
        ["C1", "C2"],
        "linear",
        0.1,
        100.0,
        False,
        "#112233",
        2.5,
        "dash",
    )
    dialog.close()


def test_column_properties_dialog_offers_stratigraphy(qapp) -> None:
    dialog = ColumnPropertiesDialog(language=AppLanguage.EN)

    assert dialog.type_input.findText("stratigraphy") >= 0
    dialog.close()
