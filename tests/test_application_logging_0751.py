from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZipFile

from geoworkbench.services import application_logging
from geoworkbench.services.application_logging import ApplicationLogManager
from geoworkbench.services.build_identity import BuildIdentity


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
    build_identity = BuildIdentity(
        "0.7.51-test",
        "0123456789abcdef0123456789abcdef01234567",
        "test",
    )
    manager = ApplicationLogManager(
        tmp_path / "logs",
        application_version="0.7.51-test",
        build_identity=build_identity,
        session_id="diagnostic-bundle-session",
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
            assert report["application_commit"] == build_identity.commit
            assert report["build_identity"] == build_identity.display
            assert report["build_identity_source"] == "test"
            assert report["session_id"] == "diagnostic-bundle-session"
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


def test_clear_diagnostic_data_removes_logs_and_reports_then_resumes_logging(
    tmp_path: Path,
) -> None:
    logs = tmp_path / "logs"
    reports = tmp_path / "diagnostics"
    reports.mkdir(parents=True)
    (reports / "las_import_1.txt").write_text("report", encoding="utf-8")
    exported_bundle = tmp_path / "GEOLOG_diagnostics_exported.zip"
    exported_bundle.write_bytes(b"user export")
    project_file = tmp_path / "well.geolog.json"
    project_file.write_text("{}", encoding="utf-8")
    unrelated_log_folder_file = logs / "keep-user-note.txt"
    logs.mkdir(parents=True, exist_ok=True)
    unrelated_log_folder_file.write_text("keep", encoding="utf-8")
    nested = reports / "old"
    nested.mkdir()
    (nested / "las_import_2.json").write_text("{}", encoding="utf-8")

    manager = ApplicationLogManager(
        logs,
        application_version="0.7.66-test",
        max_bytes=4096,
        backup_count=2,
    )
    try:
        manager.event("before.reset")
        manager.flush()
        (logs / "geolog.log.1").write_text("old log", encoding="utf-8")

        result = manager.clear_diagnostic_data(
            extra_directories=(reports,),
        )

        assert result.deleted_files >= 4
        assert result.freed_bytes > 0
        assert result.failed_paths == ()
        assert list(reports.rglob("*")) == []
        assert manager.current_log_path.exists()
        assert manager.crash_log_path.exists()
        assert exported_bundle.read_bytes() == b"user export"
        assert project_file.read_text(encoding="utf-8") == "{}"
        assert unrelated_log_folder_file.read_text(encoding="utf-8") == "keep"

        manager.event("after.reset")
        manager.flush()
        current = manager.current_log_path.read_text(encoding="utf-8")
        assert "diagnostics.data.reset" in current
        assert "after.reset" in current
        assert "before.reset" not in current
    finally:
        manager.close()


def test_diagnostics_reset_action_and_labels_are_wired() -> None:
    main_source = (ROOT / "src/geoworkbench/ui/main_window.py").read_text(
        encoding="utf-8"
    )
    assert '"diagnostics.clear_data"' in main_source
    assert "def clear_diagnostic_data(self)" in main_source
    assert "manager.clear_diagnostic_data(" in main_source

    required = {
        "diagnostics.clear_data",
        "diagnostics.clear_title",
        "diagnostics.clear_confirm",
        "diagnostics.clear_done",
        "diagnostics.clear_partial",
        "diagnostics.clear_failed",
    }
    for language in ("ru", "kk", "en"):
        data = json.loads(
            (ROOT / f"src/geoworkbench/resources/i18n/{language}.json").read_text(
                encoding="utf-8"
            )
        )
        assert required.issubset(data)

def test_application_log_uses_utc_formatter_and_records_build_session(
    tmp_path: Path,
    monkeypatch,
) -> None:
    def localtime_must_not_be_used(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("local time formatter was used")

    monkeypatch.setattr(application_logging.time, "localtime", localtime_must_not_be_used)
    identity = BuildIdentity(
        "0.7.96-test",
        "abcdef0123456789abcdef0123456789abcdef01",
        "test",
    )
    manager = ApplicationLogManager(
        tmp_path / "logs",
        application_version="0.7.96-test",
        build_identity=identity,
        session_id="session-plus-five",
    )
    try:
        manager.event("timezone.contract.checked")
        manager.flush()
        text = manager.current_log_path.read_text(encoding="utf-8")

        assert "application.logging.started" in text
        assert 'build_identity="0.7.96-test+abcdef012345"' in text
        assert f'commit="{identity.commit}"' in text
        assert 'session_id="session-plus-five"' in text
        for line in text.splitlines():
            if "event=" in line:
                assert line.split(" | ", 1)[0].endswith("Z")
    finally:
        manager.close()


def test_crash_log_boundaries_separate_legacy_content_and_consecutive_runs(
    tmp_path: Path,
) -> None:
    log_directory = tmp_path / "logs"
    log_directory.mkdir(parents=True)
    crash_path = log_directory / "geolog-crash.log"
    crash_path.write_text("legacy crash entry without session identity\n", encoding="utf-8")
    identity = BuildIdentity("0.7.96-test", "1" * 40, "test")

    first = ApplicationLogManager(
        log_directory,
        application_version="0.7.96-test",
        build_identity=identity,
        session_id="session-one",
    )
    first.close()

    second = ApplicationLogManager(
        log_directory,
        application_version="0.7.96-test",
        build_identity=identity,
        session_id="session-two",
    )
    second.close()

    text = crash_path.read_text(encoding="utf-8")
    legacy = text.index("legacy crash entry without session identity")
    first_start = text.index("GEOLOG SESSION START", legacy)
    first_stop = text.index("GEOLOG SESSION STOP", first_start)
    second_start = text.index("GEOLOG SESSION START", first_stop)
    second_stop = text.index("GEOLOG SESSION STOP", second_start)

    assert legacy < first_start < first_stop < second_start < second_stop
    assert "session_id=session-one" in text[first_start:first_stop]
    assert "session_id=session-two" in text[second_start:second_stop]
    assert f"commit={identity.commit}" in text


def test_application_log_rejects_mismatched_build_version(tmp_path: Path) -> None:
    identity = BuildIdentity("0.7.95", "2" * 40, "test")

    try:
        ApplicationLogManager(
            tmp_path / "logs",
            application_version="0.7.96",
            build_identity=identity,
        )
    except ValueError as exc:
        assert "build identity version" in str(exc)
    else:
        raise AssertionError("mismatched build identity version must be rejected")

