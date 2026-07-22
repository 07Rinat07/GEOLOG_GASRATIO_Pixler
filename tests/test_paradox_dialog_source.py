from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_import_dialog_has_adaptive_size_close_and_safe_cancel() -> None:
    source = (ROOT / "src/geoworkbench/ui/paradox_import_dialog.py").read_text(
        encoding="utf-8"
    )
    assert "WindowCloseButtonHint" in source
    assert "availableGeometry" in source
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
