from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_masterlog_uses_headless_grid_and_legend_contracts() -> None:
    source = (ROOT / "src/geoworkbench/printing/masterlog_renderer.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)
    grid_geometry_imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module == "geoworkbench.tablet.grid_geometry"
        for alias in node.names
    }

    assert "normalized_grid_lines" in grid_geometry_imports
    assert "build_lithology_legend_from_ids" in source
    assert "from geoworkbench.tablet.grid_renderer import normalized_grid_lines" not in source


def test_screen_and_print_annotations_use_shared_layout_contract() -> None:
    screen = (ROOT / "src/geoworkbench/tablet/annotation_graphics.py").read_text(
        encoding="utf-8"
    )
    printed = (ROOT / "src/geoworkbench/printing/masterlog_renderer.py").read_text(
        encoding="utf-8"
    )

    assert "annotation_box_rect(self.record)" in screen
    assert "annotation_leader_endpoint(" in screen
    assert "layout_annotation(" in printed
    assert "def _closest_point_on_rect" not in printed


def test_golden_update_tool_writes_only_under_tests_directory() -> None:
    source = (ROOT / "tools/update_render_goldens.py").read_text(encoding="utf-8")

    assert 'project_root / "tests" / "golden_rendering"' in source
    assert "docs" not in source
