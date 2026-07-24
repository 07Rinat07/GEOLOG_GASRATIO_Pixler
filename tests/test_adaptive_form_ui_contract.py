from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_form_editor_exposes_live_a4_width_advice() -> None:
    source = (ROOT / "src/geoworkbench/ui/form_structure_editor_dialog.py").read_text(
        encoding="utf-8"
    )
    assert "self.width_advice = QLabel()" in source
    assert "def _update_width_advice" in source
    assert "audit_form_width" in source
    assert "self._update_width_advice()" in source
    assert '"A4 книжн."' in source
    assert '"A4 альбомн."' in source


def test_form_library_reports_portrait_and_landscape_fit() -> None:
    source = (ROOT / "src/geoworkbench/ui/form_manager_dialog.py").read_text(
        encoding="utf-8"
    )
    assert "A4-контроль" in source
    assert "audit.portrait_scale_percent" in source
    assert "audit.landscape_scale_percent" in source
    assert "FormWidthLevel.NEEDS_FIT" in source


def test_interval_statistics_is_screen_clamped_floating_overlay() -> None:
    source = (ROOT / "src/geoworkbench/ui/main_window.py").read_text(encoding="utf-8")
    assert "def _adapt_interval_statistics_overlay" in source
    assert "calculate_interval_statistics_overlay_geometry" in source
    assert "dock.setFloating(True)" in source
    assert "Qt.DockWidgetArea.NoDockWidgetArea" in source
    statistics_block = source[source.index("def _create_interval_statistics_panel") :]
    statistics_block = statistics_block[: statistics_block.index("def _create_issues_panel")]
    assert "DockWidgetFloatable" in statistics_block
    assert "BottomDockWidgetArea" not in statistics_block


def test_runtime_diagnostics_include_a4_width_state() -> None:
    source = (ROOT / "src/geoworkbench/ui/main_window.py").read_text(encoding="utf-8")
    assert '"tablet_form_width_px"' in source
    assert '"tablet_a4_portrait_percent"' in source
    assert '"tablet_a4_width_level"' in source
