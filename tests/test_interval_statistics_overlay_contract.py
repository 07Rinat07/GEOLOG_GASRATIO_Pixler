from pathlib import Path


def _source() -> str:
    return Path("src/geoworkbench/ui/main_window.py").read_text(encoding="utf-8")


def test_statistics_uses_floating_overlay_instead_of_consuming_tablet_width() -> None:
    source = _source()
    start = source.index("    def _adapt_interval_statistics_dock")
    end = source.index("    def _create_issues_panel", start)
    block = source[start:end]
    assert 'dock.setFloating(True)' in block
    assert 'dock.move(target_x, target_y)' in block
    assert 'screen.availableGeometry()' in block
    assert 'BottomDockWidgetArea' not in block


def test_form_switch_clears_previous_interval_analysis() -> None:
    source = _source()
    start = source.index("    def apply_form_to_tablet")
    end = source.index("    def build_default_tablet", start)
    block = source[start:end]
    assert 'self._clear_interval_analysis()' in block
    assert block.index('self._clear_interval_analysis()') < block.index('self._deactivate_curve_pencil_for_layout_change')
