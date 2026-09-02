from __future__ import annotations

import json
from pathlib import Path

from tools.check_asset_provenance import DEFAULT_PROVENANCE, main, validate_provenance


def test_bundled_constructor_assets_have_provenance_coverage() -> None:
    errors, unresolved = validate_provenance()

    assert errors == []
    assert set(unresolved) == {"constructor-lithology", "constructor-symbols"}


def test_strict_clearance_fails_closed_for_unresolved_archives() -> None:
    assert main(["--require-cleared"]) == 3


def test_cleared_record_requires_concrete_evidence(tmp_path: Path) -> None:
    payload = json.loads(DEFAULT_PROVENANCE.read_text(encoding="utf-8"))
    payload["collections"][0]["review_status"] = "cleared"
    manifest = tmp_path / "asset-provenance.json"
    manifest.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    errors, unresolved = validate_provenance(manifest)

    assert any("cleared record is missing" in item for item in errors)
    assert "constructor-lithology" not in unresolved
    assert "constructor-symbols" in unresolved


def test_source_archive_drift_is_rejected(tmp_path: Path) -> None:
    payload = json.loads(DEFAULT_PROVENANCE.read_text(encoding="utf-8"))
    payload["collections"][1]["source_archives"] = ["renamed-or-unknown.zip"]
    manifest = tmp_path / "asset-provenance.json"
    manifest.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    errors, _ = validate_provenance(manifest)

    assert any("source_archives do not match" in item for item in errors)
