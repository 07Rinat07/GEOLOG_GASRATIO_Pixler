"""Regression checks for the fail-closed directory publication primitive."""
from __future__ import annotations

import errno
from pathlib import Path
import sys

import pytest

from geoworkbench.storage import atomic_directory_publish as publishing


@pytest.mark.skipif(
    not (sys.platform.startswith("linux") or sys.platform == "win32"),
    reason="OS no-replace directory primitive is not implemented",
)
def test_publishes_complete_staged_folder_only_after_rename(tmp_path: Path) -> None:
    staged = tmp_path / ".stage"
    staged.mkdir()
    (staged / "projects").mkdir()
    (staged / "projects" / "well.geologpkg").write_bytes(b"validated")
    target = tmp_path / "restored"

    publishing.publish_new_directory(staged, target)

    assert (target / "projects" / "well.geologpkg").read_bytes() == b"validated"
    assert not staged.exists()


@pytest.mark.skipif(
    not (sys.platform.startswith("linux") or sys.platform == "win32"),
    reason="OS no-replace directory primitive is not implemented",
)
@pytest.mark.parametrize("existing_file", [False, True])
def test_existing_directory_is_never_replaced(tmp_path: Path, existing_file: bool) -> None:
    staged = tmp_path / ".stage"
    staged.mkdir()
    (staged / "payload").write_bytes(b"new")
    target = tmp_path / "restored"
    target.mkdir()
    if existing_file:
        (target / "keep").write_bytes(b"foreign")

    with pytest.raises(OSError) as captured:
        publishing.publish_new_directory(staged, target)

    assert captured.value.errno in {errno.EEXIST, errno.ENOTEMPTY, errno.EACCES}
    assert (staged / "payload").read_bytes() == b"new"
    if existing_file:
        assert (target / "keep").read_bytes() == b"foreign"
    else:
        assert list(target.iterdir()) == []


def test_rejects_cross_parent_and_non_directory(tmp_path: Path) -> None:
    staged = tmp_path / ".stage"
    staged.write_bytes(b"not a directory")
    with pytest.raises(ValueError, match="real directory"):
        publishing.publish_new_directory(staged, tmp_path / "restored")
    other = tmp_path / "elsewhere"
    other.mkdir()
    staged.unlink()
    staged.mkdir()
    with pytest.raises(ValueError, match="distinct siblings"):
        publishing.publish_new_directory(staged, other / "restored")
    assert staged.is_dir()


def test_does_not_fall_back_after_no_replace_unavailable(tmp_path: Path, monkeypatch) -> None:
    if not sys.platform.startswith("linux"):
        pytest.skip("Linux-specific primitive")
    staged = tmp_path / ".stage"
    staged.mkdir()
    target = tmp_path / "restored"

    def unsupported(*_args):
        raise publishing.AtomicDirectoryPublicationUnsupported("unavailable")

    monkeypatch.setattr(publishing, "_linux_rename_noreplace", unsupported)
    with pytest.raises(publishing.AtomicDirectoryPublicationUnsupported):
        publishing.publish_new_directory(staged, target)
    assert staged.is_dir()
    assert not target.exists()


def test_racing_destination_is_not_overwritten(tmp_path: Path, monkeypatch) -> None:
    if not sys.platform.startswith("linux"):
        pytest.skip("Linux-specific race injection")
    staged = tmp_path / ".stage"
    staged.mkdir()
    target = tmp_path / "restored"
    original = publishing._linux_rename_noreplace

    def create_target_before_syscall(source, destination):
        destination.mkdir()
        (destination / "foreign").write_bytes(b"mine")
        return original(source, destination)

    monkeypatch.setattr(publishing, "_linux_rename_noreplace", create_target_before_syscall)
    with pytest.raises(OSError) as captured:
        publishing.publish_new_directory(staged, target)
    assert captured.value.errno in (errno.EEXIST, errno.ENOTEMPTY)
    assert (target / "foreign").read_bytes() == b"mine"
    assert staged.is_dir()
