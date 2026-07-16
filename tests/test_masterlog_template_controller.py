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
        x_scale="logarithmic",
        x_min=0.1,
        x_max=1000.0,
        show_legend=False,
        line_color="#112233",
        line_width=2.5,
        line_style="dash",
    )

    assert second.curve_mnemonics == ["C1", "C2"]
    assert second.x_scale == "logarithmic"
    assert second.x_min == 0.1
    assert second.show_legend is False
    assert second.line_color == "#112233"
    assert second.line_width == 2.5
    assert second.line_style == "dash"
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


def test_masterlog_column_rejects_invalid_logarithmic_range() -> None:
    controller = MasterlogTemplateController(ProjectSession())
    template = controller.create("Standard")

    with pytest.raises(ValueError, match="положительным"):
        controller.add_column(
            template.template_id,
            title="Gas",
            column_type="curves",
            width_mm=30.0,
            x_scale="logarithmic",
            x_min=0.0,
            x_max=100.0,
        )


def test_masterlog_column_rejects_invalid_line_style() -> None:
    controller = MasterlogTemplateController(ProjectSession())
    template = controller.create("Standard")

    with pytest.raises(ValueError, match="RRGGBB"):
        controller.add_column(
            template.template_id,
            title="Gas",
            column_type="curves",
            width_mm=30.0,
            line_color="blue",
        )


def test_masterlog_template_controller_manages_header_elements() -> None:
    controller = MasterlogTemplateController(ProjectSession())
    template = controller.create("Standard")
    title = controller.add_header_element(
        template.template_id,
        element_type="text",
        x_mm=5.0,
        y_mm=5.0,
        width_mm=80.0,
        height_mm=10.0,
        properties={"text": "Masterlog"},
    )
    logo = controller.add_header_element(
        template.template_id,
        element_type="image",
        x_mm=90.0,
        y_mm=5.0,
        width_mm=30.0,
        height_mm=20.0,
        properties={"asset_ref": "sha256:logo"},
    )

    assert controller.move_header_element(template.template_id, logo.element_id, -1)
    updated = controller.update_header_element(
        template.template_id,
        title.element_id,
        element_type="field",
        x_mm=5.0,
        y_mm=6.0,
        width_mm=80.0,
        height_mm=10.0,
        properties={"field": "well.name"},
    )
    assert updated.element_type == "field"
    assert updated.properties == {"field": "well.name"}
    controller.remove_header_element(template.template_id, logo.element_id)
    assert [item.element_id for item in template.header_elements] == [title.element_id]
    assert template.version == 6


@pytest.mark.parametrize(
    ("element_type", "x_mm", "width_mm"),
    [("script", 0.0, 10.0), ("text", -1.0, 10.0), ("text", 0.0, 0.0)],
)
def test_masterlog_header_rejects_unsafe_type_and_geometry(
    element_type: str, x_mm: float, width_mm: float
) -> None:
    controller = MasterlogTemplateController(ProjectSession())
    template = controller.create("Standard")

    with pytest.raises(ValueError):
        controller.add_header_element(
            template.template_id,
            element_type=element_type,
            x_mm=x_mm,
            y_mm=0.0,
            width_mm=width_mm,
            height_mm=10.0,
        )
