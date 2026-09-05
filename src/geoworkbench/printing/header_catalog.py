from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from geoworkbench.domain.models import MasterlogTemplate
from geoworkbench.printing.masterlog_presets import (
    BUILTIN_MASTERLOG_HEADER_PRESETS,
    CURATED_MASTERLOG_HEADER_PRESETS,
    MASTERLOG_REFERENCE_HEADER_PRESETS,
    MasterlogHeaderPreset,
)
from geoworkbench.services.localization import AppLanguage

HEADER_CATALOG_KIND = "print_header"
FACTORY_HEADER_PREFIX = "factory-header:"


@dataclass(frozen=True, slots=True)
class HeaderCatalogItem:
    catalog_id: str
    name: str
    description: str
    read_only: bool
    factory: bool
    header_height_mm: float
    element_count: int
    preferred_orientation: str


def factory_header_catalog_id(preset_id: str) -> str:
    return f"{FACTORY_HEADER_PREFIX}{preset_id}"


def is_factory_header_catalog_id(catalog_id: str) -> bool:
    return catalog_id.startswith(FACTORY_HEADER_PREFIX)


def factory_header_preset(catalog_id: str) -> MasterlogHeaderPreset:
    preset_id = catalog_id.removeprefix(FACTORY_HEADER_PREFIX)
    try:
        return next(
            item for item in BUILTIN_MASTERLOG_HEADER_PRESETS if item.preset_id == preset_id
        )
    except StopIteration as exc:
        raise KeyError(catalog_id) from exc


def header_template_from_preset(
    preset: MasterlogHeaderPreset,
    *,
    catalog_id: str | None = None,
    name: str | None = None,
) -> MasterlogTemplate:
    orientation = preset.preferred_orientation
    properties: dict[str, object] = {
        "catalog_kind": HEADER_CATALOG_KIND,
        "factory_preset_id": preset.preset_id,
        "preferred_orientation": orientation,
    }
    if orientation in {"portrait", "landscape"}:
        properties["orientation"] = orientation
    return MasterlogTemplate(
        template_id=catalog_id or factory_header_catalog_id(preset.preset_id),
        name=name or preset.name(AppLanguage.RU),
        page_format="A4",
        header_height_mm=preset.height_mm,
        header_elements=list(deepcopy(preset.elements)),
        columns=[],
        properties=properties,
    )


def is_user_header_template(template: MasterlogTemplate) -> bool:
    return template.properties.get("catalog_kind") == HEADER_CATALOG_KIND


def catalog_items(
    templates: dict[str, MasterlogTemplate],
    language: AppLanguage = AppLanguage.RU,
) -> tuple[HeaderCatalogItem, ...]:
    factory = tuple(
        HeaderCatalogItem(
            catalog_id=factory_header_catalog_id(preset.preset_id),
            name=preset.name(language),
            description=preset.description(language),
            read_only=True,
            factory=True,
            header_height_mm=preset.height_mm,
            element_count=len(preset.elements),
            preferred_orientation=preset.preferred_orientation,
        )
        for preset in CURATED_MASTERLOG_HEADER_PRESETS + MASTERLOG_REFERENCE_HEADER_PRESETS
    )
    user = tuple(
        HeaderCatalogItem(
            catalog_id=template.template_id,
            name=template.name,
            description=str(template.properties.get("catalog_description", "")),
            read_only=False,
            factory=False,
            header_height_mm=template.header_height_mm,
            element_count=len(template.header_elements),
            preferred_orientation=str(template.properties.get("preferred_orientation", "both")),
        )
        for template in sorted(
            (item for item in templates.values() if is_user_header_template(item)),
            key=lambda item: item.name.casefold(),
        )
    )
    return factory + user


def resolve_catalog_header(
    templates: dict[str, MasterlogTemplate], catalog_id: str
) -> MasterlogTemplate:
    if is_factory_header_catalog_id(catalog_id):
        return header_template_from_preset(factory_header_preset(catalog_id))
    try:
        template = templates[catalog_id]
    except KeyError as exc:
        raise KeyError(catalog_id) from exc
    if not is_user_header_template(template):
        # A complete Masterlog template is also a valid source of a print header.
        return template
    return template
