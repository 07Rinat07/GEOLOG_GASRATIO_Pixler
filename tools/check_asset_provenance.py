#!/usr/bin/env python3
"""Validate provenance coverage for bundled constructor assets.

Coverage validation is suitable for CI: every shipped lithology/symbol collection must have a
provenance record consistent with its asset manifest and every referenced image must exist.
Legal clearance is intentionally a stricter, explicit mode; unresolved source archives must not
be silently promoted to cleared merely because repository metadata declares general ownership.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RESOURCES = ROOT / "src" / "geoworkbench" / "resources"
CONSTRUCTOR_ASSETS = RESOURCES / "constructor_assets"
DEVELOPMENT_CONSTRUCTOR_ASSETS = ROOT / "resources" / "constructor_assets"
DEFAULT_PROVENANCE = RESOURCES / "asset-provenance.json"
CLEARANCE_FIELDS = ("rights_holder", "license_basis", "evidence_reference")
ASSET_MANIFEST_SCHEMA = "geoworkbench.constructor-assets/v1"
PROVENANCE_SCHEMA = "geolog.asset-provenance.v1"


def _load_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _resolve_below(root: Path, relative: str) -> Path | None:
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None
    return candidate


def _resolve_collection_asset(
    collection_dir: str,
    relative: str,
    *,
    root: Path = CONSTRUCTOR_ASSETS,
) -> Path | None:
    candidate = _resolve_below(root, relative)
    if candidate is None:
        return None
    collection_root = (root / collection_dir).resolve()
    try:
        candidate.relative_to(collection_root)
    except ValueError:
        return None
    return candidate


def _string_list(value: Any) -> list[str] | None:
    if not isinstance(value, list):
        return None
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip() or item != item.strip():
            return None
        result.append(item)
    if len(result) != len(set(result)):
        return None
    return result


def _has_clearance_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _discover_collection_manifests(root: Path = CONSTRUCTOR_ASSETS) -> dict[str, Path]:
    """Return all one-level constructor collection manifests keyed by packaged relative path."""

    if not root.is_dir():
        return {}
    return {
        f"constructor_assets/{manifest.parent.name}/manifest.json": manifest
        for manifest in sorted(root.glob("*/manifest.json"))
        if manifest.is_file()
    }


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tree_files(root: Path) -> dict[str, Path]:
    if not root.is_dir():
        return {}
    return {
        path.relative_to(root).as_posix(): path
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def validate_asset_tree_parity(
    development_root: Path = DEVELOPMENT_CONSTRUCTOR_ASSETS,
    packaged_root: Path = CONSTRUCTOR_ASSETS,
) -> list[str]:
    """Require development and packaged constructor asset trees to be byte-identical."""

    errors: list[str] = []
    if not development_root.is_dir():
        errors.append(f"development constructor asset root is missing: {development_root}")
        return errors
    if not packaged_root.is_dir():
        errors.append(f"packaged constructor asset root is missing: {packaged_root}")
        return errors

    development = _tree_files(development_root)
    packaged = _tree_files(packaged_root)
    development_paths = set(development)
    packaged_paths = set(packaged)

    missing_from_package = sorted(development_paths - packaged_paths)
    missing_from_development = sorted(packaged_paths - development_paths)
    if missing_from_package:
        errors.append(
            "constructor assets missing from packaged tree: " + ", ".join(missing_from_package)
        )
    if missing_from_development:
        errors.append(
            "constructor assets missing from development tree: "
            + ", ".join(missing_from_development)
        )

    for relative in sorted(development_paths & packaged_paths):
        left = development[relative]
        right = packaged[relative]
        if left.stat().st_size != right.stat().st_size or _sha256_file(left) != _sha256_file(right):
            errors.append(f"constructor asset tree drift: {relative}")
    return errors


def validate_provenance(path: Path = DEFAULT_PROVENANCE) -> tuple[list[str], list[str]]:
    """Return coverage errors and unresolved collection ids."""

    errors = validate_asset_tree_parity()
    unresolved: list[str] = []
    try:
        payload = _load_object(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return errors + [f"cannot read provenance manifest: {exc}"], unresolved

    if payload.get("schema") != PROVENANCE_SCHEMA:
        errors.append("unsupported asset provenance schema")
    collections = payload.get("collections")
    if not isinstance(collections, list):
        return errors + ["collections must be an array"], unresolved

    discovered = _discover_collection_manifests()
    if not discovered:
        errors.append("no packaged constructor asset manifests were discovered")

    collection_dirs = {
        path.parent.name
        for path in CONSTRUCTOR_ASSETS.iterdir()
        if path.is_dir()
    } if CONSTRUCTOR_ASSETS.is_dir() else set()
    manifests_by_dir = {path.parent.name for path in discovered.values()}
    missing_manifests = sorted(collection_dirs - manifests_by_dir)
    if missing_manifests:
        errors.append(
            "constructor asset directories without manifest.json: " + ", ".join(missing_manifests)
        )
    loose_files = sorted(
        path.name for path in CONSTRUCTOR_ASSETS.iterdir() if path.is_file()
    ) if CONSTRUCTOR_ASSETS.is_dir() else []
    if loose_files:
        errors.append("loose constructor asset files are not allowed: " + ", ".join(loose_files))

    records: dict[str, dict[str, Any]] = {}
    manifest_records: dict[str, str] = {}
    for raw in collections:
        if not isinstance(raw, dict):
            errors.append("collection entries must be objects")
            continue
        collection_id = raw.get("id")
        if not isinstance(collection_id, str) or not collection_id.strip():
            errors.append("collection id must be a non-empty string")
            continue
        if collection_id in records:
            errors.append(f"duplicate collection id: {collection_id}")
            continue
        records[collection_id] = raw

        manifest_rel = raw.get("manifest_path")
        if not isinstance(manifest_rel, str) or not manifest_rel.strip():
            errors.append(f"{collection_id}: manifest_path must be a non-empty string")
            continue
        if manifest_rel in manifest_records:
            errors.append(
                f"{collection_id}: manifest_path is already covered by "
                f"{manifest_records[manifest_rel]}"
            )
            continue
        manifest_records[manifest_rel] = collection_id

        manifest_path = discovered.get(manifest_rel)
        if manifest_path is None:
            errors.append(f"{collection_id}: provenance references an undiscovered asset manifest")
            continue
        try:
            asset_manifest = _load_object(manifest_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"{collection_id}: cannot read asset manifest: {exc}")
            continue

        if asset_manifest.get("schema") != ASSET_MANIFEST_SCHEMA:
            errors.append(
                f"{collection_id}: unsupported asset manifest schema "
                f"{asset_manifest.get('schema')!r}"
            )
        actual_kind = asset_manifest.get("kind")
        if not isinstance(actual_kind, str) or not actual_kind.strip():
            errors.append(f"{collection_id}: asset manifest kind must be a non-empty string")
        elif raw.get("kind") != actual_kind:
            errors.append(
                f"{collection_id}: provenance kind {raw.get('kind')!r} does not match "
                f"asset manifest kind {actual_kind!r}"
            )

        expected_archives = _string_list(raw.get("source_archives"))
        actual_archives = _string_list(asset_manifest.get("source_archives"))
        if expected_archives is None:
            errors.append(
                f"{collection_id}: provenance source_archives must be unique non-empty strings"
            )
        if actual_archives is None:
            errors.append(
                f"{collection_id}: asset manifest source_archives must be unique non-empty strings"
            )
        if (
            expected_archives is not None
            and actual_archives is not None
            and sorted(expected_archives) != sorted(actual_archives)
        ):
            errors.append(f"{collection_id}: source_archives do not match the asset manifest")
        allowed_archives = set(actual_archives or [])

        assets = asset_manifest.get("assets")
        if not isinstance(assets, list) or not assets:
            errors.append(f"{collection_id}: asset manifest has no assets")
        else:
            asset_ids: set[str] = set()
            paths_by_field: dict[str, set[Path]] = {
                "asset_path": set(),
                "thumbnail_path": set(),
            }
            collection_dir = manifest_path.parent.name
            for index, asset in enumerate(assets):
                if not isinstance(asset, dict):
                    errors.append(f"{collection_id}: asset #{index} is not an object")
                    continue

                asset_id = asset.get("id")
                if not isinstance(asset_id, str) or not asset_id.strip():
                    errors.append(f"{collection_id}: asset #{index} has no valid id")
                elif asset_id in asset_ids:
                    errors.append(f"{collection_id}: duplicate asset id: {asset_id}")
                else:
                    asset_ids.add(asset_id)

                asset_archives = _string_list(asset.get("source_archives"))
                if not asset_archives:
                    errors.append(f"{collection_id}: asset #{index} has invalid source_archives")
                elif not set(asset_archives).issubset(allowed_archives):
                    errors.append(
                        f"{collection_id}: asset #{index} references source archive outside "
                        "the collection manifest"
                    )

                for field in ("asset_path", "thumbnail_path"):
                    rel = asset.get(field)
                    if not isinstance(rel, str) or not rel:
                        errors.append(f"{collection_id}: asset #{index} has no {field}")
                        continue
                    candidate = _resolve_collection_asset(collection_dir, rel)
                    if candidate is None:
                        errors.append(
                            f"{collection_id}: referenced {field} escapes or crosses the "
                            f"{collection_dir} collection: {rel}"
                        )
                    elif not candidate.is_file():
                        errors.append(f"{collection_id}: referenced {field} does not exist: {rel}")
                    elif candidate in paths_by_field[field]:
                        errors.append(f"{collection_id}: duplicate referenced {field}: {rel}")
                    else:
                        paths_by_field[field].add(candidate)

        status = raw.get("review_status")
        if status not in {"unresolved", "cleared"}:
            errors.append(f"{collection_id}: invalid review_status {status!r}")
        elif status == "unresolved":
            unresolved.append(collection_id)
        else:
            missing = [
                field for field in CLEARANCE_FIELDS if not _has_clearance_text(raw.get(field))
            ]
            if missing:
                errors.append(
                    f"{collection_id}: cleared record is missing non-empty string evidence: "
                    + ", ".join(missing)
                )

    missing_records = sorted(set(discovered) - set(manifest_records))
    if missing_records:
        errors.append(
            "asset manifests missing provenance records: " + ", ".join(missing_records)
        )
    return errors, unresolved


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_PROVENANCE)
    parser.add_argument(
        "--require-cleared",
        action="store_true",
        help="Fail unless every covered collection has evidence-backed clearance.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    errors, unresolved = validate_provenance(args.manifest.resolve())
    if errors:
        for error in errors:
            print(f"[FAIL] {error}", file=sys.stderr)
        return 2
    if unresolved:
        print("Asset provenance coverage is complete; legal review remains unresolved for:")
        for collection_id in unresolved:
            print(f"  - {collection_id}")
        if args.require_cleared:
            print("Evidence-backed clearance is required.", file=sys.stderr)
            return 3
        return 0
    print("Asset provenance coverage and clearance are complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
