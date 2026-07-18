import pytest

from geoworkbench.project.description_template_controller import DescriptionTemplateController
from geoworkbench.project.session import ProjectSession


def test_description_template_crud() -> None:
    session = ProjectSession()
    controller = DescriptionTemplateController(session)

    controller.add("Песчаник", "Серый мелкозернистый песчаник")
    controller.update("Песчаник", "Песчаник продуктивный", "Песчаник с признаками нефти")

    assert controller.available() == (
        ("Песчаник продуктивный", "Песчаник с признаками нефти"),
    )
    controller.remove("Песчаник продуктивный")
    assert controller.available() == ()
    assert session.dirty is True


def test_description_template_rejects_empty_and_duplicate_values() -> None:
    controller = DescriptionTemplateController(ProjectSession())
    controller.add("Песчаник", "Описание")

    with pytest.raises(ValueError, match="существует"):
        controller.add("Песчаник", "Другое описание")
    with pytest.raises(ValueError, match="пустым"):
        controller.add("", "Описание")
