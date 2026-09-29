from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_manual_fit_printing_still_builds_adaptive_page_geometry() -> None:
    source = (ROOT / "src/geoworkbench/printing/document_renderer.py").read_text(
        encoding="utf-8"
    )
    guarded_block = (
        "if (\n"
        "            job.page.scale_mode is PrintScaleMode.FIT\n"
        "            and full_range is not None\n"
        "        ):"
    )
    assert guarded_block in source
    assert "and use_auto_density\n        ):" not in source


def test_geology_dialog_does_not_create_report_passport_sidecars() -> None:
    source = (
        ROOT / "src/geoworkbench/ui/interpretation_report_dialog.py"
    ).read_text(encoding="utf-8")
    assert "passport_sidecar_path" not in source
    assert "_build_report_passport" not in source
    assert "passport=" not in source


def test_native_print_preview_contains_renderer_exceptions() -> None:
    source = (ROOT / "src/geoworkbench/ui/main_window.py").read_text(encoding="utf-8")
    assert "def render_preview_safely(requested)" in source
    assert "except (RuntimeError, ValueError) as exc:" in source
    assert "QTimer.singleShot(0, preview.reject)" in source


def test_masterlog_print_preferences_are_resolved_per_active_form() -> None:
    source = (ROOT / "src/geoworkbench/ui/main_window.py").read_text(encoding="utf-8")
    assert 'if ":form:" in scope_id:' in source
    assert "or layout_form_id" in source
    assert "or self.user_profile_settings.selected_form_id()" in source
    assert "print_export_preferences_for_form(form_id)" in source
    assert "save_print_export_preferences_for_form(" in source


def test_saved_analysis_has_a_dedicated_reedit_path() -> None:
    tablet = (ROOT / "src/geoworkbench/tablet/tablet_view.py").read_text(encoding="utf-8")
    main_window = (ROOT / "src/geoworkbench/ui/main_window.py").read_text(encoding="utf-8")
    controller = (
        ROOT / "src/geoworkbench/project/cuttings_controller.py"
    ).read_text(encoding="utf-8")

    assert "analysis_sample_edit_requested = Signal(str)" in tablet
    assert "self.analysis_sample_edit_requested.emit(sample.sample_id)" in tablet
    assert "self._edit_analysis_interval_from_tablet" in main_window
    assert "def update_analysis(" in controller


def test_rock_description_interpretation_track_uses_geological_edit_routing() -> None:
    source = (ROOT / "src/geoworkbench/tablet/tablet_view.py").read_text(
        encoding="utf-8"
    )
    right_click_block = source[source.index("event.button() == Qt.MouseButton.RightButton") :]
    assert "TrackKind.INTERPRETATION" in right_click_block
    assert "kind in {TrackKind.TEXT, TrackKind.INTERPRETATION}" in source
