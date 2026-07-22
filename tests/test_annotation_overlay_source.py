from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_tablet_uses_one_canvas_wide_annotation_overlay() -> None:
    source = (ROOT / "src/geoworkbench/tablet/tablet_view.py").read_text(encoding="utf-8")
    assert "TabletAnnotationOverlay(self._tracks_container)" in source
    assert "self._refresh_annotation_overlay()" in source
    assert "paint_annotations_for_track" in source
    assert "annotation_items: dict[str, TabletAnnotationItem] = {}" in source


def test_annotation_overlay_supports_selection_and_eight_resize_handles() -> None:
    source = (ROOT / "src/geoworkbench/tablet/annotation_graphics.py").read_text(
        encoding="utf-8"
    )
    assert "class TabletAnnotationOverlay" in source
    assert '"nw"' in source and '"se"' in source
    assert '"n"' in source and '"s"' in source
    assert '"e"' in source and '"w"' in source
    assert "mouseDoubleClickEvent" in source
    assert "selection_changed = Signal(object)" in source
    assert "self.grabMouse()" in source
    assert "self.releaseMouse()" in source
    assert "def keyPressEvent" in source
    assert "QPainterPathStroker" in source


def test_annotations_do_not_clutter_project_tree() -> None:
    source = (ROOT / "src/geoworkbench/ui/main_window.py").read_text(encoding="utf-8")
    refresh_tree = source[source.index("def _refresh_tree"):source.index("def _activate_tree_item")]
    assert '("annotation", well.well_id' not in refresh_tree
    assert "dedicated F4 layer" in refresh_tree
    assert "annotation_edit_selected_action" in source
    assert "annotation_delete_selected_action" in source


def test_depth_navigation_remaps_annotation_anchors() -> None:
    tablet_source = (ROOT / "src/geoworkbench/tablet/tablet_view.py").read_text(
        encoding="utf-8"
    )
    overlay_source = (ROOT / "src/geoworkbench/tablet/annotation_graphics.py").read_text(
        encoding="utf-8"
    )

    assert "def _refresh_annotation_overlay_anchors" in tablet_source
    assert "self._annotation_overlay.set_anchor_positions(anchors)" in tablet_source
    assert tablet_source.count("self._refresh_annotation_overlay_anchors()") >= 2
    assert "def set_anchor_positions" in overlay_source
    assert "positions only; it never changes text, style, size or saved offsets" in overlay_source


def test_anchor_refresh_reuses_existing_annotation_helpers() -> None:
    source = (ROOT / "src/geoworkbench/tablet/annotation_graphics.py").read_text(
        encoding="utf-8"
    )

    assert "old_entries = self._entries" in source
    assert "existing = old_entries.get(annotation_id)" in source
    assert "if annotation_id != self._drag_id" in source
