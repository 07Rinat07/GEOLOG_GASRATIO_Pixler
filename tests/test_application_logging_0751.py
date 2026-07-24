from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZipFile

from geoworkbench.services.application_logging import ApplicationLogManager


ROOT = Path(__file__).resolve().parents[1]


def test_application_log_records_events_and_tracebacks(tmp_path: Path) -> None:
    manager = ApplicationLogManager(
        tmp_path / "logs",
        application_version="0.7.51-test",
        max_bytes=64 * 1024,
        backup_count=2,
    )
    try:
        manager.event(
            "forms.apply.requested",
            form_id="daily-form",
            pencil_active=True,
        )
        try:
            raise RuntimeError("simulated form failure")
        except RuntimeError as exc:
            manager.exception(
                "forms.apply.failed",
                exc,
                context={"form_id": "daily-form"},
            )
        manager.flush()
        text = manager.current_log_path.read_text(encoding="utf-8")
        assert "application.logging.started" in text
        assert "forms.apply.requested" in text
        assert "forms.apply.failed" in text
        assert "RuntimeError: simulated form failure" in text
        assert 'form_id="daily-form"' in text
    finally:
        manager.close()


def test_diagnostic_bundle_contains_logs_but_not_project_data(tmp_path: Path) -> None:
    manager = ApplicationLogManager(
        tmp_path / "logs",
        application_version="0.7.51-test",
    )
    try:
        manager.event("tablet.pencil.commit_finished", accepted=False)
        project_file = tmp_path / "secret-project.las"
        project_file.write_text("LAS VALUES MUST NOT BE COPIED", encoding="utf-8")
        result = manager.build_diagnostic_bundle(
            tmp_path / "diagnostics.zip",
            runtime_context={
                "dataset_id": "dataset-1",
                "pencil_active": True,
            },
        )
        assert result.path.exists()
        with ZipFile(result.path) as archive:
            names = set(archive.namelist())
            assert "system-report.json" in names
            assert "README.txt" in names
            assert any(name.startswith("logs/geolog.log") for name in names)
            assert not any(name.endswith(".las") for name in names)
            report = json.loads(archive.read("system-report.json"))
            assert report["application_version"] == "0.7.51-test"
            assert report["runtime_context"]["dataset_id"] == "dataset-1"
    finally:
        manager.close()


def test_runtime_logging_and_pencil_lifecycle_are_wired() -> None:
    app_source = (ROOT / "src/geoworkbench/app/main.py").read_text(encoding="utf-8")
    main_source = (ROOT / "src/geoworkbench/ui/main_window.py").read_text(
        encoding="utf-8"
    )
    tablet_source = (ROOT / "src/geoworkbench/tablet/tablet_view.py").read_text(
        encoding="utf-8"
    )

    assert "class DiagnosticApplication(QApplication)" in app_source
    assert "qInstallMessageHandler(handler)" in app_source
    assert "install_python_exception_hooks(log_manager)" in app_source
    assert "qt.event.exception" in app_source

    assert 'self._localized_action("diagnostics.open_logs")' in main_source
    assert '"diagnostics.build_bundle"' in main_source
    assert "def _diagnostic_runtime_context" in main_source
    assert "manager.build_diagnostic_bundle(" in main_source

    after_edit = main_source.split("    def _after_curve_edit", 1)[1].split(
        "    def _after_table_edit", 1
    )[0]
    assert "refresh_dataset_curves(dataset, changed_mnemonics)" in after_edit
    assert "self.tablet_view.set_dataset(dataset)" not in after_edit

    assert "def refresh_dataset_curves(" in tablet_source
    assert "self.invalidate_track(track_id, DirtyReason.DATA)" in tablet_source
    assert "update_curve_header_range(" in tablet_source
    clear_block = tablet_source.split("    def clear(self) -> None:", 1)[1].split(
        "    def refresh_view", 1
    )[0]
    assert "self.set_curve_pencil_mode(False)" in clear_block
    assert "tablet.pencil.cancelled_for_full_rebuild" in clear_block

    apply_block = main_source.split("    def apply_form_to_tablet", 1)[1].split(
        "    def build_default_tablet", 1
    )[0]
    assert '_deactivate_curve_pencil_for_layout_change("form-apply")' in apply_block
    assert apply_block.index("_deactivate_curve_pencil_for_layout_change") < apply_block.index(
        "set_layout_and_dataset"
    )


def test_diagnostic_labels_exist_in_all_languages() -> None:
    required = {
        "diagnostics.title",
        "diagnostics.open_logs",
        "diagnostics.copy_log_path",
        "diagnostics.build_bundle",
        "diagnostics.bundle_saved",
    }
    for language in ("ru", "kk", "en"):
        data = json.loads(
            (ROOT / f"src/geoworkbench/resources/i18n/{language}.json").read_text(
                encoding="utf-8"
            )
        )
        assert required.issubset(data)
