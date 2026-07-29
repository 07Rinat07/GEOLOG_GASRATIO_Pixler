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
    assert any(item.catalog_id == "factory-header:geological_geochemical" for item in factory_items)
    assert all(item.read_only for item in factory_items)

    user = controller.create_header_template(
        "Шапка заказчика",
        preset_catalog_id="factory-header:geological_geochemical",
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

    controller.apply_header_catalog_item(
        target.template_id, "factory-header:geological_geochemical"
    )
    assert target.header_elements
    assert target.properties["header_catalog_origin"] == (
        "factory-header:geological_geochemical"
    )

    saved = controller.save_header_to_catalog(target.template_id, "Сохранённая шапка")
    target.header_elements.clear()
    resolved = resolve_catalog_header(
        controller.session.project.masterlog_templates, saved.template_id
    )
    assert resolved.header_elements
    assert target.header_elements == []
