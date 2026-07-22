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


def test_full_canvas_overlay_is_hidden_and_never_paints() -> None:
    source = (ROOT / "src/geoworkbench/tablet/annotation_graphics.py").read_text(encoding="utf-8")
    overlay = source[source.index("class TabletAnnotationOverlay"):]

    assert "self.hide()" in overlay
    assert "def paintEvent" in overlay
    assert "Deliberately empty" in overlay
    assert "WA_TranslucentBackground" not in overlay
    assert "setMask(" not in overlay
    assert "QRegion" not in overlay


def test_annotations_are_rendered_as_small_per_object_sprites() -> None:
    source = (ROOT / "src/geoworkbench/tablet/annotation_graphics.py").read_text(encoding="utf-8")
    overlay = source[source.index("class TabletAnnotationOverlay"):]

    assert "self._sprites: dict[str, QLabel]" in overlay
    assert "sprite = QLabel(self._canvas)" in overlay
    assert "full_bounds = helper.boundingRect().translated(anchor)" in overlay
    assert "visible_bounds = full_bounds.intersected(self._content_rect)" in overlay
    assert "pixmap.fill(Qt.GlobalColor.transparent)" in overlay


def test_pointer_move_updates_only_active_sprite() -> None:
    update = ast.unparse(_method("update_interaction"))
    assert "self._refresh_sprite(gesture.annotation_id)" in update
    assert "setMask" not in update
    assert "set_entries" not in update


def test_sprite_widgets_never_own_mouse_input() -> None:
    source = (ROOT / "src/geoworkbench/tablet/annotation_graphics.py").read_text(encoding="utf-8")
    overlay = source[source.index("class TabletAnnotationOverlay"):]
    assert "WA_TransparentForMouseEvents" in overlay
    assert "grabMouse(" not in overlay
    assert "releaseMouse(" not in overlay
    assert "def mousePressEvent" not in overlay
