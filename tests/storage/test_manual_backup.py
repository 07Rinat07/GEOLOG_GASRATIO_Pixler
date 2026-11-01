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



def test_readonly_inspection_reports_only_verified_archive_members(tmp_path):
    project = tmp_path / "well.geologpkg"
    project.write_bytes(b"geology" * 1000)
    settings = tmp_path / "preferences.ini"
    settings.write_text("[General]\nlanguage=kk\n")
    output = ManualBackupService().create(
        BackupPlan.build((project,), settings), tmp_path / "manual.zip"
    )
    original = output.read_bytes()
    result = ManualBackupService().inspect(output)
    assert result.total_bytes == project.stat().st_size + settings.stat().st_size
    assert [entry.path for entry in result.entries] == [
        "projects/0001.geologpkg", "settings/preferences.ini"
    ]
    assert result.entries[0].name == "well.geologpkg"
    assert result.created_at.endswith("+00:00")
    assert output.read_bytes() == original
    assert project.read_bytes() == b"geology" * 1000


def _rewrite_backup(path, *, manifest_change=None, payload_change=None, extra=None,
                    compression=None):
    from zipfile import ZIP_STORED

    with ZipFile(path) as original:
        manifest = json.loads(original.read("manifest.json"))
        contents = {
            name: original.read(name)
            for name in original.namelist() if name != "manifest.json"
        }
    if manifest_change:
        manifest_change(manifest)
    if payload_change:
        payload_change(contents)
    if extra:
        contents.update(extra)
    with ZipFile(path, "w", compression=ZIP_STORED if compression is None else compression) as archive:
        for name, data in contents.items():
            archive.writestr(name, data)
        archive.writestr("manifest.json", json.dumps(manifest).encode("utf-8"))


@pytest.fixture
def inspected_archive(tmp_path):
    project = tmp_path / "well.geologpkg"
    project.write_bytes(b"sample" * 100)
    output = ManualBackupService().create(BackupPlan.build((project,)), tmp_path / "backup.zip")
    return output


def test_inspection_rejects_modified_payload_without_touching_archive(inspected_archive):
    def corrupt(contents):
        contents["projects/0001.geologpkg"] = b"tamper" * 100

    _rewrite_backup(inspected_archive, payload_change=corrupt)
    before = inspected_archive.read_bytes()
    with pytest.raises(BackupError, match="checksum mismatch"):
        ManualBackupService().inspect(inspected_archive)
    assert inspected_archive.read_bytes() == before


@pytest.mark.parametrize("mutation", [
    lambda m: m.update(version=True),
    lambda m: m["entries"][0].update(size=-1),
    lambda m: m["entries"][0].update(sha256="0" * 63),
    lambda m: m["entries"][0].update(path="../well.geologpkg"),
    lambda m: m.update(created_at="not a date"),
])
def test_inspection_rejects_invalid_manifest(inspected_archive, mutation):
    _rewrite_backup(inspected_archive, manifest_change=mutation)
    with pytest.raises(BackupError):
        ManualBackupService().inspect(inspected_archive)


def test_inspection_rejects_unlisted_member_and_traversal(inspected_archive):
    _rewrite_backup(inspected_archive, extra={"../unlisted.geologpkg": b"evil"})
    with pytest.raises(BackupError, match="inventory does not match archive"):
        ManualBackupService().inspect(inspected_archive)


def test_inspection_rejects_duplicate_zip_members(inspected_archive):
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with ZipFile(inspected_archive, "a") as archive:
            archive.writestr("projects/0001.geologpkg", b"duplicate")
    with pytest.raises(BackupError, match="Duplicate"):
        ManualBackupService().inspect(inspected_archive)


def test_inspection_rejects_compressed_or_oversized_archives(inspected_archive):
    from zipfile import ZIP_DEFLATED

    with pytest.raises(BackupError, match="byte limit"):
        ManualBackupService().inspect(inspected_archive, max_total_bytes=5)
    _rewrite_backup(inspected_archive, compression=ZIP_DEFLATED)
    with pytest.raises(BackupError, match="Unsupported"):
        ManualBackupService().inspect(inspected_archive)


def test_inspection_rejects_invalid_zip_and_does_not_restore(tmp_path):
    output = tmp_path / "invalid.zip"
    output.write_bytes(b"not a ZIP")
    with pytest.raises(BackupError):
        ManualBackupService().inspect(output)
    assert list(tmp_path.iterdir()) == [output]



def test_inspection_rejects_symlink_zip_member(inspected_archive):
    import stat
    from zipfile import ZipInfo

    with ZipFile(inspected_archive) as archive:
        payload = archive.read("projects/0001.geologpkg")
        manifest = archive.read("manifest.json")
    with ZipFile(inspected_archive, "w") as archive:
        link = ZipInfo("projects/0001.geologpkg")
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(link, payload)
        archive.writestr("manifest.json", manifest)
    with pytest.raises(BackupError, match="Unsupported"):
        ManualBackupService().inspect(inspected_archive)


def test_inspection_rejects_duplicate_json_manifest_keys(inspected_archive):
    with ZipFile(inspected_archive) as archive:
        payload = archive.read("projects/0001.geologpkg")
        manifest = archive.read("manifest.json")
    duplicated = manifest.replace(b'"format":', b'"format":"wrong","format":', 1)
    with ZipFile(inspected_archive, "w") as archive:
        archive.writestr("projects/0001.geologpkg", payload)
        archive.writestr("manifest.json", duplicated)
    with pytest.raises(BackupError, match="Duplicate backup manifest key"):
        ManualBackupService().inspect(inspected_archive)


def test_restore_preflight_maps_verified_files_without_creating_destination(tmp_path):
    project = tmp_path / "well.geologpkg"
    project.write_bytes(b"saved project")
    settings = tmp_path / "preferences.ini"
    settings.write_bytes(b"settings snapshot")
    service = ManualBackupService()
    archive = service.create(
        BackupPlan.build((project,), settings), tmp_path / "backup.zip"
    )
    target = tmp_path / "restored"
    before = archive.read_bytes()

    plan = service.plan_restore(archive, target)
    assert plan.archive == archive.resolve()
    assert plan.destination == target
    assert plan.total_bytes == project.stat().st_size + settings.stat().st_size
    assert [(item.archive_path, item.relative_path) for item in plan.items] == [
        ("projects/0001.geologpkg", "projects/well.geologpkg"),
        ("settings/preferences.ini", "settings/preferences.ini"),
    ]
    assert all(len(item.sha256) == 64 for item in plan.items)
    assert not target.exists()
    assert archive.read_bytes() == before
    assert project.read_bytes() == b"saved project"


def test_restore_preflight_rejects_existing_destination_without_writing(
    tmp_path, inspected_archive
):
    target = tmp_path / "restored"
    target.mkdir()
    marker = target / "existing.geologpkg"
    marker.write_bytes(b"keep")
    with pytest.raises(BackupError, match="already exists"):
        ManualBackupService().plan_restore(inspected_archive, target)
    assert marker.read_bytes() == b"keep"


@pytest.mark.parametrize("name", ["CON.geologpkg", "bad?.geologpkg", "NUL.geologpkg"])
def test_restore_preflight_rejects_windows_unsafe_project_names(
    inspected_archive, tmp_path, name
):
    _rewrite_backup(
        inspected_archive,
        manifest_change=lambda manifest: manifest["entries"][0].update(name=name),
    )
    with pytest.raises(BackupError, match="Unsafe restore filename"):
        ManualBackupService().plan_restore(inspected_archive, tmp_path / "new")
    assert not (tmp_path / "new").exists()


def test_restore_preflight_rejects_casefold_colliding_project_names(tmp_path):
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first_dir.mkdir()
    second_dir.mkdir()
    first = first_dir / "Well.geologpkg"
    second = second_dir / "well.geologpkg"
    first.write_bytes(b"one")
    second.write_bytes(b"two")
    service = ManualBackupService()
    archive = service.create(
        BackupPlan.build((first, second)), tmp_path / "backup.zip"
    )
    with pytest.raises(BackupError, match="collide"):
        service.plan_restore(archive, tmp_path / "restored")
    assert not (tmp_path / "restored").exists()


def test_restore_preflight_rejects_tampered_archive_without_writing(
    inspected_archive, tmp_path
):
    _rewrite_backup(
        inspected_archive,
        payload_change=lambda contents: contents.update(
            {"projects/0001.geologpkg": b"tamper" * 100}
        ),
    )
    with pytest.raises(BackupError, match="checksum mismatch"):
        ManualBackupService().plan_restore(inspected_archive, tmp_path / "restored")
    assert not (tmp_path / "restored").exists()


def test_restore_preflight_rejects_unsafe_target_name_and_byte_limit(
    inspected_archive, tmp_path
):
    service = ManualBackupService()
    with pytest.raises(BackupError, match="Unsafe restore filename"):
        service.plan_restore(inspected_archive, tmp_path / "CON")
    with pytest.raises(BackupError, match="byte limit"):
        service.plan_restore(inspected_archive, tmp_path / "restored", max_total_bytes=1)
    assert not (tmp_path / "restored").exists()
