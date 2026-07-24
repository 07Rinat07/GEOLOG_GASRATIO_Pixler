from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _main_source() -> str:
    return (ROOT / "src/geoworkbench/ui/main_window.py").read_text(encoding="utf-8")


def _overlay_source() -> str:
    return (ROOT / "src/geoworkbench/ui/interval_statistics_overlay.py").read_text(
        encoding="utf-8"
    )


def test_statistics_is_child_overlay_instead_of_floating_native_window() -> None:
    source = _main_source()
    start = source.index("    def _create_interval_statistics_panel")
    end = source.index("    def _create_issues_panel", start)
    block = source[start:end]
    assert "IntervalStatisticsOverlay(" in block
    assert "self.tablet_view," in block
    assert "addDockWidget" not in block
    assert "setFloating" not in block
    assert "screen.availableGeometry" not in block


def test_overlay_preserves_user_position_and_clamps_to_parent() -> None:
    source = _overlay_source()
    assert "self._user_positioned = True" in source
    assert "constrain_overlay_geometry(" in source
    assert "anchor_right=not self._user_positioned" in source
    assert "self.move_constrained(" in source
    assert "globalPosition().toPoint()" in source


def test_overlay_close_clears_interval_analysis() -> None:
    source = _main_source()
    start = source.index("    def _create_interval_statistics_panel")
    end = source.index("    def _create_issues_panel", start)
    block = source[start:end]
    assert "closeRequested.connect(" in block
    assert "self._clear_interval_analysis" in block


def test_form_switch_clears_previous_interval_analysis_before_render() -> None:
    source = _main_source()
    start = source.index("    def apply_form_to_tablet")
    end = source.index("    def build_default_tablet", start)
    block = source[start:end]
    assert "self._clear_interval_analysis()" in block
    assert block.index("self._clear_interval_analysis()") < block.index(
        "self._deactivate_curve_pencil_for_layout_change"
    )


def test_dataset_switch_clears_interval_overlay_before_rebinding_views() -> None:
    source = _main_source()
    start = source.index("    def _show_current_dataset")
    end = source.index("    def show_las_editor", start)
    block = source[start:end]
    assert "self._clear_interval_analysis()" in block
    assert block.index("self._clear_interval_analysis()") < block.index(
        "dataset = self.session.current_dataset"
    )


def test_overlay_toggle_off_routes_through_close_request() -> None:
    source = _overlay_source()
    assert "self._toggle_action.toggled.connect(self._toggle_requested)" in source
    assert "self.closeRequested.emit()" in source


def test_statistics_panel_buttons_use_compact_grid_instead_of_one_wide_row() -> None:
    source = (
        ROOT / "src/geoworkbench/ui/interval_statistics_panel.py"
    ).read_text(encoding="utf-8")
    assert "QGridLayout" in source
    assert "buttons.addWidget(self.copy_button, 0, 0)" in source
    assert "buttons.addWidget(self.xlsx_button, 0, 1)" in source
    assert "buttons.addWidget(self.csv_button, 1, 0)" in source
    assert "buttons.addWidget(self.clear_button, 1, 1)" in source
