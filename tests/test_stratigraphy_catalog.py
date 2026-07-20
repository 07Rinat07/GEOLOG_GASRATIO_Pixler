from __future__ import annotations

from geoworkbench.catalogs.stratigraphy import load_stratigraphy_catalog
from geoworkbench.project.session import ProjectSession
from geoworkbench.project.stratigraphy_catalog_controller import StratigraphyCatalogController
from geoworkbench.storage.project_codec import project_from_dict


def test_factory_stratigraphy_catalog_has_editable_period_reference() -> None:
    units = load_stratigraphy_catalog()
    by_code = {item.code: item for item in units}

    assert {"Q", "N", "Pg", "K", "J", "T", "P", "C", "D"} <= set(by_code)
    assert by_code["K"].rank == "System / Period"
    assert by_code["K"].name_ru == "Меловая"
    assert by_code["K"].name_en == "Cretaceous"
    assert by_code["K"].color.startswith("#")


def test_project_can_override_reset_and_extend_stratigraphy_catalog() -> None:
    session = ProjectSession()
    controller = StratigraphyCatalogController(session)
    factory = controller.get("period_cretaceous")

    overridden = controller.save(
        factory.unit_id,
        rank=factory.rank,
        code="K-field",
        name_ru="Меловые отложения месторождения",
        name_kk="Кен орнының бор шөгінділері",
        name_en="Field Cretaceous",
        color=factory.color,
        parent_code=factory.parent_code,
        description="Field-specific caption",
    )
    assert overridden.system is True
    assert overridden.overridden is True
    assert controller.get(factory.unit_id).code == "K-field"

    custom = controller.save(
        "custom_formation_a",
        rank="Formation",
        code="Fm-A",
        name_ru="Свита А",
        name_kk="А свитасы",
        name_en="Formation A",
        color="#aabbcc",
    )
    assert custom.system is False
    assert session.dirty is True

    reset = controller.reset(factory.unit_id)
    assert reset.code == "K"
    assert controller.get(custom.unit_id).name_ru == "Свита А"


def test_project_codec_reads_project_stratigraphy_overrides() -> None:
    project = project_from_dict(
        {
            "project_id": "p",
            "name": "Project",
            "wells": {},
            "stratigraphy_units": {
                "custom_local": {
                    "unit_id": "custom_local",
                    "rank": "Formation",
                    "code": "LCL",
                    "name_ru": "Местная свита",
                    "name_kk": "Жергілікті свита",
                    "name_en": "Local formation",
                    "color": "#abcdef",
                    "parent_code": "J",
                    "description": "Editable project entry",
                }
            },
        }
    )

    assert project.stratigraphy_units["custom_local"].code == "LCL"
