from __future__ import annotations

import ast
from pathlib import Path


UI_FILES = (
    Path("src/geoworkbench/ui/main_window.py"),
    Path("src/geoworkbench/ui/main_window_drilling.py"),
)

_PROJECT_COLLECTIONS = {
    "project",
    "tablet_layouts",
    "tablet_presets",
    "source_documents",
    "import_reports",
    "image_assets",
    "rock_code_profiles",
    "rock_code_source_bindings",
}

_MUTATING_METHODS = {
    "add",
    "append",
    "clear",
    "discard",
    "extend",
    "insert",
    "pop",
    "remove",
    "set_active_index",
    "set_current_tablet_layout",
    "setdefault",
    "update",
    "upsert_curve",
}

_ALLOWED_DATASET_READ_METHODS = {
    "curve_by_mnemonic",
}

_FORBIDDEN_AD_HOC_CONSTRUCTORS = (
    "WitsmlProjectImportController(self.session)",
    "CanvasObjectTransferController(self.session)",
    "CanvasObjectTransferWorkflow(",
    "WellAnalysisUpdateController(self.session)",
    "WellAnalysisUpdateWorkflow(",
)


def _attribute_path(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        owner = _attribute_path(node.value)
        return f"{owner}.{node.attr}" if owner else node.attr
    if isinstance(node, ast.Subscript):
        owner = _attribute_path(node.value)
        return f"{owner}[]" if owner else None
    return None


def _assignment_targets(node: ast.AST) -> tuple[ast.AST, ...]:
    if isinstance(node, ast.Assign):
        return tuple(node.targets)
    if isinstance(node, ast.AnnAssign):
        return (node.target,)
    if isinstance(node, ast.AugAssign):
        return (node.target,)
    return ()


def test_main_window_layers_do_not_write_project_state_directly() -> None:
    violations: list[str] = []

    for path in UI_FILES:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))

        for node in ast.walk(tree):
            for target in _assignment_targets(node):
                target_path = _attribute_path(target)
                if target_path and target_path.startswith("self.session"):
                    violations.append(
                        f"{path}:{getattr(node, 'lineno', '?')}: assignment to {target_path}"
                    )
                if target_path and (
                    target_path.startswith("dataset.")
                    or target_path.startswith("well.")
                ):
                    violations.append(
                        f"{path}:{getattr(node, 'lineno', '?')}: domain assignment to {target_path}"
                    )

            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            owner = _attribute_path(node.func.value)
            method = node.func.attr
            if owner is None:
                continue

            if owner == "self.session" and method in _MUTATING_METHODS:
                violations.append(
                    f"{path}:{node.lineno}: mutating session call {owner}.{method}()"
                )

            if owner.startswith("self.session."):
                first_member = owner.split(".", 2)[2].split("[]", 1)[0].split(".", 1)[0]
                if first_member in _PROJECT_COLLECTIONS and method in _MUTATING_METHODS:
                    violations.append(
                        f"{path}:{node.lineno}: project collection mutation {owner}.{method}()"
                    )

            if owner == "dataset" and method not in _ALLOWED_DATASET_READ_METHODS:
                violations.append(
                    f"{path}:{node.lineno}: Dataset method call dataset.{method}()"
                )
            if owner == "well":
                violations.append(
                    f"{path}:{node.lineno}: Well method call well.{method}()"
                )

        for token in _FORBIDDEN_AD_HOC_CONSTRUCTORS:
            if token in source:
                violations.append(f"{path}: forbidden ad-hoc application constructor: {token}")

    assert violations == []


def test_arch02_boundary_keeps_known_feature_coordinators_in_ui_composition() -> None:
    base = UI_FILES[0].read_text(encoding="utf-8")
    production = UI_FILES[1].read_text(encoding="utf-8")

    assert "WitsmlImportCoordinator(self.session)" in base
    assert "GasRatioProjectController(self.session)" in base
    assert "Gs2ImportCoordinator(self._dataset_import_jobs)" in base
    assert "CanvasObjectTransferCoordinator(" in production
    assert "LateAnalysisCoordinator(" in production
    assert "InterpretationFeatureCoordinator(" in production
    assert "DrillingCalculationCoordinator(" in production
