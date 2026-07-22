from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_batch_dialog_explains_save_location_and_exposes_post_run_actions() -> None:
    source = (ROOT / "src/geoworkbench/ui/paradox_batch_dialog.py").read_text(
        encoding="utf-8"
    )

    assert "paradox.batch_instructions" in source
    assert "paradox.open_result_folder" in source
    assert "paradox.open_selected_las" in source
    assert "paradox.convert_and_save" in source
    assert "paradox.stop_conversion" in source
    assert "def closeEvent" in source
    assert "QDesktopServices.openUrl" in source


def test_batch_dialog_prevents_output_name_collisions_and_previews_full_paths() -> None:
    source = (ROOT / "src/geoworkbench/ui/paradox_batch_dialog.py").read_text(
        encoding="utf-8"
    )

    assert "paradox.batch_duplicate_targets" in source
    assert "_target_plan" in source
    assert "target_item = QTableWidgetItem(str(target))" in source
    assert '"{source_name}_{mode}.las"' in source


def test_main_window_can_open_generated_las_from_batch_dialog() -> None:
    source = (ROOT / "src/geoworkbench/ui/main_window.py").read_text(encoding="utf-8")

    assert "dialog.open_las_requested.connect(self._open_generated_las)" in source
    assert "def _open_generated_las" in source
    assert "def _open_las_files" in source
