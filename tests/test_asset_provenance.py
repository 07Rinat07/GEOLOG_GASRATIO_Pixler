from __future__ import annotations

import json
from pathlib import Path

from tools.check_asset_provenance import (
    DEFAULT_PROVENANCE,
    _resolve_collection_asset,
    main,
    validate_provenance,
)


def _write_manifest(tmp_path: Path, payload: dict[str, object]) -> Path:
    manifest = tmp_path / "asset-provenance.json"
    manifest.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return manifest


def test_bundled_constructor_assets_have_provenance_coverage() -> None:
    errors, unresolved = validate_provenance()

    assert errors == []
    assert set(unresolved) == {"constructor-lithology", "constructor-symbols"}


def test_strict_clearance_fails_closed_for_unresolved_archives() -> None:
    assert main(["--require-cleared"]) == 3


def test_cleared_record_requires_concrete_string_evidence(tmp_path: Path) -> None:
    payload = json.loads(DEFAULT_PROVENANCE.read_text(encoding="utf-8"))
    record = payload["collections"][0]
    record["review_status"] = "cleared"
    record["rights_holder"] = ["not-a-string"]
    record["license_basis"] = "   "
    record["evidence_reference"] = {"path": "not-a-string"}

    errors, unresolved = validate_provenance(_write_manifest(tmp_path, payload))

    assert any("missing non-empty string evidence" in item for item in errors)
    assert "constructor-lithology" not in unresolved
    assert "constructor-symbols" in unresolved


def test_source_archive_drift_is_rejected(tmp_path: Path) -> None:
    payload = json.loads(DEFAULT_PROVENANCE.read_text(encoding="utf-8"))
    payload["collections"][1]["source_archives"] = ["renamed-or-unknown.zip"]

    errors, _ = validate_provenance(_write_manifest(tmp_path, payload))

    assert any("source_archives do not match" in item for item in errors)


def test_malformed_source_archive_list_fails_closed_without_exception(tmp_path: Path) -> None:
    payload = json.loads(DEFAULT_PROVENANCE.read_text(encoding="utf-8"))
    payload["collections"][0]["source_archives"] = ["Litol_Bmp(2).zip", 123]

    errors, _ = validate_provenance(_write_manifest(tmp_path, payload))

    assert any("must be unique non-empty strings" in item for item in errors)


def test_asset_path_cannot_cross_collection_boundary() -> None:
    assert (
        _resolve_collection_asset(
            "lithology", "symbols/transparent/symbol-casing-shoe.png"
        )
        is None
    )
    assert _resolve_collection_asset(
        "symbols", "symbols/transparent/symbol-casing-shoe.png"
    ) is not None
