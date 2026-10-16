from pathlib import Path
import time
from zipfile import ZipFile

import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QMessageBox

from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.manual_backup_dialog import ManualBackupDialog


@pytest.mark.parametrize('language', list(AppLanguage))
def test_manual_dialog_does_nothing_until_requested_and_respects_selection(qapp, tmp_path, monkeypatch, language):
    project = tmp_path / 'selected.geologpkg'
    project.write_bytes(b'saved bytes')
    excluded = tmp_path / 'excluded.geologpkg'
    excluded.write_bytes(b'excluded')
    dialog = ManualBackupDialog(project, language=language)
    dialog._add_project(excluded)
    dialog.projects.item(1).setCheckState(Qt.CheckState.Unchecked)
    assert not dialog.settings_box.isChecked()
    assert dialog._pending is None
    assert list(tmp_path.glob('*.zip')) == []
    dialog.folder.setText(str(tmp_path))
    notices = []
    monkeypatch.setattr(QMessageBox, 'information', lambda *args: notices.append(args[-1]))
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: pytest.fail(str(args[-1])))
    dialog._create()
    assert not dialog.create_button.isEnabled()
    deadline = time.monotonic() + 5
    while dialog._pending is not None and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.01)
    assert dialog._pending is None
    assert notices
    archives = list(tmp_path.glob('*.zip'))
    assert len(archives) == 1
    with ZipFile(archives[0]) as archive:
        assert set(archive.namelist()) == {'manifest.json', 'projects/0001.geologpkg'}
        assert archive.read('projects/0001.geologpkg') == b'saved bytes'
    assert dialog.create_button.isEnabled()
    dialog.reject()


def test_settings_snapshot_preserves_qt_types_without_mutating_preferences(qapp, tmp_path, monkeypatch):
    import geoworkbench.ui.manual_backup_dialog as module
    from PySide6.QtCore import QByteArray
    source = QSettings(str(tmp_path / 'original.ini'), QSettings.Format.IniFormat)
    source.setValue('language', 'ru')
    source.setValue('splitter', QByteArray(b'\x00\x01\xff'))
    source.sync()
    before = Path(source.fileName()).read_bytes()
    original_settings = QSettings
    monkeypatch.setattr(module, 'QSettings', lambda *args: original_settings(*args) if args else source)
    # Expose Qt enums on the factory used by the dialog.
    module.QSettings.Format = original_settings.Format
    module.QSettings.Status = original_settings.Status
    dialog = ManualBackupDialog(None)
    dialog.settings_box.setChecked(True)
    dialog.folder.setText(str(tmp_path))
    monkeypatch.setattr(QMessageBox, 'information', lambda *args: None)
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: pytest.fail(str(args[-1])))
    dialog._create()
    deadline = time.monotonic() + 5
    while dialog._pending is not None and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.01)
    assert dialog._pending is None
    with ZipFile(next(tmp_path.glob('*.zip'))) as archive:
        snapshot = tmp_path / 'restored.ini'
        snapshot.write_bytes(archive.read('settings/preferences.ini'))
    recovered = original_settings(str(snapshot), original_settings.Format.IniFormat)
    assert recovered.value('language') == 'ru'
    assert recovered.value('splitter') == QByteArray(b'\x00\x01\xff')
    assert Path(source.fileName()).read_bytes() == before
    dialog.reject()
