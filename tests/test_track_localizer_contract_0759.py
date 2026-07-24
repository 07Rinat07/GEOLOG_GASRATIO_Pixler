from __future__ import annotations

import ast
from pathlib import Path


SOURCE = Path("src/geoworkbench/tablet/tablet_view.py")


def _module() -> ast.Module:
    return ast.parse(SOURCE.read_text(encoding="utf-8"))


def _class(module: ast.Module, name: str) -> ast.ClassDef:
    return next(
        node for node in module.body if isinstance(node, ast.ClassDef) and node.name == name
    )


def _method(node: ast.ClassDef, name: str) -> ast.FunctionDef:
    return next(
        item for item in node.body if isinstance(item, ast.FunctionDef) and item.name == name
    )


def test_track_widget_initializes_localizer_before_header_overflow_text() -> None:
    module = _module()
    widget = _class(module, "TabletTrackWidget")
    init = _method(widget, "__init__")
    parameter_names = [argument.arg for argument in init.args.args]

    assert "localizer" in parameter_names
    assert any(
        isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Attribute)
            and isinstance(target.value, ast.Name)
            and target.value.id == "self"
            and target.attr == "_localizer"
            for target in node.targets
        )
        for node in ast.walk(init)
    )


def test_tablet_view_passes_active_localizer_to_every_track_widget() -> None:
    module = _module()
    view = _class(module, "TabletView")
    creator = _method(view, "_create_rendered_track")
    calls = [
        node
        for node in ast.walk(creator)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "TabletTrackWidget"
    ]

    assert len(calls) == 1
    localizer_keyword = next(
        (keyword for keyword in calls[0].keywords if keyword.arg == "localizer"), None
    )
    assert localizer_keyword is not None
    assert isinstance(localizer_keyword.value, ast.Attribute)
    assert isinstance(localizer_keyword.value.value, ast.Name)
    assert localizer_keyword.value.value.id == "self"
    assert localizer_keyword.value.attr == "_localizer"
