from __future__ import annotations

import ast
from pathlib import Path


SOURCE_ROOT = Path("src")
LAYER_ROOTS = (
    SOURCE_ROOT / "geoworkbench/domain",
    SOURCE_ROOT / "geoworkbench/calculations",
)
FORBIDDEN_PREFIXES = (
    "pyqtgraph",
    "qtpy",
    "geoworkbench.ui",
    "geoworkbench.printing",
)
QT_BINDING_PREFIXES = ("PySide", "PyQt")


def _module_name(path: Path) -> str:
    relative = path.relative_to(SOURCE_ROOT).with_suffix("")
    parts = relative.parts
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _package_name(path: Path) -> str:
    module = _module_name(path)
    return module if path.name == "__init__.py" else module.rpartition(".")[0]


def _resolve_from_module(path: Path, node: ast.ImportFrom) -> str:
    if node.level == 0:
        return node.module or ""

    package_parts = _package_name(path).split(".")
    keep = len(package_parts) - (node.level - 1)
    base_parts = package_parts[: max(keep, 0)]
    if node.module:
        base_parts.extend(node.module.split("."))
    return ".".join(part for part in base_parts if part)


def _imported_names(path: Path, node: ast.Import | ast.ImportFrom) -> tuple[str, ...]:
    if isinstance(node, ast.Import):
        return tuple(alias.name for alias in node.names)

    base = _resolve_from_module(path, node)
    imported: list[str] = []
    if base:
        imported.append(base)
    for alias in node.names:
        if alias.name == "*":
            continue
        imported.append(f"{base}.{alias.name}" if base else alias.name)
    return tuple(imported)


def _is_forbidden(module: str) -> bool:
    if module.startswith(QT_BINDING_PREFIXES):
        return True
    return any(
        module == prefix or module.startswith(f"{prefix}.")
        for prefix in FORBIDDEN_PREFIXES
    )


def test_domain_and_calculations_do_not_depend_on_qt_ui_or_printing() -> None:
    violations: list[str] = []
    audited_files: list[Path] = []

    for root in LAYER_ROOTS:
        assert root.is_dir(), f"Missing architecture layer: {root}"
        for path in sorted(root.rglob("*.py")):
            audited_files.append(path)
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

            for node in ast.walk(tree):
                if not isinstance(node, (ast.Import, ast.ImportFrom)):
                    continue
                for imported in _imported_names(path, node):
                    if _is_forbidden(imported):
                        violations.append(
                            f"{path}:{node.lineno}: forbidden layer dependency {imported}"
                        )

    assert audited_files, "ARCH-05 import boundary did not audit any production modules"
    assert any("geoworkbench/domain" in path.as_posix() for path in audited_files)
    assert any("geoworkbench/calculations" in path.as_posix() for path in audited_files)
    assert violations == []
