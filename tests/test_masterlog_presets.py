from geoworkbench.project.masterlog_template_controller import MasterlogTemplateController
from geoworkbench.project.session import ProjectSession
from geoworkbench.printing.masterlog_presets import (
    BUILTIN_MASTERLOG_FORM_PRESETS,
    BUILTIN_MASTERLOG_HEADER_PRESETS,
)


def test_builtin_masterlog_presets_are_unique_and_cover_core_tracks() -> None:
    assert len(BUILTIN_MASTERLOG_FORM_PRESETS) >= 3
    assert len({item.preset_id for item in BUILTIN_MASTERLOG_FORM_PRESETS}) == len(
        BUILTIN_MASTERLOG_FORM_PRESETS
    )
    column_types = {
        column.column_type
        for preset in BUILTIN_MASTERLOG_FORM_PRESETS
        for column in preset.template.columns
    }
    assert {
        "depth",
        "curves",
        "stratigraphy",
        "lithology",
        "text",
        "cuttings_description",
        "analysis_interpretation",
    } <= column_types

    field = next(
        item for item in BUILTIN_MASTERLOG_FORM_PRESETS if item.preset_id == "international_mudlog"
    )
    assert [column.column_id for column in field.template.columns] == [
        "drilling",
        "depth",
        "core_slide",
        "cuttings",
        "direct_fluorescence",
        "cut_fluorescence",
        "resistivity",
        "gas",
        "calcimetry",
        "lithology",
        "interpretation",
        "description",
    ]
    gas = next(column for column in field.template.columns if column.column_id == "gas")
    assert set(gas.curve_styles) == set(gas.curve_mnemonics)
    assert len({style.color for style in gas.curve_styles.values()}) > 1
    assert gas.curve_styles["TG"].x_min == 1.0
    assert gas.grid_x is True
    assert gas.grid_y is True
    assert gas.grid_major_divisions == 5
    assert gas.grid_minor_divisions == 5
    assert gas.grid_alpha == 0.22
    depth = next(column for column in field.template.columns if column.column_id == "depth")
    assert depth.grid_x is False
    assert depth.grid_y is False
    legend = next(
        element
        for element in field.template.header_elements
        if element.element_type == "lithology_legend"
    )
    assert field.template.header_height_mm == 60.0
    assert legend.properties == {
        "scope": "all",
        "columns": 5,
        "show_code": True,
        "font_size_mm": 2.6,
    }


def test_form_preset_creates_independent_project_copy() -> None:
    controller = MasterlogTemplateController(ProjectSession())

    first = controller.create_from_preset("international_mudlog", "Well A")
    second = controller.create_from_preset("international_mudlog", "Well B")
    first.columns[0].title = "MD"
    first.header_elements[0].properties["text"] = "CUSTOM"

    assert second.columns[0].title == "Drilling parameters: ROP / WOB / TORQUE / GR"
    assert second.header_elements[0].properties["text"] == "MASTERLOG"
    assert first.template_id != second.template_id


def test_header_preset_is_copied_into_form_and_remains_editable() -> None:
    controller = MasterlogTemplateController(ProjectSession())
    template = controller.create("Custom")

    controller.apply_header_preset(template.template_id, "compact")
    template.header_elements[0].properties["text"] = "PROJECT TITLE"

    assert len(BUILTIN_MASTERLOG_HEADER_PRESETS) >= 3
    assert template.header_height_mm == 25.0
    compact = next(
        item for item in BUILTIN_MASTERLOG_HEADER_PRESETS if item.preset_id == "compact"
    )
    assert compact.elements[0].properties["text"] == "MASTERLOG"
    assert template.properties["header_preset_origin"] == "compact"
