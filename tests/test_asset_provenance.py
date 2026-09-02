from __future__ import annotations

import json
from pathlib import Path
import tomllib

from tools.check_asset_provenance import (
    DEFAULT_PROVENANCE,
    _collection_dirs,
    _discover_collection_manifests,
    _resolve_collection_asset,
    main,
    validate_asset_tree_parity,
    validate_provenance,
)


ROOT = Path(__file__).resolve().parents[1]


def _write_manifest(tmp_path: Path, payload: dict[str, object]) -> Path:
    manifest = tmp_path / "asset-provenance.json"
    manifest.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return manifest


def test_bundled_constructor_assets_have_provenance_coverage() -> None:
    errors, unresolved = validate_provenance()

    assert errors == []
    assert set(unresolved) == {"constructor-lithology", "constructor-symbols"}


def test_development_and_packaged_constructor_asset_trees_are_identical() -> None:
    assert validate_asset_tree_parity() == []


def test_collection_directory_discovery_uses_child_names(tmp_path: Path) -> None:
    for collection in ("lithology", "symbols", "future-assets"):
        (tmp_path / collection).mkdir()

    assert _collection_dirs(tmp_path) == {"lithology", "symbols", "future-assets"}


def test_collection_manifest_discovery_is_dynamic(tmp_path: Path) -> None:
    for collection in ("lithology", "symbols", "future-assets"):
        target = tmp_path / collection / "manifest.json"
        target.parent.mkdir(parents=True)
        target.write_text("{}", encoding="utf-8")

    discovered = _discover_collection_manifests(tmp_path)

    assert set(discovered) == {
        "constructor_assets/lithology/manifest.json",
        "constructor_assets/symbols/manifest.json",
        "constructor_assets/future-assets/manifest.json",
    }


def test_provenance_manifest_is_in_packaged_resource_patterns() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    package_data = pyproject["tool"]["setuptools"]["package-data"]["geoworkbench"]

    assert "resources/*.json" in package_data


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
