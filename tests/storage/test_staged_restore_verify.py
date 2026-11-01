"""Headless staging verification: no archive extraction or publication."""
import pytest

from geoworkbench.storage.manual_backup import (
    BackupError, BackupPlan, BackupRestorePlan, ManualBackupService,
)
from geoworkbench.storage.staged_restore_verify import verify_staged_restore


@pytest.fixture
def staged(tmp_path):
    project = tmp_path / "well.geologpkg"
    project.write_bytes(b"geology" * 128)
    settings = tmp_path / "prefs.ini"
    settings.write_bytes(b"language=ru")
    service = ManualBackupService()
    archive = service.create(BackupPlan.build((project,), settings), tmp_path / "backup.zip")
    plan = service.plan_restore(archive, tmp_path / "restored")
    stage = tmp_path / ".geolog-restore-test"
    (stage / "projects").mkdir(parents=True)
    (stage / "settings").mkdir()
    (stage / "projects" / project.name).write_bytes(project.read_bytes())
    (stage / "settings" / "preferences.ini").write_bytes(settings.read_bytes())
    return plan, stage


def test_verified_staging_is_read_only_and_does_not_publish(staged):
    plan, stage = staged
    original = {
        path.relative_to(stage): path.read_bytes()
        for path in stage.rglob("*") if path.is_file()
    }
    assert verify_staged_restore(plan, stage) is None
    assert not plan.destination.exists()
    assert original == {
        path.relative_to(stage): path.read_bytes()
        for path in stage.rglob("*") if path.is_file()
    }


@pytest.mark.parametrize("mutation", ["missing", "extra", "tampered", "extra_directory"])
def test_staging_rejects_missing_extra_or_changed_content(staged, mutation):
    plan, stage = staged
    project = stage / "projects" / "well.geologpkg"
    if mutation == "missing":
        project.unlink()
    elif mutation == "extra":
        (stage / "projects" / "foreign.geologpkg").write_bytes(b"foreign")
    elif mutation == "extra_directory":
        (stage / "foreign").mkdir()
    else:
        project.write_bytes(b"tamper!" * 128)
    with pytest.raises(BackupError):
        verify_staged_restore(plan, stage)
    assert not plan.destination.exists()


def test_staging_rejects_symlink_and_wrong_parent(staged, tmp_path):
    plan, stage = staged
    project = stage / "projects" / "well.geologpkg"
    project.unlink()
    outside = tmp_path / "outside.geologpkg"
    outside.write_bytes(b"geology" * 128)
    try:
        project.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("Filesystem cannot create symlinks")
    with pytest.raises(BackupError):
        verify_staged_restore(plan, stage)
    other = tmp_path / "other"
    other.mkdir()
    with pytest.raises(BackupError, match="Unsafe staging location"):
        verify_staged_restore(plan, other / stage.name)


def test_staging_rejects_destination_collision(staged):
    plan, stage = staged
    plan.destination.mkdir()
    with pytest.raises(BackupError, match="occupied"):
        verify_staged_restore(plan, stage)


def test_staging_rejects_duplicate_planned_output(staged):
    plan, stage = staged
    bad = BackupRestorePlan(
        plan.archive, plan.destination, plan.items + (plan.items[0],),
        plan.total_bytes + plan.items[0].size,
    )
    with pytest.raises(BackupError, match="Duplicate"):
        verify_staged_restore(bad, stage)


def test_staging_rejects_replaced_file_before_final_validation(staged, monkeypatch):
    from geoworkbench.storage import staged_restore_verify as verifier

    plan, stage = staged
    project = stage / "projects" / "well.geologpkg"
    original = verifier._snapshot
    file_checks = 0

    def replace_after_close(path, *, directory):
        nonlocal file_checks
        if path == project and not directory:
            file_checks += 1
            if file_checks == 2:
                # The verification stream is now closed; works on Windows too.
                content = project.read_bytes()
                project.unlink()
                project.write_bytes(content)
        return original(path, directory=directory)

    monkeypatch.setattr(verifier, "_snapshot", replace_after_close)
    with pytest.raises(BackupError, match="replaced"):
        verify_staged_restore(plan, stage)
    assert file_checks == 2


def test_staging_rejects_new_file_added_during_hash(staged, monkeypatch):
    plan, stage = staged
    original = ManualBackupService._copy
    injected = False

    def add_extra(self, source, target):
        nonlocal injected
        result = original(self, source, target)
        if not injected:
            injected = True
            (stage / "projects" / "foreign.geologpkg").write_bytes(b"foreign")
        return result

    monkeypatch.setattr(ManualBackupService, "_copy", add_extra)
    with pytest.raises(BackupError, match="changed"):
        verify_staged_restore(plan, stage)
    assert injected
