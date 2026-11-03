"""Read-only staging CLI must never authorize cleanup or change foreign files."""
from __future__ import annotations

import json

from tools import inspect_restore_staging


def test_cli_lists_candidates_without_reading_or_changing_contents(tmp_path, capsys):
    stage = tmp_path / ".geolog-restore-a"
    stage.mkdir()
    foreign = stage / "unrelated.bin"
    foreign.write_bytes(b"foreign user data")
    (tmp_path / "unrelated").mkdir()

    assert inspect_restore_staging.main([str(tmp_path)]) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    result = json.loads(captured.out)
    assert result["read_only"] is True
    assert result["ownership_verified"] is False
    assert result["deletion_authorized"] is False
    assert [row["path"] for row in result["candidates"]] == [str(stage)]
    assert result["candidates"][0]["inode"] == stage.lstat().st_ino
    assert foreign.read_bytes() == b"foreign user data"
    assert "unrelated.bin" not in captured.out


def test_cli_reports_empty_inventory_without_claiming_ownership(tmp_path, capsys):
    assert inspect_restore_staging.main([str(tmp_path)]) == 0
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert result["candidates"] == []
    assert result["deletion_authorized"] is False
    assert captured.err == ""


def test_cli_refuses_nonexistent_parent_and_emits_no_report(tmp_path, capsys):
    assert inspect_restore_staging.main([str(tmp_path / "missing")]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Staging inspection failed" in captured.err


def test_cli_fails_closed_if_candidate_changes_before_report(tmp_path, capsys, monkeypatch):
    stage = tmp_path / ".geolog-restore-a"
    stage.mkdir()
    foreign = stage / "foreign.txt"
    foreign.write_text("keep", encoding="utf-8")
    monkeypatch.setattr(inspect_restore_staging, "recheck_staging_candidate", lambda _: False)

    assert inspect_restore_staging.main([str(tmp_path)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "changed before report" in captured.err
    assert foreign.read_text(encoding="utf-8") == "keep"


def test_cli_rejects_parent_containing_dotdot(tmp_path, capsys):
    child = tmp_path / "child"
    child.mkdir()
    assert inspect_restore_staging.main([str(child / ".." / "child")]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "cannot contain" in captured.err
