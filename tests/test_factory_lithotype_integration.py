from __future__ import annotations

from geoworkbench.domain.models import (
    MasterlogColumnTemplate,
    MasterlogHeaderElement,
    MasterlogTemplate,
)
from geoworkbench.project.lithotype_catalog_controller import (
    LithotypeCatalogController,
    _CODE_PATTERN,
)
from geoworkbench.project.session import ProjectSession
from geoworkbench.printing.masterlog_output import MasterlogOutputSettings
from geoworkbench.printing.masterlog_preflight import analyze_masterlog_output
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.lithology_interval_dialog import LithologyIntervalDialog
from geoworkbench.ui.masterlog_header_dialog import HeaderElementDialog
from geoworkbench.ui.unified_cuttings_sample_dialog import UnifiedCuttingsSampleDialog


def test_factory_lithotypes_are_available_without_copying_them_into_project() -> None:
    session = ProjectSession()
    controller = LithotypeCatalogController(session)

    catalog = controller.available()
    factory = [item for item in catalog if item.source == "factory"]

    assert len(factory) == 117
    assert session.project.lithotypes == {}
    dolomite = controller.get("lithology-dolomite")
    assert dolomite.pattern_key == "constructor:lithology-dolomite"
    assert dolomite.system is True
    assert all(_CODE_PATTERN.fullmatch(item.code) for item in factory)


def test_factory_lithotype_can_be_overridden_and_reset() -> None:
    session = ProjectSession()
    controller = LithotypeCatalogController(session)
    original = controller.get("lithology-dolomite")

    changed = controller.update(
        original.lithotype_id,
        code=original.code,
        name_ru="Доломит пользовательский",
        name_kk="Пайдаланушы доломиті",
        name_en="Custom dolomite",
        category=original.category,
        color="#aabbcc",
        pattern_key=original.pattern_key,
    )

    assert changed.overridden is True
    assert controller.get(original.lithotype_id).name_ru == "Доломит пользовательский"
    assert original.lithotype_id in session.project.lithotypes

    controller.remove(original.lithotype_id)

    reset = controller.get(original.lithotype_id)
    assert reset.name_ru == original.name_ru
    assert reset.source == "factory"
    assert original.lithotype_id not in session.project.lithotypes


def test_lithology_quick_selector_shows_standard_bitmap_set(qapp) -> None:
    catalog = LithotypeCatalogController(ProjectSession()).available()
    dialog = LithologyIntervalDialog(100.0, 110.0, catalog, language=AppLanguage.RU)

    assert dialog.lithotype_input.count() == len(catalog)
    index = dialog.lithotype_input.findData("lithology-dolomite")
    assert index >= 0
    assert not dialog.lithotype_input.itemIcon(index).isNull()
    # The quick editor remains a selection-only control; keyboard prefix search
    # still works without accepting arbitrary lithotype text.
    assert dialog.lithotype_input.isEditable() is False
    dialog.close()


def test_cuttings_editor_shows_standard_bitmap_set_with_search(qapp) -> None:
    catalog = LithotypeCatalogController(ProjectSession()).available()
    dialog = UnifiedCuttingsSampleDialog(
        100.0,
        110.0,
        catalog,
        language=AppLanguage.RU,
    )

    first = dialog.rock_inputs[0]
    assert first.count() == len(catalog) + 1
    assert first.isEditable() is True
    index = first.findData("lithology-dolomite")
    assert index >= 0
    assert not first.itemIcon(index).isNull()
    dialog.close()


def test_header_can_insert_one_factory_lithotype_with_rotated_label(qapp) -> None:
    catalog = LithotypeCatalogController(ProjectSession()).available()
    lithotypes = {item.lithotype_id: item for item in catalog}
    dialog = HeaderElementDialog(language=AppLanguage.RU, lithotypes=lithotypes)
    dialog.type_input.setCurrentText("lithotype_swatch")
    assert dialog.type_input.currentText() == "Образец литотипа / рисунок породы"
    dialog.lithotype_input.setCurrentIndex(
        dialog.lithotype_input.findData("lithology-dolomite")
    )
    dialog.lithotype_label_mode_input.setCurrentIndex(
        dialog.lithotype_label_mode_input.findData("pattern_code_name")
    )
    dialog.text_orientation_input.setCurrentIndex(
        dialog.text_orientation_input.findData("vertical_bottom_to_top")
    )
    dialog.text_position_input.setCurrentIndex(
        dialog.text_position_input.findData("bottom")
    )

    properties = dialog.values()[-1]

    assert properties["lithotype_id"] == "lithology-dolomite"
    assert properties["display_mode"] == "pattern_code_name"
    assert properties["text_orientation"] == "vertical_bottom_to_top"
    assert properties["text_position"] == "bottom"
    dialog.close()


def test_preflight_accepts_factory_swatch_and_rejects_unknown_lithotype() -> None:
    session = ProjectSession()
    element = MasterlogHeaderElement(
        "swatch",
        "lithotype_swatch",
        2.0,
        2.0,
        40.0,
        10.0,
        {"lithotype_id": "lithology-dolomite"},
    )
    template = MasterlogTemplate(
        "template",
        "Template",
        header_elements=[element],
        columns=[MasterlogColumnTemplate("depth", "Depth", "depth", 20.0)],
    )

    report = analyze_masterlog_output(template, session, MasterlogOutputSettings(0.0, 100.0))
    assert not any(issue.code == "missing_lithotype" for issue in report.issues)

    element.properties["lithotype_id"] = "missing-pattern"
    report = analyze_masterlog_output(template, session, MasterlogOutputSettings(0.0, 100.0))
    assert any(issue.code == "missing_lithotype" for issue in report.issues)

