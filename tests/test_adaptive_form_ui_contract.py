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


def test_interval_statistics_uses_parent_clamped_overlay_without_stealing_form_width() -> None:
    source = (ROOT / "src/geoworkbench/ui/main_window.py").read_text(encoding="utf-8")
    assert "def _adapt_interval_statistics_dock" in source
    assert "IntervalStatisticsOverlay(" in source
    assert "self.tablet_view," in source
    assert "overlay.constrain_to_parent(anchor_right=False)" in source
    assert "setFloating(True)" not in source


def test_runtime_diagnostics_include_a4_width_state() -> None:
    source = (ROOT / "src/geoworkbench/ui/main_window.py").read_text(encoding="utf-8")
    assert '"tablet_form_width_px"' in source
    assert '"tablet_a4_portrait_percent"' in source
    assert '"tablet_a4_width_level"' in source
