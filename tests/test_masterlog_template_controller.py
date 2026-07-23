from hashlib import sha256

import pytest

import numpy as np

from geoworkbench.domain.models import (
    CanvasObject,
    Dataset,
    DatasetKind,
    DepthDomain,
    MasterlogColumnTemplate,
    MasterlogCurveStyle,
    Well,
)
from geoworkbench.project.masterlog_template_controller import MasterlogTemplateController
from geoworkbench.printing.image_assets import ImageAsset, ImageAssetError
from geoworkbench.project.session import ProjectSession


def test_masterlog_template_lifecycle_uses_independent_copy_and_versions() -> None:
    session = ProjectSession()
    controller = MasterlogTemplateController(session)
    source = controller.create("Standard")
    source.columns.append(MasterlogColumnTemplate("gas", "Gas", "curves", 35.0, ["C1"]))

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


def test_masterlog_template_saves_dataset_specific_curve_bindings() -> None:
    controller = MasterlogTemplateController(ProjectSession())
    template = controller.create("Customer form")
    template.columns.append(MasterlogColumnTemplate("gas", "Gas", "curves", 40.0, ["TG", "C1"]))
    dataset = Dataset(
        "foreign", "Vendor LAS", DatasetKind.GTI, DepthDomain.MD, np.array([1.0, 2.0])
    )
    total = dataset.upsert_curve("GAS_TOTAL_VENDOR", np.array([10.0, 20.0]))
    methane = dataset.upsert_curve("METH_VENDOR", np.array([5.0, 8.0]))

    saved = controller.save_curve_bindings(
        template.template_id,
        dataset,
        {"TG": total.metadata.curve_id, "C1": methane.metadata.curve_id},
    )

    assert controller.required_curve_mnemonics(template.template_id) == ("TG", "C1")
    assert controller.curve_bindings(template.template_id, dataset) == saved
    assert template.version == 2
    with pytest.raises(ValueError, match="Не сопоставлены"):
        controller.save_curve_bindings(
            template.template_id, dataset, {"TG": total.metadata.curve_id}
        )


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
        curve_styles={
            "C1": MasterlogCurveStyle("#abcdef", 3.0, "dot", 0.2, 200.0),
            "STALE": MasterlogCurveStyle(),
        },
        grid_x=True,
        grid_y=True,
        grid_major_divisions=4,
        grid_minor_divisions=5,
        grid_alpha=0.3,
    )

    assert second.curve_mnemonics == ["C1", "C2"]
    assert second.x_scale == "logarithmic"
    assert second.x_min == 0.1
    assert second.show_legend is False
    assert second.line_color == "#112233"
    assert second.line_width == 2.5
    assert second.line_style == "dash"
    assert second.curve_styles == {"C1": MasterlogCurveStyle("#abcdef", 3.0, "dot", 0.2, 200.0)}
    assert second.grid_x is True
    assert second.grid_y is True
    assert second.grid_major_divisions == 4
    assert second.grid_minor_divisions == 5
    assert second.grid_alpha == 0.3
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
    assert second.curve_styles["C1"].color == "#abcdef"
    assert [column.column_id for column in template.columns] == [
        second.column_id,
        first.column_id,
    ]
    controller.remove_column(template.template_id, second.column_id)
    assert [column.column_id for column in template.columns] == [first.column_id]
    assert template.version == 6


def test_masterlog_column_update_preserves_grid_when_omitted() -> None:
    controller = MasterlogTemplateController(ProjectSession())
    template = controller.create("Standard")
    column = controller.add_column(
        template.template_id,
        title="Gas",
        column_type="curves",
        width_mm=35.0,
        grid_x=True,
        grid_y=True,
        grid_major_divisions=4,
        grid_minor_divisions=8,
        grid_alpha=0.4,
    )

    updated = controller.update_column(
        template.template_id,
        column.column_id,
        title="Gas curves",
        column_type="curves",
        width_mm=40.0,
        curve_mnemonics=[],
    )

    assert updated.grid_x is True
    assert updated.grid_y is True
    assert updated.grid_major_divisions == 4
    assert updated.grid_minor_divisions == 8
    assert updated.grid_alpha == 0.4


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


@pytest.mark.parametrize(
    ("grid_settings", "message"),
    [
        ({"grid_major_divisions": 0}, "от 1 до 20"),
        ({"grid_minor_divisions": 21}, "от 1 до 20"),
        ({"grid_alpha": 1.1}, "от 0 до 1"),
    ],
)
def test_masterlog_column_rejects_invalid_grid_settings(
    grid_settings: dict[str, int | float], message: str
) -> None:
    controller = MasterlogTemplateController(ProjectSession())
    template = controller.create("Standard")

    with pytest.raises(ValueError, match=message):
        controller.add_column(
            template.template_id,
            title="Gas",
            column_type="curves",
            width_mm=30.0,
            **grid_settings,
        )


def test_masterlog_column_rejects_non_positive_curve_range_for_log_scale() -> None:
    controller = MasterlogTemplateController(ProjectSession())
    template = controller.create("Standard")

    with pytest.raises(ValueError, match="положительным"):
        controller.add_column(
            template.template_id,
            title="Gas",
            column_type="curves",
            width_mm=30.0,
            curve_mnemonics=["TG"],
            x_scale="logarithmic",
            curve_styles={"TG": MasterlogCurveStyle(x_min=0.0, x_max=100.0)},
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


def test_masterlog_header_accepts_dynamic_lithology_legend() -> None:
    controller = MasterlogTemplateController(ProjectSession())
    template = controller.create("Standard")

    element = controller.add_header_element(
        template.template_id,
        element_type="lithology_legend",
        x_mm=5.0,
        y_mm=35.0,
        width_mm=200.0,
        height_mm=22.0,
        properties={"scope": "used", "columns": 5, "show_code": True},
    )

    assert element.element_type == "lithology_legend"
    assert element.properties["scope"] == "used"


def test_masterlog_template_controller_protects_referenced_image_asset() -> None:
    session = ProjectSession()
    controller = MasterlogTemplateController(session)
    payload = b"\x89PNG\r\n\x1a\nasset"
    digest = sha256(payload).hexdigest()
    asset = ImageAsset(f"sha256:{digest}", "logo.png", "image/png", payload)
    session.image_assets[asset.asset_id] = asset
    template = controller.create("Standard")
    element = controller.add_header_element(
        template.template_id,
        element_type="image",
        x_mm=0,
        y_mm=0,
        width_mm=20,
        height_mm=10,
        properties={"asset_ref": asset.asset_id},
    )

    assert controller.image_asset_references(asset.asset_id) == ("Standard",)
    with pytest.raises(ValueError, match="Standard"):
        controller.remove_image_asset(asset.asset_id)

    controller.remove_header_element(template.template_id, element.element_id)
    assert controller.remove_image_asset(asset.asset_id) is asset
    assert session.dirty


def test_masterlog_template_controller_renames_image_metadata_without_changing_id() -> None:
    session = ProjectSession()
    controller = MasterlogTemplateController(session)
    payload = b"\x89PNG\r\n\x1a\nasset"
    digest = sha256(payload).hexdigest()
    asset = ImageAsset(f"sha256:{digest}", "logo.png", "image/png", payload)
    session.image_assets[asset.asset_id] = asset

    renamed = controller.rename_image_asset(asset.asset_id, "  Operator logo  ")

    assert renamed.asset_id == asset.asset_id
    assert renamed.payload == asset.payload
    assert renamed.original_name == "Operator logo"
    with pytest.raises(ValueError):
        controller.rename_image_asset(asset.asset_id, "../logo.png")


def test_masterlog_template_controller_installs_content_addressed_asset_once() -> None:
    session = ProjectSession()
    controller = MasterlogTemplateController(session)
    payload = b"\x89PNG\r\n\x1a\nasset"
    digest = sha256(payload).hexdigest()
    asset = ImageAsset(f"sha256:{digest}", "symbol.png", "image/png", payload)

    assert controller.install_image_asset(asset) is asset
    session.dirty = False
    assert controller.install_image_asset(asset) is asset
    assert len(session.image_assets) == 1
    assert not session.dirty


def test_masterlog_template_controller_protects_template_and_asset_used_by_depth_symbol() -> None:
    session = ProjectSession()
    controller = MasterlogTemplateController(session)
    template = controller.create("Standard")
    payload = b"\x89PNG\r\n\x1a\nasset"
    digest = sha256(payload).hexdigest()
    asset = ImageAsset(f"sha256:{digest}", "symbol.png", "image/png", payload)
    session.image_assets[asset.asset_id] = asset
    well = Well("well", "Well")
    well.canvas_objects.append(
        CanvasObject(
            "show",
            "masterlog_symbol",
            "depth",
            0.0,
            100.0,
            8.0,
            8.0,
            top_depth=100.0,
            track_id="gas",
            properties={"template_id": template.template_id, "asset_ref": asset.asset_id},
        )
    )
    session.project.wells[well.well_id] = well

    assert controller.image_asset_references(asset.asset_id) == ("Standard",)
    with pytest.raises(ValueError, match="обозначениями"):
        controller.delete(template.template_id)
    with pytest.raises(ValueError, match="Standard"):
        controller.remove_image_asset(asset.asset_id)


def test_masterlog_template_controller_configures_page_geometry() -> None:
    controller = MasterlogTemplateController(ProjectSession())
    template = controller.create("Standard")

    updated = controller.configure_page(
        template.template_id,
        page_format="custom",
        depth_scale=200,
        header_height_mm=35.0,
        custom_width_mm=250.0,
        custom_height_mm=500.0,
        orientation="landscape",
    )

    assert updated.page_format == "custom"
    assert updated.depth_scale == 200
    assert updated.header_height_mm == 35.0
    assert updated.properties["custom_width_mm"] == 250.0
    assert updated.properties["custom_height_mm"] == 500.0
    assert updated.properties["orientation"] == "landscape"
    assert updated.version == 2
    with pytest.raises(ValueError):
        controller.configure_page(
            template.template_id,
            page_format="custom",
            depth_scale=5,
            header_height_mm=35.0,
            custom_width_mm=250.0,
            custom_height_mm=500.0,
        )


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


def test_masterlog_template_controller_installs_image_asset_batch_atomically() -> None:
    session = ProjectSession()
    controller = MasterlogTemplateController(session)
    payload = b"\x89PNG\r\n\x1a\nsafe"
    digest = sha256(payload).hexdigest()
    asset = ImageAsset(f"sha256:{digest}", "logo.png", "image/png", payload)

    installed = controller.install_image_assets({asset.asset_id: asset})

    assert installed == (asset,)
    assert session.image_assets == {asset.asset_id: asset}
    assert session.dirty is True

    session.dirty = False
    assert controller.install_image_assets({asset.asset_id: asset}) == (asset,)
    assert session.dirty is False


def test_masterlog_template_controller_rejects_asset_batch_without_partial_install() -> None:
    session = ProjectSession()
    controller = MasterlogTemplateController(session)
    existing_payload = b"\x89PNG\r\n\x1a\nexisting"
    existing_digest = sha256(existing_payload).hexdigest()
    existing = ImageAsset(
        f"sha256:{existing_digest}",
        "existing.png",
        "image/png",
        existing_payload,
    )
    controller.install_image_asset(existing)
    session.dirty = False

    new_payload = b"\x89PNG\r\n\x1a\nnew"
    new_digest = sha256(new_payload).hexdigest()
    new_asset = ImageAsset(
        f"sha256:{new_digest}",
        "new.png",
        "image/png",
        new_payload,
    )
    conflicting = ImageAsset(
        existing.asset_id,
        "conflict.png",
        "image/png",
        b"\x89PNG\r\n\x1a\nconflict",
    )

    with pytest.raises(ImageAssetError, match="SHA-256 содержимого"):
        controller.install_image_assets(
            {
                new_asset.asset_id: new_asset,
                conflicting.asset_id: conflicting,
            }
        )

    assert session.image_assets == {existing.asset_id: existing}
    assert session.dirty is False
