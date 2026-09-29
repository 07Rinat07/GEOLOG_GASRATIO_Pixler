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
    assert "explicit_form_id or self.user_profile_settings.selected_form_id()" in source
    assert "print_export_preferences_for_form(form_id)" in source
    assert "save_print_export_preferences_for_form(" in source
