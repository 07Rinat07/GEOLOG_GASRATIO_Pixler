import json
from hashlib import sha256
from pathlib import Path

import numpy as np

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.form_constructor.asset_install import factory_symbol_variant_path
from geoworkbench.form_constructor.asset_registry import ConstructorAssetRegistry
from geoworkbench.printing.image_assets import ImageAsset, PNG_MEDIA_TYPE
from geoworkbench.project.annotation_controller import DepthAnnotationController
from geoworkbench.project.annotation_schema import AnnotationAnchor, AnnotationKind
from geoworkbench.project.session import ProjectSession
from geoworkbench.project.symbol_insertion import SymbolInsertionSelection
from geoworkbench.storage.atomic_json import save_project
from geoworkbench.storage.project_codec import load_project_document
from geoworkbench.tablet import TabletLayout, TrackDefinition, TrackKind


ASSET_ROOT = Path(__file__).resolve().parents[1] / "resources" / "constructor_assets"


def make_controller() -> DepthAnnotationController:
    dataset = Dataset(
        "dataset",
        "Well",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([100.0, 150.0, 200.0]),
    )
    dataset.upsert_curve("ROP", np.array([10.0, 20.0, 30.0]), unit="m/h")
    session = ProjectSession()
    session.add_dataset(dataset)
    session.set_current_tablet_layout(TabletLayout(
        tracks=[
            TrackDefinition(
                "drilling",
                "Drilling",
                TrackKind.CURVE,
                curve_mnemonics=["ROP"],
            )
        ]
    ))
    return DepthAnnotationController(session)

def test_catalog_symbol_variant_resolves_transparent_and_original_assets() -> None:
    registry = ConstructorAssetRegistry.from_root(ASSET_ROOT)
    symbols = registry.all(kind="depth_symbol")

    assert len(symbols) == 19
    for symbol in symbols:
        transparent = factory_symbol_variant_path(symbol, transparent_background=True)
        original = factory_symbol_variant_path(symbol, transparent_background=False)

        assert transparent.name == f"{symbol.asset_id}.png"
        assert transparent.parent.name == "transparent"
        assert original.name == f"{symbol.asset_id}.bmp"
        assert original.parent.name == "originals"
        assert transparent.is_file()
        assert original.is_file()

def test_symbol_selection_builds_existing_annotation_contract() -> None:
    registry = ConstructorAssetRegistry.from_root(ASSET_ROOT)
    symbol = registry.get("symbol-bit")
    selection = SymbolInsertionSelection(
        symbol=symbol,
        transparent_background=False,
        track_id="drilling",
        parameter_mnemonic="ROP",
        depth=150.0,
        x_fraction=0.4,
        offset_x=-36.0,
        offset_y=-24.0,
        width=72.0,
        height=48.0,
    )

    values = selection.annotation_values(asset_ref="sha256:test")

    assert values["kind"] is AnnotationKind.SYMBOL
    assert values["anchor"] is AnnotationAnchor.CURVE
    assert values["track_id"] == "drilling"
    assert values["parameter_mnemonic"] == "ROP"
    assert values["symbol_id"] == "symbol-bit"
    assert values["transparent_background"] is False
    assert values["asset_ref"] == "sha256:test"

def test_symbol_annotation_persists_catalog_and_background_metadata() -> None:
    controller = make_controller()
    image = ImageAsset(
        "sha256:test-symbol",
        "Bit-transparent.png",
        PNG_MEDIA_TYPE,
        b"not-validated-by-controller",
    )
    controller.session.image_assets[image.asset_id] = image

    created = controller.add_annotation(
        kind=AnnotationKind.SYMBOL,
        anchor=AnnotationAnchor.CURVE,
        track_id="drilling",
        depth=150.0,
        parameter_mnemonic="ROP",
        x_fraction=0.45,
        offset_x=-32.0,
        offset_y=-32.0,
        width=64.0,
        height=64.0,
        asset_ref=image.asset_id,
        symbol_id="symbol-bit",
        transparent_background=True,
    )

    assert created.kind is AnnotationKind.SYMBOL
    assert created.anchor is AnnotationAnchor.CURVE
    assert created.parameter_mnemonic == "ROP"
    assert created.parameter_value == 20.0
    assert created.symbol_id == "symbol-bit"
    assert created.transparent_background is True

    stored = controller.session.current_well.canvas_objects[-1]
    assert stored.properties["symbol_id"] == "symbol-bit"
    assert stored.properties["transparent_background"] is True

    duplicate = controller.duplicate(created.annotation_id)
    assert duplicate.symbol_id == created.symbol_id
    assert duplicate.transparent_background is True

def test_symbol_annotation_survives_project_round_trip(tmp_path: Path) -> None:
    controller = make_controller()
    registry = ConstructorAssetRegistry.from_root(ASSET_ROOT)
    symbol = registry.get("symbol-bit")
    payload = factory_symbol_variant_path(symbol).read_bytes()
    digest = sha256(payload).hexdigest()
    image = ImageAsset(
        f"sha256:{digest}",
        "Bit-transparent.png",
        PNG_MEDIA_TYPE,
        payload,
    )
    controller.session.image_assets[image.asset_id] = image
    created = controller.add_annotation(
        kind=AnnotationKind.SYMBOL,
        anchor=AnnotationAnchor.DEPTH,
        track_id="drilling",
        depth=150.0,
        x_fraction=0.5,
        offset_x=-32.0,
        offset_y=-32.0,
        width=64.0,
        height=64.0,
        asset_ref=image.asset_id,
        symbol_id="symbol-bit",
        transparent_background=True,
    )

    target = tmp_path / "symbol-round-trip.geolog.json"
    save_project(
        controller.session.project,
        target,
        tablet_layouts=controller.session.tablet_layouts,
        image_assets=controller.session.image_assets,
    )
    loaded = load_project_document(target)
    well_id = controller.session.current_well.well_id
    loaded_item = loaded.project.wells[well_id].canvas_objects[-1]

    assert loaded_item.object_id == created.annotation_id
    assert loaded_item.properties["kind"] == AnnotationKind.SYMBOL.value
    assert loaded_item.properties["symbol_id"] == "symbol-bit"
    assert loaded_item.properties["transparent_background"] is True
    assert loaded_item.properties["asset_ref"] in loaded.image_assets

def test_symbol_insertion_ui_is_wired_to_toolbar_context_and_mouse_geometry() -> None:
    main_window = Path("src/geoworkbench/ui/main_window.py").read_text(encoding="utf-8")
    tablet_view = Path("src/geoworkbench/tablet/tablet_view.py").read_text(encoding="utf-8")
    dialog = Path("src/geoworkbench/ui/symbol_insertion_dialog.py").read_text(encoding="utf-8")
    overlay = Path("src/geoworkbench/tablet/annotation_graphics.py").read_text(encoding="utf-8")

    assert "self.annotation_symbol_action" in main_window
    assert "_open_symbol_insertion_dialog" in main_window
    assert "annotations.add_symbol_action" in tablet_view
    assert "AnnotationKind.SYMBOL" in tablet_view
    assert "symbol-transparent-checkbox" in dialog
    assert "symbol-depth-input" in dialog
    assert "symbol-parameter-input" in dialog
    assert "resize_handle_rects" in overlay
    assert "begin_interaction" in overlay

def test_symbol_insertion_has_complete_ru_kk_en_localization() -> None:
    required = {
        "annotations.toolbar_symbol",
        "annotations.tool_symbol_hint",
        "annotations.add_symbol_action",
        "symbol_insert.title",
        "symbol_insert.hint",
        "symbol_insert.search_placeholder",
        "symbol_insert.transparent",
        "symbol_insert.track",
        "symbol_insert.parameter",
        "symbol_insert.depth",
        "symbol_insert.width",
        "symbol_insert.height",
        "symbol_insert.mouse_hint",
        "symbol_insert.insert",
        "symbol_insert.inserted_status",
    }
    resources = Path("src/geoworkbench/resources/i18n")
    for language in ("ru", "kk", "en"):
        payload = json.loads((resources / f"{language}.json").read_text(encoding="utf-8"))
        missing = sorted(required.difference(payload))
        assert not missing, f"{language}: missing localization keys: {missing}"
