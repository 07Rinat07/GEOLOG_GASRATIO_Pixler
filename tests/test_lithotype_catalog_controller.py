import pytest

from geoworkbench.domain.models import LithologyInterval, Well
from geoworkbench.project.lithotype_catalog_controller import LithotypeCatalogController
from geoworkbench.project.session import ProjectSession


def test_project_lithotype_lifecycle_marks_project_dirty() -> None:
    session = ProjectSession()
    controller = LithotypeCatalogController(session)

    created = controller.add(
        "oil_sand", "os", "Нефтенасыщенный песок", "Oil sand", "sedimentary", "#A07840", "dots", "Мұнайлы құм"
    )
    updated = controller.update(
        "oil_sand",
        code="OS2",
        name_ru="Нефтяной песок",
        name_en="Oil sand",
        category="sedimentary",
        color="#a07840",
        pattern_key="dense_dots",
        name_kk="Мұнайлы құм",
    )
    removed = controller.remove("oil_sand")

    assert created.system is False
    assert created.localized_name("kk") == "Мұнайлы құм"
    assert updated.code == "OS2"
    assert removed.lithotype_id == "oil_sand"
    assert session.project.lithotypes == {}
    assert session.dirty is True


def test_system_lithotype_and_duplicate_code_are_protected() -> None:
    controller = LithotypeCatalogController(ProjectSession())

    with pytest.raises(KeyError, match="нельзя удалить"):
        controller.remove("sandstone")
    with pytest.raises(ValueError, match="Код литотипа уже существует"):
        controller.add("my_sand", "SANDSTONE", "Песок", "Sand", "sedimentary", "#ffeeaa", "dots")


def test_used_project_lithotype_cannot_be_removed() -> None:
    session = ProjectSession()
    controller = LithotypeCatalogController(session)
    controller.add("custom", "CUS", "Порода", "Rock", "other", "#112233", "solid")
    session.project.wells["well"] = Well(
        "well",
        "Well",
        lithology=[LithologyInterval("interval", 10.0, 20.0, "custom", None)],
    )

    with pytest.raises(ValueError, match="используется"):
        controller.remove("custom")

    assert "custom" in session.project.lithotypes
