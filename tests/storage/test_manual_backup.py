from hashlib import sha256
import json
from zipfile import ZipFile

import pytest

from geoworkbench.storage.manual_backup import BackupError, BackupPlan, ManualBackupService


def test_selected_saved_files_and_settings_roundtrip_with_verified_manifest(tmp_path):
    project = tmp_path / 'well.geologpkg'
    project.write_bytes(b'project data' * 100000)
    excluded = tmp_path / 'excluded.geologpkg'
    excluded.write_bytes(b'not selected')
    settings = tmp_path / 'settings.ini'
    settings.write_text('[General]\nlanguage=ru\n')
    plan = BackupPlan.build((project, project), settings)
    assert plan.estimated_bytes == project.stat().st_size + settings.stat().st_size
    output = ManualBackupService().create(plan, tmp_path / 'backup.zip')
    with ZipFile(output) as archive:
        manifest = json.loads(archive.read('manifest.json'))
        assert len(manifest['entries']) == 2
        assert archive.read('projects/0001.geologpkg') == project.read_bytes()
        assert archive.read('settings/preferences.ini') == settings.read_bytes()
        for entry in manifest['entries']:
            data = archive.read(entry['path'])
            assert sha256(data).hexdigest() == entry['sha256']
            assert len(data) == entry['size']
        assert b'not selected' not in [archive.read(name) for name in archive.namelist()]
    assert not list(tmp_path.glob('.geolog-backup-*'))


def test_backup_never_overwrites_existing_target_or_source(tmp_path):
    project = tmp_path / 'project.geologpkg'
    project.write_bytes(b'original')
    plan = BackupPlan.build((project,))
    with pytest.raises(BackupError):
        ManualBackupService().create(plan, project)
    assert project.read_bytes() == b'original'


def test_source_change_aborts_and_removes_partial_archive(tmp_path, monkeypatch):
    project = tmp_path / 'project.geologpkg'
    project.write_bytes(b'original')
    service = ManualBackupService()
    original = service._copy
    def copy_and_change(source, target):
        result = original(source, target)
        project.write_bytes(b'changed')
        return result
    monkeypatch.setattr(service, '_copy', copy_and_change)
    output = tmp_path / 'backup.zip'
    with pytest.raises(BackupError, match='changed'):
        service.create(BackupPlan.build((project,)), output)
    assert not output.exists()
    assert not list(tmp_path.glob('.geolog-backup-*'))


def test_write_failure_preserves_previous_backups(tmp_path, monkeypatch):
    project = tmp_path / 'project.geologpkg'
    project.write_bytes(b'original')
    previous = tmp_path / 'previous.zip'
    previous.write_bytes(b'previous')
    service = ManualBackupService()
    def fail(*args):
        raise OSError('disk full')
    monkeypatch.setattr(service, '_copy', fail)
    output = tmp_path / 'new.zip'
    with pytest.raises(BackupError, match='disk full'):
        service.create(BackupPlan.build((project,)), output)
    assert previous.read_bytes() == b'previous'
    assert not output.exists()
    assert not list(tmp_path.glob('.geolog-backup-*'))


def test_no_selection_is_rejected_and_no_backup_appears(tmp_path):
    with pytest.raises(BackupError):
        BackupPlan.build(())
    assert list(tmp_path.iterdir()) == []
