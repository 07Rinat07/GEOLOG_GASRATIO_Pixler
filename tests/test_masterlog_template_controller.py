import pytest

from geoworkbench.domain.models import MasterlogColumnTemplate
from geoworkbench.project.masterlog_template_controller import MasterlogTemplateController
from geoworkbench.project.session import ProjectSession


def test_masterlog_template_lifecycle_uses_independent_copy_and_versions() -> None:
    session = ProjectSession()
    controller = MasterlogTemplateController(session)
    source = controller.create("Standard")
    source.columns.append(
        MasterlogColumnTemplate("gas", "Gas", "curves", 35.0, ["C1"])
    )

    copied = controller.copy(source.template_id, "Customer")
    renamed = controller.rename(source.template_id, "Standard v2")

    assert copied.template_id != source.template_id
    assert copied.columns[0] is not source.columns[0]
    assert copied.version == 1
    assert renamed.version == 2
    assert session.dirty is True
    controller.delete(copied.template_id)
    assert set(session.project.masterlog_templates) == {source.template_id}


def test_masterlog_template_rejects_duplicate_name() -> None:
    controller = MasterlogTemplateController(ProjectSession())
    controller.create("Standard")

    with pytest.raises(ValueError, match="существует"):
        controller.create(" standard ")
