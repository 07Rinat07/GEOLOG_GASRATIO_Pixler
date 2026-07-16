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


def test_masterlog_template_controller_manages_column_lifecycle() -> None:
    controller = MasterlogTemplateController(ProjectSession())
    template = controller.create("Standard")
    first = controller.add_column(
        template.template_id,
        title="Depth",
        column_type="depth",
        width_mm=15.0,
    )
    second = controller.add_column(
        template.template_id,
        title="Gas",
        column_type="curves",
        width_mm=35.0,
        curve_mnemonics=["C1", "C2", "C1"],
    )

    assert second.curve_mnemonics == ["C1", "C2"]
    assert controller.move_column(template.template_id, second.column_id, -1) is True
    updated = controller.update_column(
        template.template_id,
        first.column_id,
        title="Measured depth",
        column_type="depth",
        width_mm=20.0,
        curve_mnemonics=[],
    )
    assert updated.width_mm == 20.0
    assert [column.column_id for column in template.columns] == [
        second.column_id,
        first.column_id,
    ]
    controller.remove_column(template.template_id, second.column_id)
    assert [column.column_id for column in template.columns] == [first.column_id]
    assert template.version == 6


def test_masterlog_column_rejects_unsafe_width() -> None:
    controller = MasterlogTemplateController(ProjectSession())
    template = controller.create("Standard")

    with pytest.raises(ValueError, match="5 до 200"):
        controller.add_column(
            template.template_id,
            title="Bad",
            column_type="curves",
            width_mm=2.0,
        )
