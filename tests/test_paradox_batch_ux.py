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


def test_batch_dialog_has_in_place_manual_configuration_workflow() -> None:
    source = (ROOT / "src/geoworkbench/ui/paradox_batch_dialog.py").read_text(encoding="utf-8")
    import_dialog = (ROOT / "src/geoworkbench/ui/paradox_import_dialog.py").read_text(encoding="utf-8")

    assert "paradox.configure_selected_source" in source
    assert "def _configure_selected_source" in source
    assert "configuration_only=True" in source
    assert "self._manual_plans[source] = plan" in source
    assert "paradox.retry_after_configuration" in source
    assert "self.selected_plan: ParadoxImportPlan | None" in import_dialog
    assert "paradox.apply_batch_settings" in import_dialog


def test_batch_dialog_offers_explicit_source_or_geoscape_depth_grid(
    qapp,
    tmp_path: Path,
) -> None:
    from geoworkbench.services.localization import AppLanguage
    from geoworkbench.ui.paradox_batch_dialog import ParadoxBatchDialog

    dialog = ParadoxBatchDialog(
        (tmp_path / "source.db",),
        language=AppLanguage.EN,
    )

    assert dialog.depth_grid.count() == 2
    assert dialog.depth_grid.itemData(0) is None
    assert dialog.depth_grid.itemData(1) == 0.2
    assert "no resampling" in dialog.depth_grid.itemText(0)
    assert "0.2 m" in dialog.depth_grid.itemText(1)
    dialog.close()
