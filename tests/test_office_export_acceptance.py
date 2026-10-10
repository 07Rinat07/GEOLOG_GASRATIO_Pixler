"""The Windows Office acceptance corpus contains only validated synthetic data."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tools.capture_office_exports import create_office_acceptance_bundle


def test_office_acceptance_corpus_has_six_formats_for_each_language(tmp_path: Path) -> None:
    manifest = create_office_acceptance_bundle(tmp_path)
    assert manifest["schema"] == 1
    assert manifest["microsoft_office_desktop_review"] == "not_performed_by_ci"

    entries = manifest["files"]
    assert isinstance(entries, list)
    assert len(entries) == 18
    expected_names = {
        "interval.csv", "interval.xlsx", "interval.docx", "interval.html",
        "statistics.csv", "statistics.xlsx",
    }
    for language in ("ru", "kk", "en"):
        assert {entry["name"] for entry in entries if entry["language"] == language} == expected_names

    for entry in entries:
        target = tmp_path / str(entry["path"])
        contents = target.read_bytes()
        assert len(contents) == entry["size_bytes"]
        assert hashlib.sha256(contents).hexdigest() == entry["sha256"]

    persisted = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert persisted == manifest
    checklist = (tmp_path / "OPEN_IN_MICROSOFT_OFFICE.txt").read_text(encoding="utf-8")
    assert "Microsoft Excel" in checklist
    assert "Windows CI НЕ запускал Microsoft Office" in checklist
