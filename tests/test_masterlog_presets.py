import pytest

from geoworkbench.project.masterlog_template_controller import MasterlogTemplateController
from geoworkbench.project.session import ProjectSession
from geoworkbench.printing.masterlog_presets import (
    BUILTIN_MASTERLOG_FORM_PRESETS,
    BUILTIN_MASTERLOG_HEADER_PRESETS,
    CURATED_MASTERLOG_FORM_PRESETS,
    CURATED_MASTERLOG_HEADER_PRESETS,
    MASTERLOG_REFERENCE_HEADER_PRESETS,
)
from geoworkbench.services.localization import AppLanguage


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
    assert gas.curve_styles["TG"].x_min == 0.0
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
    compact = next(item for item in BUILTIN_MASTERLOG_HEADER_PRESETS if item.preset_id == "compact")
    assert compact.elements[0].properties["text"] == "MASTERLOG"
    assert template.properties["header_preset_origin"] == "compact"


def test_geological_geochemical_reference_preset_matches_working_masterlog_structure() -> None:
    preset = next(
        item
        for item in BUILTIN_MASTERLOG_FORM_PRESETS
        if item.preset_id == "geological_geochemical_reference"
    )
    assert [column.column_type for column in preset.template.columns] == [
        "stratigraphy",
        "curves",
        "depth",
        "cuttings",
        "lba",
        "calcimetry",
        "lithology",
        "curves",
        "cuttings_description",
    ]
    assert preset.template.header_height_mm == 110.0
    assert any(
        element.element_type == "lithology_legend" for element in preset.template.header_elements
    )
    assert any(element.element_type == "lba_legend" for element in preset.template.header_elements)
    drilling = preset.template.columns[1]
    assert drilling.curve_styles["WOB"].x_max == 20.0
    assert drilling.curve_styles["ROP"].x_max == 100.0
    assert drilling.curve_styles["DMC"].x_max == 50.0
    assert drilling.curve_styles["DEXP"].x_max == 3.0
    gas = preset.template.columns[7]
    assert gas.x_scale == "linear"
    assert gas.x_min == 0.0
    assert gas.x_max == 100.0
    assert gas.curve_mnemonics[-1] == "TG"


def test_kazgeology_reference_blank_has_uploadable_logo_slots_and_expected_columns() -> None:
    preset = next(
        item
        for item in BUILTIN_MASTERLOG_FORM_PRESETS
        if item.preset_id == "kazgeology_reference_blank"
    )
    assert preset.template.page_format == "A3"
    assert preset.template.properties["orientation"] == "landscape"
    assert preset.template.header_height_mm == 104.0
    logo_slots = [
        element for element in preset.template.header_elements if element.element_type == "image"
    ]
    assert [element.element_id for element in logo_slots] == ["kz_logo_left", "kz_logo_right"]
    assert all(element.properties["optional"] is True for element in logo_slots)
    assert all("asset_ref" not in element.properties for element in logo_slots)
    assert [column.column_type for column in preset.template.columns] == [
        "stratigraphy",
        "curves",
        "depth",
        "cuttings",
        "lba",
        "calcimetry",
        "lithology",
        "curves",
        "cuttings_description",
    ]
    assert preset.template.columns[-1].properties["automatic_lithology_fallback"] is False
    gas = preset.template.columns[7]
    assert gas.x_scale == "linear"
    assert gas.x_min == 0.0
    assert gas.x_max == 100.0
    assert gas.grid_major_divisions == 5
    assert gas.grid_minor_divisions == 10


def test_every_builtin_masterlog_column_is_linear_by_default() -> None:
    for preset in BUILTIN_MASTERLOG_FORM_PRESETS:
        assert all(column.x_scale == "linear" for column in preset.template.columns)


def test_curated_a4_forms_and_headers_are_paired_and_fit_both_orientations() -> None:
    assert len(CURATED_MASTERLOG_FORM_PRESETS) == 10
    assert len(CURATED_MASTERLOG_HEADER_PRESETS) == 10
    headers = {item.preset_id: item for item in CURATED_MASTERLOG_HEADER_PRESETS}

    for preset in CURATED_MASTERLOG_FORM_PRESETS:
        template = preset.template
        orientation = template.properties["orientation"]
        expected_width = 210.0 if orientation == "portrait" else 297.0
        printable_width = 200.0 if orientation == "portrait" else 287.0
        header_id = template.properties["paired_header_preset_id"]
        header = headers[header_id]

        assert template.page_format == "A4"
        assert header.preferred_orientation == orientation
        assert template.header_height_mm == header.height_mm == 34.0
        assert sum(column.width_mm for column in template.columns) == pytest.approx(printable_width)
        assert all(
            element.x_mm >= 0.0
            and element.y_mm >= 0.0
            and element.x_mm + element.width_mm <= expected_width
            and element.y_mm + element.height_mm <= header.height_mm
            for element in header.elements
        )


def test_reference_masterlog_headers_are_editable_and_have_default_logo_contract() -> None:
    assert {item.preferred_orientation for item in MASTERLOG_REFERENCE_HEADER_PRESETS} == {
        "portrait", "landscape"
    }
    for preset in MASTERLOG_REFERENCE_HEADER_PRESETS:
        assert preset.height_mm in {100.0, 140.0}
        assert set(preset.names) == {AppLanguage.RU, AppLanguage.KK, AppLanguage.EN}
        images = [
            item for item in preset.elements
            if item.element_type == "image" and item.properties.get("logo_role")
        ]
        assert {item.properties.get("logo_role") for item in images} == {"customer", "contractor"}
        contractor = next(item for item in images if item.properties.get("logo_role") == "contractor")
        assert isinstance(contractor.properties.get("asset_ref"), str)
        customer = next(item for item in images if item.properties.get("logo_role") == "customer")
        assert customer.properties.get("asset_ref") is None
        fields = {
            item.properties.get("field")
            for item in preset.elements
            if item.element_type == "field"
        }
        assert {"header.interval_start", "header.interval_end", "header.geologists"} <= fields


def test_curated_a4_header_text_is_available_in_all_languages() -> None:
    header = next(
        item
        for item in CURATED_MASTERLOG_HEADER_PRESETS
        if item.preset_id == "a4_geology_technology_gas_portrait"
    )
    text_elements = {
        element.element_id: element
        for element in header.elements
        if element.element_type == "text"
    }

    title = text_elements["geology_technology_gas_portrait_title"].properties
    assert title["text_ru"] == "ГЕОЛОГИЯ · ТЕХНОЛОГИЯ · ГАЗ"
    assert title["text_kk"] == "ГЕОЛОГИЯ · БҰРҒЫЛАУ · ГАЗ"
    assert title["text_en"] == "GEOLOGY · DRILLING · GAS"

    project = text_elements["geology_technology_gas_portrait_0_0_label"].properties
    assert project["text_ru"] == "ПРОЕКТ"
    assert project["text_kk"] == "ЖОБА"
    assert project["text_en"] == "PROJECT"

    well = text_elements["geology_technology_gas_portrait_0_1_label"].properties
    assert well["text_ru"] == "СКВАЖИНА"
    assert well["text_kk"] == "ҰҢҒЫМА"
    assert well["text_en"] == "WELL"


def test_curated_masterlog_column_titles_follow_selected_language() -> None:
    preset = next(
        item
        for item in CURATED_MASTERLOG_FORM_PRESETS
        if item.preset_id == "a4_geology_technology_gas_portrait"
    )

    expected = {
        AppLanguage.RU: ("Глубина", "Описание пород"),
        AppLanguage.KK: ("Тереңдік", "Тау жыныстарының сипаттамасы"),
        AppLanguage.EN: ("Depth", "Rock description"),
    }
    for language, (depth_title, description_title) in expected.items():
        template = preset.template_for(language)
        assert template.name == preset.name(language)
        assert template.columns[0].title == depth_title
        assert template.columns[-1].title == description_title


def test_operational_header_catalog_contains_daily_technology_and_emergency_templates() -> None:
    by_id = {item.preset_id: item for item in BUILTIN_MASTERLOG_HEADER_PRESETS}
    assert {
        "daily_technology_control",
        "technology_research",
        "emergency_control",
    } <= set(by_id)
    daily = by_id["daily_technology_control"]
    assert daily.height_mm == 50.0
    assert sum(element.element_type == "image" for element in daily.elements) == 2
    assert any(
        element.properties.get("field") == "header.shift_personnel" for element in daily.elements
    )
    technology = by_id["technology_research"]
    assert any(element.element_type == "lithology_legend" for element in technology.elements)
    emergency = by_id["emergency_control"]
    assert emergency.height_mm == 32.0
    assert any(
        element.properties.get("field") == "header.interval" for element in emergency.elements
    )
