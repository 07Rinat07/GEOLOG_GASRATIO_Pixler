from pathlib import Path


SOURCE = Path("src/geoworkbench/ui/main_window.py").read_text(encoding="utf-8")


def test_statistics_panel_is_a_floating_overlay_not_a_width_consuming_dock() -> None:
    create_block = SOURCE.split(
        "    def _create_interval_statistics_panel(self) -> None:\n", 1
    )[1].split("    def _create_issues_panel(self) -> None:\n", 1)[0]

    assert 'setObjectName("intervalStatisticsOverlay")' in create_block
    assert "setFloating(True)" in create_block
    assert "NoDockWidgetArea" in create_block
    assert "calculate_interval_statistics_overlay_geometry" in create_block


def test_form_switch_clears_stale_interval_before_widget_replacement() -> None:
    apply_block = SOURCE.split("    def apply_form_to_tablet(\n", 1)[1].split(
        "    def build_default_tablet(self) -> None:\n", 1
    )[0]

    clear_position = apply_block.index("self._clear_interval_analysis()")
    render_position = apply_block.index("def render_candidate")
    assert clear_position < render_position


def test_dataset_switch_clears_interval_report_and_shading() -> None:
    dataset_block = SOURCE.split("    def _show_current_dataset(self) -> None:\n", 1)[1].split(
        "    def show_las_editor(self) -> None:\n", 1
    )[0]

    assert "self._clear_interval_analysis()" in dataset_block


def test_user_closing_overlay_clears_selection_even_when_buttons_are_hidden() -> None:
    visibility_block = SOURCE.split(
        "    def _interval_statistics_visibility_changed(self, visible: bool) -> None:\n",
        1,
    )[1].split("    def _adapt_interval_statistics_overlay", 1)[0]

    assert "clear_interval_analysis(emit_signal=False)" in visibility_block
    assert "dataset_selection.clear()" in visibility_block
    assert "interval_statistics_panel.clear_report()" in visibility_block
