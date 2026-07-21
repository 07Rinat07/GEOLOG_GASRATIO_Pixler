from geoworkbench.domain.models import MasterlogCurveStyle
from geoworkbench.project.masterlog_template_controller import MasterlogTemplateController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.masterlog_columns_dialog import (
    ColumnPropertiesDialog,
    CurveStylesDialog,
    DatasetCurveSelectionDialog,
    MasterlogColumnsDialog,
)
from PySide6.QtCore import Qt


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

    dialog = MasterlogColumnsDialog(controller, template.template_id, language=AppLanguage.EN)

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
    dialog.line_style_input.setCurrentIndex(dialog.line_style_input.findData("dash"))

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
    assert dialog.grid_settings() == (True, True, 5, 5, 0.25)
    dialog.close()


def test_column_properties_dialog_returns_title_orientation_and_position(qapp) -> None:
    dialog = ColumnPropertiesDialog(language=AppLanguage.RU)
    dialog.title_orientation_input.setCurrentIndex(
        dialog.title_orientation_input.findData("vertical_top_to_bottom")
    )
    dialog.title_position_input.setCurrentIndex(
        dialog.title_position_input.findData("bottom")
    )

    assert dialog.title_presentation() == ("vertical_top_to_bottom", "bottom")
    dialog.close()


def test_masterlog_controller_persists_column_title_presentation() -> None:
    controller = MasterlogTemplateController(ProjectSession())
    template = controller.create("Rotated")
    column = controller.add_column(
        template.template_id,
        title="Стратиграфия",
        column_type="stratigraphy",
        width_mm=30.0,
        title_orientation="vertical_bottom_to_top",
        title_position="top",
    )

    assert column.properties["title_orientation"] == "vertical_bottom_to_top"
    assert column.properties["title_position"] == "top"

    updated = controller.update_column(
        template.template_id,
        column.column_id,
        title=column.title,
        column_type=column.column_type,
        width_mm=column.width_mm,
        curve_mnemonics=[],
        title_orientation="horizontal",
        title_position="bottom",
    )

    assert updated.properties["title_orientation"] == "horizontal"
    assert updated.properties["title_position"] == "bottom"


def test_column_properties_dialog_offers_stratigraphy(qapp) -> None:
    dialog = ColumnPropertiesDialog(language=AppLanguage.EN)

    assert dialog.type_input.findText("stratigraphy") >= 0
    assert dialog.type_input.findText("cuttings_description") >= 0
    assert dialog.type_input.findText("analysis_interpretation") >= 0
    dialog.close()


def test_dataset_curve_selection_preserves_parameter_order(qapp) -> None:
    dialog = DatasetCurveSelectionDialog(
        ["TG", "C1"], ["C1", "C2", "ROP", "TG"], language=AppLanguage.EN
    )

    assert dialog.windowTitle() == "Column parameters"
    assert dialog.selected_mnemonics() == ["TG", "C1"]
    dialog.list.item(2).setCheckState(Qt.CheckState.Checked)
    assert dialog.selected_mnemonics() == ["TG", "C1", "C2"]
    dialog.close()


def test_curve_styles_dialog_preserves_individual_settings(qapp) -> None:
    dialog = CurveStylesDialog(
        ["C1", "C2"],
        {"C2": MasterlogCurveStyle("#00ff00", 2.5, "dash", 1.0, 100.0)},
        language=AppLanguage.EN,
        default_color="#112233",
        default_width=2.0,
    )

    styles = dialog.styles()

    assert styles["C1"].color == "#112233"
    assert styles["C1"].width == 2.0
    assert styles["C2"] == MasterlogCurveStyle("#00ff00", 2.5, "dash", 1.0, 100.0)
    assert "X 1–100" in dialog.list.item(1).text()
    dialog.close()
