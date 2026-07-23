from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_main_window_does_not_mutate_serialized_project_collections_directly() -> None:
    source = _source("src/geoworkbench/ui/main_window.py")

    forbidden = (
        "self.session.dirty =",
        "well.datasets.pop(",
        "self.session.tablet_layouts.pop(",
        "self.session.source_documents.pop(",
        "self.session.import_reports.pop(",
        "self.session.set_current_tablet_layout(",
        "result.name =",
    )
    for pattern in forbidden:
        assert pattern not in source

    assert "self.derived_dataset_controller.checkpoint()" in source
    assert "self.derived_dataset_controller.rollback(checkpoint)" in source
    assert "self.tablet_controller.install_layout(" in source
    assert "self.tablet_controller.move_track_to_index(" in source


def test_tablet_view_routes_serializable_layout_mutations_through_headless_boundary() -> None:
    source = _source("src/geoworkbench/tablet/tablet_view.py")

    forbidden = (
        "definition.width =",
        "self._layout_model.set_visible_depth(",
        "self._layout_model.set_vertical_index(",
        "self._layout_model.move_track(",
        "self._layout_model.add_track(",
        "self._layout_model.remove_track(",
        "self._layout_model.vertical_index_id =",
    )
    for pattern in forbidden:
        assert pattern not in source

    assert "TabletLayoutMutationController" in source
    assert "self._layout_mutations.set_track_width(" in source
    assert "self._layout_mutations.move_track_to_index(" in source
    assert "self._layout_mutations.set_visible_depth(" in source
    assert "self._layout_mutations.set_vertical_index(" in source

    resize_body = source.split("    def _resize_track_from_widget", 1)[1].split(
        "    def _start_track_header_drag", 1
    )[0]
    assert resize_body.index("track_width_change_requested.emit") < resize_body.index(
        "_layout_mutations.set_track_width"
    )

    move_body = source.split("    def move_track_with_history", 1)[1].split(
        "    def _reorder_rendered_tracks", 1
    )[0]
    assert move_body.index("track_order_change_requested.emit") < move_body.index(
        "_layout_mutations.move_track_to_index"
    )


def test_masterlog_header_dialog_installs_assets_through_controller() -> None:
    source = _source("src/geoworkbench/ui/masterlog_header_dialog.py")

    assert "self.controller.install_image_assets(dialog.imported_assets)" in source
    assert "except (ImageAssetError, ValueError) as exc:" in source
    assert "self.controller.session.image_assets.update(" not in source
    assert "self.controller.session.dirty =" not in source


def test_track_editor_only_mutates_a_deepcopied_draft() -> None:
    source = _source("src/geoworkbench/ui/tablet_track_editor_dialog.py")

    assert "self.track = deepcopy(track)" in source
    assert "self.session" not in source
    assert "session.project" not in source
