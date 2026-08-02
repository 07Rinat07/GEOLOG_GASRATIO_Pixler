from __future__ import annotations

import ast
from pathlib import Path


_FORBIDDEN_CALCULATION_IMPORTS = (
    "PySide6",
    "pyqtgraph",
    "geoworkbench.ui",
    "geoworkbench.tablet",
    "geoworkbench.printing",
)


def _imported_modules(path: str) -> set[str]:
    source = Path(path).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=path)
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_gas_calculations_are_qt_and_renderer_independent() -> None:
    for path in (
        "src/geoworkbench/calculations/gas_conditioning.py",
        "src/geoworkbench/calculations/gas_ratio.py",
    ):
        imported = _imported_modules(path)
        violations = sorted(
            module
            for module in imported
            if module.startswith(_FORBIDDEN_CALCULATION_IMPORTS)
        )
        assert violations == [], f"{path} imports forbidden upper layers: {violations}"


def test_project_session_uses_versioned_conditioned_calculation_boundary() -> None:
    source = Path("src/geoworkbench/project/session.py").read_text(encoding="utf-8")

    assert "calculate_conditioned_ratios(dataset.depth, inputs)" in source
    assert "CONDITIONED_GAS_PROVENANCE" in source
    assert "calculate_basic_ratios(inputs)" not in source
    assert "curve.metadata = replace(" in source


def test_canonical_docs_track_gas_architecture_and_testing() -> None:
    plan = Path("docs/PROJECT_PLAN.md").read_text(encoding="utf-8")
    architecture = Path("docs/ARCHITECTURE.md").read_text(encoding="utf-8")
    testing = Path("docs/TESTING.md").read_text(encoding="utf-8")

    assert "GAS-01" in plan
    assert "GAS-08" in plan
    assert "Газовый conditioning и расчётная граница" in architecture
    assert "tests/test_gas_conditioning.py" in testing
    assert "benchmarks/benchmark_gas_conditioning.py" in testing
