from __future__ import annotations

from geoworkbench.domain.models import MasterlogTemplate, Project, new_id
from geoworkbench.project.masterlog_template_controller import MasterlogTemplateController
from geoworkbench.project.session import ProjectSession
from geoworkbench.printing.header_catalog import (
    HEADER_CATALOG_KIND,
    catalog_items,
    resolve_catalog_header,
)
from geoworkbench.services.localization import AppLanguage


def _controller() -> MasterlogTemplateController:
    session = ProjectSession(Project(new_id(), "Header catalog test"))
    return MasterlogTemplateController(session)


def test_factory_and_user_headers_are_separate_catalog_entries() -> None:
    controller = _controller()
    factory_items = catalog_items(
        controller.session.project.masterlog_templates, AppLanguage.RU
    )
    curated_id = "factory-header:a4_geology_technology_gas_portrait"
    assert any(item.catalog_id == curated_id for item in factory_items)
    assert all("geological_geochemical" not in item.catalog_id for item in factory_items)
    assert all(item.read_only for item in factory_items)

    user = controller.create_header_template(
        "Шапка заказчика",
        preset_catalog_id=curated_id,
        preferred_orientation="landscape",
    )
    assert user.columns == []
    assert user.properties["catalog_kind"] == HEADER_CATALOG_KIND

    items = catalog_items(controller.session.project.masterlog_templates, AppLanguage.RU)
    item = next(value for value in items if value.catalog_id == user.template_id)
    assert item.read_only is False
    assert item.preferred_orientation == "landscape"


def test_any_masterlog_can_receive_independent_header_copy() -> None:
    controller = _controller()
    target = MasterlogTemplate(new_id(), "Target", header_elements=[])
    controller.session.project.masterlog_templates[target.template_id] = target
    curated_id = "factory-header:a4_geology_technology_gas_portrait"

    controller.apply_header_catalog_item(
        target.template_id, curated_id
    )
    assert target.header_elements
    assert target.properties["header_catalog_origin"] == curated_id

    saved = controller.save_header_to_catalog(target.template_id, "Сохранённая шапка")
    target.header_elements.clear()
    resolved = resolve_catalog_header(
        controller.session.project.masterlog_templates, saved.template_id
    )
    assert resolved.header_elements
    assert target.header_elements == []


def test_fit_header_to_page_scales_geometry_and_expands_height() -> None:
    controller = _controller()
    template = controller.create_header_template("Wide header")
    template.header_elements = []
    first = controller.add_header_element(
        template.template_id, element_type="text", x_mm=100.0, y_mm=5.0,
        width_mm=300.0, height_mm=20.0,
        properties={"text": "Wide", "font_size_mm": 6.0},
    )
    second = controller.add_header_element(
        template.template_id, element_type="field", x_mm=420.0, y_mm=35.0,
        width_mm=160.0, height_mm=30.0,
        properties={"field": "well.name", "font_size_mm": 4.0},
    )
    scale = controller.fit_header_to_page(template.template_id, 210.0)
    assert 0.0 < scale < 1.0
    assert min(item.x_mm for item in template.header_elements) == 2.0
    assert max(item.x_mm + item.width_mm for item in template.header_elements) <= 208.0
    assert template.header_height_mm >= max(item.y_mm + item.height_mm for item in template.header_elements)
    fitted_first = next(item for item in template.header_elements if item.element_id == first.element_id)
    fitted_second = next(item for item in template.header_elements if item.element_id == second.element_id)
    assert fitted_first.properties["font_size_mm"] < 6.0
    assert fitted_second.properties["font_size_mm"] < 4.0
