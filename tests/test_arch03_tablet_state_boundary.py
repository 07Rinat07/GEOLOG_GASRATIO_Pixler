from __future__ import annotations

import ast
from pathlib import Path


TABLET_VIEW = Path("src/geoworkbench/tablet/tablet_view.py")
STATE_MODULES = (
    Path("src/geoworkbench/tablet/curve_pencil_state.py"),
    Path("src/geoworkbench/tablet/navigation_coordinator.py"),
    Path("src/geoworkbench/tablet/interval_editing_state.py"),
    Path("src/geoworkbench/tablet/selection_interaction.py"),
    Path("src/geoworkbench/tablet/render_state.py"),
)

_FORBIDDEN_DIRECT_STATE = {
    "_curve_pencil_enabled",
    "_curve_pencil_track_id",
    "_curve_pencil_mnemonic",
    "_curve_pencil_curve_id",
    "_curve_pencil_points",
    "_curve_pencil_mode",
    "_curve_pencil_commit_ack",
    "_curve_pencil_commit_error",
    "_curve_pencil_unsaved",
    "_curve_pencil_can_undo",
    "_curve_pencil_can_redo",
    "_interval_edit_mode",
    "_interval_creation_type",
    "_interval_gesture",
    "_selected_interpretation_id",
    "_selected_interval_id",
    "_geometry_cache",
    "_static_layer_cache",
    "_dirty_registry",
    "_overlay_layers",
}

_REQUIRED_COMPOSITION = (
    "self._curve_pencil_state = CurvePencilState()",
    "self._navigation = TabletNavigationCoordinator()",
    "self._interval_editing = IntervalEditingState(",
    "self._selection = SelectionManager()",
    "self._interpretation_selection = InterpretationSelectionState(self._selection)",
    "self._render_state = TabletRenderState()",
    "self._track_lifecycle = TrackLifecycleCoordinator()",
)


def _tablet_init() -> ast.FunctionDef:
    tree = ast.parse(TABLET_VIEW.read_text(encoding="utf-8"), filename=str(TABLET_VIEW))
    tablet = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "TabletView"
    )
    return next(
        node
        for node in tablet.body
        if isinstance(node, ast.FunctionDef) and node.name == "__init__"
    )


def _self_attribute_name(node: ast.AST) -> str | None:
    if (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
    ):
        return node.attr
    return None


def test_tablet_view_init_has_no_legacy_direct_state_storage() -> None:
    assigned: set[str] = set()
    init = _tablet_init()

    for node in ast.walk(init):
        targets: tuple[ast.AST, ...] = ()
        if isinstance(node, ast.Assign):
            targets = tuple(node.targets)
        elif isinstance(node, ast.AnnAssign):
            targets = (node.target,)
        elif isinstance(node, ast.AugAssign):
            targets = (node.target,)
        for target in targets:
            name = _self_attribute_name(target)
            if name is not None:
                assigned.add(name)

    assert assigned.isdisjoint(_FORBIDDEN_DIRECT_STATE)


def test_tablet_view_composes_arch03_state_components() -> None:
    source = TABLET_VIEW.read_text(encoding="utf-8")

    for token in _REQUIRED_COMPOSITION:
        assert token in source

    assert "from geoworkbench.tablet.sampling import snap_viewport_to_axis_samples" in source


def test_arch03_state_modules_have_no_top_level_qt_dependency() -> None:
    violations: list[str] = []

    for path in STATE_MODULES:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if isinstance(node, ast.Import):
                names = tuple(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                names = (node.module or "",)
            else:
                continue
            for name in names:
                if name.startswith("PySide6") or name.startswith("pyqtgraph"):
                    violations.append(f"{path}: top-level Qt import {name}")

    assert violations == []
