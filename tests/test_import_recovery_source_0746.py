from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_grid_overlay_uses_qt_no_button_and_has_non_blocking_fallback() -> None:
    source = (ROOT / "src/geoworkbench/tablet/grid_renderer.py").read_text(
        encoding="utf-8"
    )

    assert "Qt.MouseButton.NoButton" in source
    assert "setAcceptedMouseButtons(0)" not in source
    assert "Tablet grid overlay failed; using axis-grid fallback" in source
    assert "except Exception:  # noqa: BLE001 - presentation-only safety boundary" in source


def test_las_open_has_table_recovery_and_diagnostic_dialog() -> None:
    source = (ROOT / "src/geoworkbench/ui/main_window.py").read_text(
        encoding="utf-8"
    )

    assert "_present_imported_dataset_safely" in source
    assert "_show_import_recovery_workspace" in source
    assert "ImportDiagnosticsDialog" in source
    assert "self.las_table_editor if presentation_items else self.tablet_view" in source
    assert "_recovery_component_diagnostic" in source
    assert "component=\"las_table\"" in source


def test_import_review_returns_unexpected_failure_to_executor_boundary() -> None:
    dialog_source = (ROOT / "src/geoworkbench/ui/import_review_dialog.py").read_text(
        encoding="utf-8"
    )
    window_source = (ROOT / "src/geoworkbench/ui/main_window.py").read_text(
        encoding="utf-8"
    )

    assert "self.failure: Exception | None = None" in dialog_source
    assert "self.failure = exc" in dialog_source
    assert "if dialog.failure is not None" in window_source
    assert "raise dialog.failure" in window_source


def test_las_adapter_reads_channels_by_position_and_skips_only_bad_channel() -> None:
    source = (ROOT / "src/geoworkbench/data/las_adapter.py").read_text(
        encoding="utf-8"
    )

    assert "_curve_values_by_position" in source
    assert "matrix[:, curve_index]" in source
    assert '"channel-import-skipped"' in source
    assert "continue" in source
