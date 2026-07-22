from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _method(name: str) -> ast.FunctionDef:
    source = (ROOT / "src/geoworkbench/tablet/annotation_graphics.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "TabletAnnotationOverlay":
            for child in node.body:
                if isinstance(child, ast.FunctionDef) and child.name == name:
                    return child
    raise AssertionError(name)


def test_full_canvas_overlay_is_never_exposed_as_native_window_region() -> None:
    source = (ROOT / "src/geoworkbench/tablet/annotation_graphics.py").read_text(encoding="utf-8")
    overlay = source[source.index("class TabletAnnotationOverlay"):]

    assert "self.setMask(QRegion())" in overlay
    assert "def _build_sparse_paint_mask" in overlay
    assert "QRegion(self._content_rect.toAlignedRect())" in overlay
    assert "helper.boundingRect().translated(anchor)" in overlay
    assert "region.intersected(content)" in overlay
    assert "clearMask(" not in overlay


def test_mask_changes_are_coalesced_and_not_applied_in_pointer_move() -> None:
    update = ast.unparse(_method("update_interaction"))
    schedule = ast.unparse(_method("_schedule_paint_mask"))

    assert "self._schedule_paint_mask()" in update
    assert "setMask" not in update
    assert "self._mask_refresh_timer.start()" in schedule


def test_mask_does_not_restore_mouse_ownership_to_overlay() -> None:
    source = (ROOT / "src/geoworkbench/tablet/annotation_graphics.py").read_text(encoding="utf-8")
    overlay = source[source.index("class TabletAnnotationOverlay"):]

    assert "WA_TransparentForMouseEvents" in overlay
    assert "grabMouse(" not in overlay
    assert "releaseMouse(" not in overlay
    assert "def mousePressEvent" not in overlay
