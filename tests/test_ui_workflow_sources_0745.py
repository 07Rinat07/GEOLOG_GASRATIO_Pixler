from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_new_depth_las_default_step_is_point_two_metres() -> None:
    source = (ROOT / "src/geoworkbench/ui/new_las_dialog.py").read_text(encoding="utf-8")
    assert "self._number_input(0.2, minimum=0.000001)" in source


def test_track_editor_exposes_independent_grid_and_header_colour_settings() -> None:
    source = (ROOT / "src/geoworkbench/ui/tablet_track_editor_dialog.py").read_text(
        encoding="utf-8"
    )
    for token in (
        "self.grid_x_input",
        "self.grid_y_input",
        "self.grid_major_input",
        "self.grid_minor_input",
        "self.grid_alpha_input",
        "self.header_text_color_input",
        "self.header_line_color_input",
    ):
        assert token in source


def test_grid_renderer_uses_overlay_independent_of_hidden_plot_axes() -> None:
    source = (ROOT / "src/geoworkbench/tablet/grid_renderer.py").read_text(encoding="utf-8")
    assert "class TabletGridOverlay" in source
    assert "pg.InfiniteLine" in source


def test_las_import_shows_busy_state_before_synchronous_job() -> None:
    source = (ROOT / "src/geoworkbench/ui/main_window.py").read_text(
        encoding="utf-8"
    )

    start = source.index("def _open_las_files(")
    end = source.index("def _persist_import_diagnostics", start)
    block = source[start:end]

    assert "QProgressDialog(" in block
    assert 'self._t("import.las_loading")' in block
    assert "progress.setRange" not in block
    assert "progress.setCancelButton(None)" in block
    assert "QApplication.processEvents()" in block
    assert block.index("progress.show()") < block.index(
        "self._dataset_import_jobs.execute_las("
    )
