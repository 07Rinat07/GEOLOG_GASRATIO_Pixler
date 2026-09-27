from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_import_dialog_has_adaptive_size_close_and_safe_cancel() -> None:
    source = (ROOT / "src/geoworkbench/ui/paradox_import_dialog.py").read_text(
        encoding="utf-8"
    )
    assert "WindowCloseButtonHint" in source
    assert "fit_window_to_screen" in source
    assert "paradox-import-secondary-actions-scroll" in source
    assert 'self.file_tab_scroll.setObjectName("paradoxImportFileScroll")' in source
    assert "QLayout.SizeConstraint.SetMinimumSize" in source
    assert "QFormLayout.RowWrapPolicy.WrapLongRows" in source
    assert "form.setVerticalSpacing(8)" in source
    assert "self.resize(1100, 720)" not in source
    assert "self.cancel_button" in source
    assert "def closeEvent" in source
    assert "request_cancel()" in source
    assert "requestInterruption()" in source


def test_import_dialog_reports_stage_count_elapsed_and_overall_progress() -> None:
    source = (ROOT / "src/geoworkbench/ui/paradox_import_dialog.py").read_text(
        encoding="utf-8"
    )
    assert "self.phase_label" in source
    assert "self.elapsed_label" in source
    assert "paradox_progress_state" in source
    assert "self.progress_detail" in source
    assert "self.progress_hint" in source
    assert "phase=\"preview\"" in source


def test_import_file_tab_uses_scrollable_non_overlapping_form(qapp, tmp_path, monkeypatch) -> None:
    from geoworkbench.services.localization import AppLanguage
    from geoworkbench.ui.paradox_import_dialog import ParadoxImportDialog

    monkeypatch.setattr(ParadoxImportDialog, "_start_reader", lambda self: None)
    source = tmp_path / "layout-only.db"
    source.write_bytes(b"")

    dialog = ParadoxImportDialog(source, language=AppLanguage.RU)
    try:
        dialog.show()
        dialog.resize(700, 500)
        qapp.processEvents()

        assert dialog.file_tab_scroll.verticalScrollBar().maximum() > 0

        fields = (
            dialog.classification,
            dialog.depth_field,
            dialog.time_field,
            dialog.active_role,
            dialog.actual_depth_step,
            dialog.standard_depth_step,
            dialog.null_value,
            dialog.duplicate_policy,
            dialog.sort_index,
            dialog.drop_empty_channels,
        )
        geometries = [field.geometry() for field in fields]
        assert all(rect.height() > 0 for rect in geometries)
        for previous, current in zip(geometries, geometries[1:]):
            assert previous.bottom() < current.top()
    finally:
        dialog.close()
        qapp.processEvents()
