from hashlib import sha256

import numpy as np
import pytest

from geoworkbench.domain.models import (
    Dataset,
    DatasetKind,
    DepthDomain,
    MasterlogColumnTemplate,
    MasterlogTemplate,
)
from geoworkbench.printing.image_assets import ImageAsset
from geoworkbench.project.masterlog_symbol_controller import MasterlogSymbolController
from geoworkbench.project.session import ProjectSession


SVG = b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><rect width="10" height="10" fill="#f00"/></svg>'


def make_controller() -> MasterlogSymbolController:
    dataset = Dataset(
        "dataset", "Log", DatasetKind.GTI, DepthDomain.MD, np.array([100.0, 200.0])
    )
    session = ProjectSession()
    session.add_dataset(dataset, "Well")
    dataset.upsert_curve("TG", np.array([1.0, 100.0]))
    template = MasterlogTemplate(
        "standard",
        "Standard",
        columns=[MasterlogColumnTemplate("gas", "Gas", "curves", 40.0, ["TG"])],
    )
    session.project.masterlog_templates[template.template_id] = template
    digest = sha256(SVG).hexdigest()
    asset = ImageAsset(f"sha256:{digest}", "show.svg", "image/svg+xml", SVG)
    session.image_assets[asset.asset_id] = asset
    session.dirty = False
    return MasterlogSymbolController(session)


def test_masterlog_symbol_crud_uses_depth_and_track_canvas_anchor() -> None:
    controller = make_controller()
    asset_ref = next(iter(controller.session.image_assets))

    created = controller.add(
        "standard",
        depth=150.0,
        column_id="gas",
        asset_ref=asset_ref,
        width_mm=8.0,
        height_mm=7.0,
        label="Show",
    )

    well = controller.session.current_well
    assert well is not None
    stored = well.canvas_objects[0]
    assert stored.object_type == "masterlog_symbol"
    assert stored.anchor_type == "depth"
    assert stored.track_id == "gas"
    assert stored.properties["template_id"] == "standard"

    updated = controller.update(
        created.object_id,
        template_id="standard",
        depth=160.0,
        column_id="gas",
        asset_ref=asset_ref,
        width_mm=9.0,
        height_mm=9.0,
        label="Updated",
    )
    assert updated.depth == 160.0
    assert controller.remove(created.object_id, "standard") == updated
    assert controller.available("standard") == ()


def test_masterlog_symbol_validates_references_range_and_history() -> None:
    controller = make_controller()
    asset_ref = next(iter(controller.session.image_assets))
    with pytest.raises(ValueError, match="Колонка"):
        controller.add(
            "standard", depth=150.0, column_id="missing", asset_ref=asset_ref,
            width_mm=8.0, height_mm=8.0,
        )
    with pytest.raises(ValueError, match="вне"):
        controller.add(
            "standard", depth=250.0, column_id="gas", asset_ref=asset_ref,
            width_mm=8.0, height_mm=8.0,
        )

    created = controller.add(
        "standard", depth=150.0, column_id="gas", asset_ref=asset_ref,
        width_mm=8.0, height_mm=8.0,
    )
    controller.remove(created.object_id, "standard")
    assert controller.undo() == "Удаление обозначения masterlog"
    assert controller.available("standard") == (created,)


def test_masterlog_symbol_supports_validated_interval_anchor() -> None:
    controller = make_controller()
    asset_ref = next(iter(controller.session.image_assets))

    created = controller.add(
        "standard",
        depth=125.0,
        bottom_depth=175.0,
        anchor_type="interval",
        column_id="gas",
        asset_ref=asset_ref,
        width_mm=10.0,
        height_mm=8.0,
        label="Zone",
    )

    assert created.anchor_type == "interval"
    assert created.top_depth == 125.0
    assert created.bottom_depth == 175.0
    assert controller.session.current_well is not None
    assert controller.session.current_well.canvas_objects[0].anchor_type == "interval"
    with pytest.raises(ValueError, match="Низ интервала"):
        controller.add(
            "standard",
            depth=175.0,
            bottom_depth=125.0,
            anchor_type="interval",
            column_id="gas",
            asset_ref=asset_ref,
            width_mm=8.0,
            height_mm=8.0,
        )
    assert controller.undo() == "Добавление обозначения masterlog"
    assert controller.available("standard") == ()
    controller.redo()
    assert controller.available("standard") == (created,)


def test_masterlog_symbol_supports_parameter_anchor_from_column_curve() -> None:
    controller = make_controller()
    asset_ref = next(iter(controller.session.image_assets))

    created = controller.add(
        "standard",
        depth=190.0,
        anchor_type="parameter",
        parameter_mnemonic="TG",
        column_id="gas",
        asset_ref=asset_ref,
        width_mm=8.0,
        height_mm=8.0,
    )

    assert created.anchor_type == "parameter"
    assert created.parameter_mnemonic == "TG"
    assert controller.session.current_well is not None
    assert controller.session.current_well.canvas_objects[0].parameter_mnemonic == "TG"
    with pytest.raises(ValueError, match="выбранную колонку"):
        controller.add(
            "standard",
            depth=150.0,
            anchor_type="parameter",
            parameter_mnemonic="ROP",
            column_id="gas",
            asset_ref=asset_ref,
            width_mm=8.0,
            height_mm=8.0,
        )
