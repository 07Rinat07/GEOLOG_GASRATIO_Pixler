"""Dependency-free guards for annotation hotfix structure.

The full interaction tests run with PySide6/pyqtgraph in the application test
environment.  These AST checks also run in minimal CI containers and prevent the
specific 0.7.15/0.7.16 regressions from being reintroduced by a misplaced method
or by removing the viewport routing guards.
"""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _classes(relative: str) -> dict[str, ast.ClassDef]:
    source = (ROOT / relative).read_text(encoding="utf-8")
    tree = ast.parse(source)
    return {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}


def _methods(node: ast.ClassDef) -> set[str]:
    return {
        child.name
        for child in node.body
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def test_axis_handler_belongs_to_annotation_dialog() -> None:
    classes = _classes("src/geoworkbench/ui/depth_annotations_dialog.py")

    assert "_axis_selection_changed" in _methods(classes["DepthAnnotationsDialog"])
    assert "_numeric_index_values" in _methods(classes["DepthAnnotationsDialog"])
    assert "_save_single_item" in _methods(classes["DepthAnnotationsDialog"])
    assert "_axis_selection_changed" not in _methods(classes["_ColorButton"])


def test_both_tablet_event_filters_protect_annotation_events() -> None:
    classes = _classes("src/geoworkbench/tablet/tablet_view.py")

    assert "_annotation_for_event" in _methods(classes["TabletTrackWidget"])
    assert "_annotation_item_for_mouse_event" in _methods(classes["TabletView"])

    source = (ROOT / "src/geoworkbench/tablet/tablet_view.py").read_text(encoding="utf-8")
    assert "Let QGraphicsView deliver the complete gesture/context" in source
    assert "deliver the event to TabletAnnotationItem" in source


def test_direct_creation_payload_contains_editable_geometry() -> None:
    source = (ROOT / "src/geoworkbench/tablet/tablet_view.py").read_text(encoding="utf-8")

    for fragment in (
        '"offset_x": offset_x',
        '"offset_y": offset_y',
        '"width": width',
        '"height": height',
    ):
        assert fragment in source


def test_main_window_reports_annotation_editor_failures() -> None:
    classes = _classes("src/geoworkbench/ui/main_window.py")

    assert "_open_annotation_dialog" in _methods(classes["MainWindow"])
    source = (ROOT / "src/geoworkbench/ui/main_window.py").read_text(encoding="utf-8")
    assert '"annotations.open_failed"' in source
    assert "never leave an F4 action silently dead" in source
