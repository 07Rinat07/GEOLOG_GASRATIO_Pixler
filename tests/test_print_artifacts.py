from __future__ import annotations

import json

from geoworkbench.services.print_artifacts import (
    PRINT_ARTIFACT_MARKER_NAME,
    cleanup_legacy_physical_print_copies,
)


def test_cleanup_adopts_dedicated_legacy_directory_and_removes_generated_copies(
    tmp_path,
) -> None:
    first = tmp_path / "Планшет_20260809_120000_000001.pdf"
    second = tmp_path / "LAS gases_20260809_120001_000002.PDF"
    interrupted = tmp_path / ".Планшет_20260809_120002_000003.pdf.xu0eico8.tmp"
    first.write_bytes(b"first-copy")
    second.write_bytes(b"second-copy")
    interrupted.write_bytes(b"partial-copy")

    result = cleanup_legacy_physical_print_copies(tmp_path)

    assert result.scanned_files == 3
    assert result.deleted_files == 3
    assert result.freed_bytes == (
        len(b"first-copy") + len(b"second-copy") + len(b"partial-copy")
    )
    assert result.failed_files == 0
    assert result.skipped_reason is None
    assert not first.exists()
    assert not second.exists()
    assert not interrupted.exists()
    assert (tmp_path / PRINT_ARTIFACT_MARKER_NAME).is_file()


def test_cleanup_fails_closed_when_directory_contains_user_file(tmp_path) -> None:
    generated = tmp_path / "Tablet_20260809_120000_000001.pdf"
    user_file = tmp_path / "final-report.pdf"
    generated.write_bytes(b"generated")
    user_file.write_bytes(b"user-output")

    result = cleanup_legacy_physical_print_copies(tmp_path)

    assert result.deleted_files == 0
    assert result.skipped_reason == "unowned_contents"
    assert generated.read_bytes() == b"generated"
    assert user_file.read_bytes() == b"user-output"
    assert not (tmp_path / PRINT_ARTIFACT_MARKER_NAME).exists()


def test_cleanup_rejects_foreign_marker_without_deleting_files(tmp_path) -> None:
    generated = tmp_path / "Tablet_20260809_120000_000001.pdf"
    generated.write_bytes(b"generated")
    (tmp_path / PRINT_ARTIFACT_MARKER_NAME).write_text(
        json.dumps(
            {
                "schema_version": 1,
                "owner": "another-application",
                "root": str(tmp_path.resolve()),
            }
        ),
        encoding="utf-8",
    )

    result = cleanup_legacy_physical_print_copies(tmp_path)

    assert result.deleted_files == 0
    assert result.skipped_reason == "marker_owner_mismatch"
    assert generated.read_bytes() == b"generated"


def test_cleanup_with_valid_marker_removes_only_known_future_copies(tmp_path) -> None:
    initial = tmp_path / "Tablet_20260809_120000_000001.pdf"
    initial.write_bytes(b"initial")
    cleanup_legacy_physical_print_copies(tmp_path)
    future = tmp_path / "Tablet_20260810_120000_000002.pdf"
    future.write_bytes(b"future")

    result = cleanup_legacy_physical_print_copies(tmp_path)

    assert result.deleted_files == 1
    assert result.freed_bytes == len(b"future")
    assert not future.exists()
    assert (tmp_path / PRINT_ARTIFACT_MARKER_NAME).is_file()
