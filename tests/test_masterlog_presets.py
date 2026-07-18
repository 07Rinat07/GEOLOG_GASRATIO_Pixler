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
    assert {"depth", "curves", "stratigraphy", "lithology", "text"} <= column_types


def test_form_preset_creates_independent_project_copy() -> None:
    controller = MasterlogTemplateController(ProjectSession())

    first = controller.create_from_preset("international_mudlog", "Well A")
    second = controller.create_from_preset("international_mudlog", "Well B")
    first.columns[0].title = "MD"
    first.header_elements[0].properties["text"] = "CUSTOM"

    assert second.columns[0].title == "Depth"
    assert second.header_elements[0].properties["text"] == "MASTERLOG"
    assert first.template_id != second.template_id


def test_header_preset_is_copied_into_form_and_remains_editable() -> None:
    controller = MasterlogTemplateController(ProjectSession())
    template = controller.create("Custom")

    controller.apply_header_preset(template.template_id, "compact")
    template.header_elements[0].properties["text"] = "PROJECT TITLE"

    assert len(BUILTIN_MASTERLOG_HEADER_PRESETS) >= 2
    assert template.header_height_mm == 25.0
    assert BUILTIN_MASTERLOG_HEADER_PRESETS[1].elements[0].properties["text"] == "MASTERLOG"
    assert template.properties["header_preset_origin"] == "compact"
