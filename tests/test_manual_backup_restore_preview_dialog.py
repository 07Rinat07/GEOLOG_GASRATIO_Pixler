"""Read-only operator review of saved manual backup archives."""

from __future__ import annotations

import time

import pytest
from PySide6.QtWidgets import QMessageBox

from geoworkbench.services.localization import AppLanguage
from geoworkbench.storage.manual_backup import BackupPlan, ManualBackupService
from geoworkbench.ui.manual_backup_restore_preview_dialog import (
    ManualBackupRestorePreviewDialog,
)


def _await_inspection(qapp, dialog: ManualBackupRestorePreviewDialog) -> None:
    deadline = time.monotonic() + 8.0
    while dialog._pending is not None and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.01)
    assert dialog._pending is None


@pytest.mark.parametrize("language", list(AppLanguage))
def test_restore_preview_is_read_only_and_requires_explicit_inspection(
    qapp, tmp_path, monkeypatch, language
):
    project = tmp_path / "well.geologpkg"
    project.write_bytes(b"saved data" * 400)
    settings = tmp_path / "prefs.ini"
    settings.write_bytes(b"[General]\nlanguage=ru\n")
    archive = ManualBackupService().create(
        BackupPlan.build((project,), settings), tmp_path / "saved.zip"
    )
    archive_bytes = archive.read_bytes()
    target = tmp_path / "new-recovery"
    dialog = ManualBackupRestorePreviewDialog(language=language)
    dialog.archive.setText(str(archive))
    dialog.parent_folder.setText(str(tmp_path))
    dialog.folder_name.setText(target.name)

    warnings: list[str] = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *args: warnings.append(str(args[-1]))
    )
    assert dialog.verified_plan is None
    assert not target.exists()

    dialog._inspect()
    assert not dialog.inspect_button.isEnabled()
    _await_inspection(qapp, dialog)

    assert not warnings
    assert dialog.verified_plan is not None
    assert dialog.verified_plan.destination == target
    assert len(dialog.verified_plan.items) == 2
    assert "projects/well.geologpkg" in dialog.preview_text.toPlainText()
    assert "settings/preferences.ini" in dialog.preview_text.toPlainText()
    assert dialog.inspect_button.isEnabled()
    assert not target.exists()
    assert archive.read_bytes() == archive_bytes
    assert project.read_bytes() == b"saved data" * 400

    # A plan for a previous operator choice must never remain 'verified'.
    dialog.folder_name.setText("different-new-folder")
    assert dialog.verified_plan is None
    assert not (tmp_path / "different-new-folder").exists()
    dialog.reject()


def test_restore_preview_rejects_corrupt_zip_without_restoring(
    qapp, tmp_path, monkeypatch
):
    invalid = tmp_path / "corrupt.zip"
    invalid.write_bytes(b"not a ZIP")
    dialog = ManualBackupRestorePreviewDialog(language=AppLanguage.EN)
    dialog.archive.setText(str(invalid))
    dialog.parent_folder.setText(str(tmp_path))
    dialog.folder_name.setText("recovery")
    warnings: list[str] = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *args: warnings.append(str(args[-1]))
    )

    dialog._inspect()
    _await_inspection(qapp, dialog)

    assert warnings
    assert dialog.verified_plan is None
    assert invalid.read_bytes() == b"not a ZIP"
    assert not (tmp_path / "recovery").exists()
    dialog.reject()


def test_restore_preview_missing_choices_do_not_start_worker(
    qapp, tmp_path, monkeypatch
):
    dialog = ManualBackupRestorePreviewDialog(language=AppLanguage.RU)
    warnings: list[str] = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *args: warnings.append(str(args[-1]))
    )
    dialog._inspect()
    assert warnings
    assert dialog._pending is None
    assert dialog.verified_plan is None
    assert not list(tmp_path.iterdir())
    dialog.reject()


def test_main_window_exposes_separate_readonly_restore_review_action(
    qapp, monkeypatch
):
    from geoworkbench.ui import main_window
    from geoworkbench.ui.main_window import MainWindow

    opened: list[AppLanguage] = []

    def fake_exec(dialog):
        opened.append(dialog.localizer.language)
        return 0

    monkeypatch.setattr(
        main_window.ManualBackupRestorePreviewDialog, "exec", fake_exec
    )
    window = MainWindow(language=AppLanguage.EN)
    assert "Inspect archive" in window.preview_manual_restore_action.text()
    window.preview_manual_restore_action.trigger()
    assert opened == [AppLanguage.EN]
    window.close()
    window.deleteLater()
    qapp.processEvents()


@pytest.mark.parametrize("language", list(AppLanguage))
def test_restore_requires_separate_confirmation_and_never_applies_settings(
    qapp, tmp_path, monkeypatch, language
):
    project = tmp_path / "well.geologpkg"
    project.write_bytes(b"saved project" * 100)
    settings = tmp_path / "preferences.ini"
    settings.write_bytes(b"[General]\\nlanguage=ru\\n")
    archive = ManualBackupService().create(
        BackupPlan.build((project,), settings), tmp_path / "backup.zip"
    )
    original_archive = archive.read_bytes()
    destination = tmp_path / "recovered"
    dialog = ManualBackupRestorePreviewDialog(language=language)
    dialog.archive.setText(str(archive))
    dialog.parent_folder.setText(str(tmp_path))
    dialog.folder_name.setText(destination.name)
    information: list[str] = []
    monkeypatch.setattr(
        QMessageBox, "information", lambda *args: information.append(str(args[-1]))
    )
    monkeypatch.setattr(
        QMessageBox, "question", lambda *args: QMessageBox.StandardButton.No
    )
    dialog._restore()
    assert dialog._pending is None
    assert not destination.exists()
    assert not dialog.restore_button.isEnabled()

    dialog._inspect()
    _await_inspection(qapp, dialog)
    assert dialog.restore_button.isEnabled()
    dialog._restore()
    assert dialog._pending is None
    assert dialog.verified_plan is not None
    assert not destination.exists()

    monkeypatch.setattr(
        QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes
    )
    dialog._restore()
    assert not dialog.restore_button.isEnabled()
    _await_inspection(qapp, dialog)

    assert information
    assert dialog.verified_plan is None
    assert not dialog.restore_button.isEnabled()
    assert (destination / "projects" / project.name).read_bytes() == project.read_bytes()
    assert (destination / "settings" / "preferences.ini").read_bytes() == settings.read_bytes()
    assert archive.read_bytes() == original_archive
    assert project.read_bytes() == b"saved project" * 100
    dialog.reject()


@pytest.mark.parametrize("interference", ["archive_modified", "destination_claimed"])
def test_restore_rechecks_preflight_after_confirmation_and_preserves_existing_data(
    qapp, tmp_path, monkeypatch, interference
):
    project = tmp_path / "well.geologpkg"
    project.write_bytes(b"project")
    archive = ManualBackupService().create(
        BackupPlan.build((project,)), tmp_path / "backup.zip"
    )
    destination = tmp_path / "new-folder"
    dialog = ManualBackupRestorePreviewDialog(language=AppLanguage.EN)
    dialog.archive.setText(str(archive))
    dialog.parent_folder.setText(str(tmp_path))
    dialog.folder_name.setText(destination.name)
    warnings: list[str] = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *args: warnings.append(str(args[-1]))
    )
    monkeypatch.setattr(
        QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes
    )
    dialog._inspect()
    _await_inspection(qapp, dialog)
    assert dialog.verified_plan is not None

    if interference == "archive_modified":
        archive.write_bytes(b"not a ZIP")
    else:
        destination.mkdir()
        (destination / "keep.txt").write_bytes(b"keep")

    dialog._restore()
    _await_inspection(qapp, dialog)
    assert warnings
    assert dialog.verified_plan is None
    assert not dialog.restore_button.isEnabled()
    assert not (destination / "projects").exists()
    if interference == "archive_modified":
        assert not destination.exists()
    else:
        assert (destination / "keep.txt").read_bytes() == b"keep"
    assert project.read_bytes() == b"project"
    dialog.reject()


def test_restore_refuses_selection_changed_during_confirmation(
    qapp, tmp_path, monkeypatch
):
    project = tmp_path / "well.geologpkg"
    project.write_bytes(b"project")
    archive = ManualBackupService().create(
        BackupPlan.build((project,)), tmp_path / "backup.zip"
    )
    dialog = ManualBackupRestorePreviewDialog(language=AppLanguage.EN)
    dialog.archive.setText(str(archive))
    dialog.parent_folder.setText(str(tmp_path))
    dialog.folder_name.setText("first")
    dialog._inspect()
    _await_inspection(qapp, dialog)

    def change_selection(*args):
        dialog.folder_name.setText("second")
        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(QMessageBox, "question", change_selection)
    dialog._restore()
    assert dialog._pending is None
    assert dialog.verified_plan is None
    assert not (tmp_path / "first").exists()
    assert not (tmp_path / "second").exists()
    dialog.reject()


def test_restore_worker_disables_close_and_duplicate_submission(
    qapp, tmp_path, monkeypatch
):
    from threading import Event

    project = tmp_path / "well.geologpkg"
    project.write_bytes(b"project")
    archive = ManualBackupService().create(
        BackupPlan.build((project,)), tmp_path / "backup.zip"
    )
    dialog = ManualBackupRestorePreviewDialog(language=AppLanguage.EN)
    dialog.archive.setText(str(archive))
    dialog.parent_folder.setText(str(tmp_path))
    dialog.folder_name.setText("new-folder")
    monkeypatch.setattr(
        QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes
    )
    monkeypatch.setattr(QMessageBox, "information", lambda *args: None)
    dialog._inspect()
    _await_inspection(qapp, dialog)
    entered, release = Event(), Event()
    original = ManualBackupRestorePreviewDialog._restore_verified

    def delayed_restore(plan):
        entered.set()
        if not release.wait(5):
            raise RuntimeError("Restore test worker timed out")
        return original(plan)

    monkeypatch.setattr(
        ManualBackupRestorePreviewDialog, "_restore_verified",
        staticmethod(delayed_restore),
    )
    try:
        dialog._restore()
        assert entered.wait(2)
        pending = dialog._pending
        assert pending is not None
        assert not dialog.close_button.isEnabled()
        assert not dialog.inspect_button.isEnabled()
        dialog._restore()
        dialog.reject()
        assert dialog._pending is pending
    finally:
        release.set()
    _await_inspection(qapp, dialog)
    assert (tmp_path / "new-folder" / "projects" / project.name).read_bytes() == b"project"
    dialog.reject()
