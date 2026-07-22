from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _method(relative: str, class_name: str, method_name: str) -> ast.FunctionDef:
    tree = ast.parse((ROOT / relative).read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for child in node.body:
                if isinstance(child, ast.FunctionDef) and child.name == method_name:
                    return child
    raise AssertionError(f"method not found: {class_name}.{method_name}")


def _called_names(node: ast.AST) -> set[str]:
    result: set[str] = set()
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        func = child.func
        if isinstance(func, ast.Attribute):
            result.add(func.attr)
        elif isinstance(func, ast.Name):
            result.add(func.id)
    return result


def test_canvas_object_sync_does_not_rebuild_complete_tablet() -> None:
    method = _method(
        "src/geoworkbench/tablet/tablet_view.py",
        "TabletView",
        "set_canvas_objects",
    )
    calls = _called_names(method)
    assert "refresh_view" not in calls
    assert "_refresh_annotation_overlay" in calls


def test_geometry_commit_does_not_refresh_annotation_layer_again() -> None:
    method = _method(
        "src/geoworkbench/ui/main_window.py",
        "MainWindow",
        "_update_annotation_geometry_from_tablet",
    )
    source = ast.unparse(method)
    success_branch = source.split("except", 1)[-1]
    assert "set_geometry" in source
    assert "self._update_title()" in success_branch
    assert source.rstrip().endswith("self._update_title()")


def test_pointer_move_repaints_only_annotation_dirty_rectangle() -> None:
    method = _method(
        "src/geoworkbench/tablet/annotation_graphics.py",
        "TabletAnnotationOverlay",
        "update_interaction",
    )
    calls = _called_names(method)
    assert "set_entries" not in calls
    assert "setMask" not in calls
    assert "_refresh_sprite" in calls
    assert "_raise_sprites" in calls


def test_overlay_is_mouse_transparent_and_uses_small_sprites() -> None:
    source = (
        ROOT / "src/geoworkbench/tablet/annotation_graphics.py"
    ).read_text(encoding="utf-8")
    overlay_source = source[source.index("class TabletAnnotationOverlay"):]

    assert "WA_TransparentForMouseEvents" in overlay_source
    assert "self.hide()" in overlay_source
    assert "sprite = QLabel(self._canvas)" in overlay_source
    assert "sprite.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)" in overlay_source
    assert "setMask(" not in overlay_source
    assert "WA_TranslucentBackground" not in overlay_source
    assert "grabMouse(" not in overlay_source


def test_release_commits_only_meaningful_geometry_changes() -> None:
    source = (
        ROOT / "src/geoworkbench/tablet/annotation_graphics.py"
    ).read_text(encoding="utf-8")
    handler = (
        ROOT / "src/geoworkbench/tablet/annotation_tool.py"
    ).read_text(encoding="utf-8")

    assert "def finish_interaction" in source
    assert "_geometry_differs(gesture.start_geometry, current)" in source
    assert "if PointerButton.LEFT not in event.pressed_buttons" in handler
    assert "InputEventKind.POINTER_RELEASE" in handler


def test_sprite_pixmap_is_explicitly_cleared_to_transparent() -> None:
    source = (
        ROOT / "src/geoworkbench/tablet/annotation_graphics.py"
    ).read_text(encoding="utf-8")
    assert "pixmap.fill(Qt.GlobalColor.transparent)" in source
    assert "sprite.setPixmap(pixmap)" in source

