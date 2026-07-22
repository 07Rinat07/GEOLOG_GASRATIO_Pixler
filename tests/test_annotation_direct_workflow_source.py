from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_annotations_are_clipped_to_graph_body_below_headers() -> None:
    source = (ROOT / "src/geoworkbench/tablet/annotation_graphics.py").read_text(
        encoding="utf-8"
    )
    tablet = (ROOT / "src/geoworkbench/tablet/tablet_view.py").read_text(
        encoding="utf-8"
    )

    assert "def set_content_rect" in source
    assert "painter.setClipRect(self._content_rect" in source
    assert "WA_TransparentForMouseEvents" in source
    assert "visible_bounds = full_bounds.intersected(self._content_rect)" in source
    assert "target = visible_bounds.toAlignedRect()" in source
    assert "setMask(" not in source[source.index("class TabletAnnotationOverlay"):]
    assert "def _anchor_is_visible" in source
    assert "plot.getViewBox().sceneBoundingRect()" in tablet
    assert "self._annotation_overlay.set_content_rect(content_rect)" in tablet


def test_f4_tools_create_at_the_mouse_position_without_opening_dialog_first() -> None:
    tablet = (ROOT / "src/geoworkbench/tablet/tablet_view.py").read_text(
        encoding="utf-8"
    )
    main_window = (ROOT / "src/geoworkbench/ui/main_window.py").read_text(
        encoding="utf-8"
    )

    assert "def set_annotation_tool" in tablet
    assert "def _direct_annotation_payload" in tablet
    assert 'payload["direct_create"]' in tablet
    assert "event.position().x()" in tablet
    assert "event.position().y()" in tablet
    assert "self.annotation_add_requested.emit(payload)" in tablet
    assert "action.setCheckable(True)" in main_window
    assert "self.depth_annotation_controller.add_annotation(**values)" in main_window
    assert "self.tablet_view.select_annotation(record.annotation_id)" in main_window


def test_direct_creation_keeps_initial_box_inside_plot_viewport() -> None:
    source = (ROOT / "src/geoworkbench/tablet/tablet_view.py").read_text(
        encoding="utf-8"
    )

    assert "viewport_height = max(1.0, float(plot.viewport().height()))" in source
    assert "if local_y + offset_y < margin" in source
    assert "elif local_y + offset_y + box_height > viewport_height - margin" in source
