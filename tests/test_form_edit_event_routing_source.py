from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _class_methods(relative: str, class_name: str) -> set[str]:
    tree = ast.parse((ROOT / relative).read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return {
                child.name
                for child in node.body
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
    raise AssertionError(f"class not found: {class_name}")


def test_f4_uses_one_oop_router_for_annotations_and_track_editing() -> None:
    source = (ROOT / "src/geoworkbench/tablet/tablet_view.py").read_text(
        encoding="utf-8"
    )

    assert "TabletInteractionRouter()" in source
    assert "AnnotationInteractionHandler(" in source
    assert "TrackEditInteractionHandler(" in source
    assert "self._interaction_router.register(self._annotation_interaction)" in source
    assert "self._interaction_router.register(self._track_edit_interaction)" in source
    assert "TabletEditModeCoordinator(" in source
    assert "self._edit_mode_coordinator.set_form_edit_enabled(requested)" in source


def test_track_selection_and_full_editor_are_not_owned_by_overlay() -> None:
    source = (ROOT / "src/geoworkbench/tablet/tablet_view.py").read_text(
        encoding="utf-8"
    )
    track_tool = (ROOT / "src/geoworkbench/tablet/track_edit_tool.py").read_text(
        encoding="utf-8"
    )

    assert "self.select_track(event.track_id, emit_signal=True)" in source
    assert "edit_track=self.track_full_edit_requested.emit" in source
    assert "InteractionResponse.pass_through()" in track_tool
    assert "self._edit_track(event.track_id)" in track_tool


def test_track_header_double_click_opens_full_editor() -> None:
    source = (ROOT / "src/geoworkbench/tablet/tablet_view.py").read_text(
        encoding="utf-8"
    )

    assert "edit_requested = Signal(str)" in source
    assert "self.edit_requested.emit(self.definition.track_id)" in source
    assert "track.edit_requested.connect(self.track_full_edit_requested.emit)" in source


def test_paint_overlay_has_no_native_mouse_capture_or_event_handlers() -> None:
    relative = "src/geoworkbench/tablet/annotation_graphics.py"
    source = (ROOT / relative).read_text(encoding="utf-8")
    methods = _class_methods(relative, "TabletAnnotationOverlay")
    overlay_source = source[source.index("class TabletAnnotationOverlay"):]

    assert "WA_TransparentForMouseEvents" in overlay_source
    assert "grabMouse(" not in overlay_source
    assert "releaseMouse(" not in overlay_source
    assert "def _build_sparse_paint_mask" in overlay_source
    assert "WA_TransparentForMouseEvents" in overlay_source
    assert "mousePressEvent" not in methods
    assert "mouseMoveEvent" not in methods
    assert "mouseReleaseEvent" not in methods
    assert "mouseDoubleClickEvent" not in methods


def test_lost_release_recovery_is_owned_by_watchdog() -> None:
    source = (ROOT / "src/geoworkbench/tablet/interaction_watchdog.py").read_text(
        encoding="utf-8"
    )
    tablet = (ROOT / "src/geoworkbench/tablet/tablet_view.py").read_text(
        encoding="utf-8"
    )

    assert "class TabletInteractionWatchdog" in source
    assert "QApplication.mouseButtons()" in source
    assert "self._recover_release()" in source
    assert "QEvent.Type.UngrabMouse" in tablet
    assert "self._interaction_router.cancel_active" in tablet
