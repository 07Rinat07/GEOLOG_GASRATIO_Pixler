#!/usr/bin/env python3
"""Validate provenance coverage for bundled constructor assets.

Coverage validation is suitable for CI: every shipped lithology/symbol collection must have a
provenance record consistent with its asset manifest and every referenced image must exist.
Legal clearance is intentionally a stricter, explicit mode; unresolved source archives must not
be silently promoted to cleared merely because repository metadata declares general ownership.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RESOURCES = ROOT / "src" / "geoworkbench" / "resources"
CONSTRUCTOR_ASSETS = RESOURCES / "constructor_assets"
DEFAULT_PROVENANCE = RESOURCES / "asset-provenance.json"
EXPECTED_COLLECTIONS = {
    "constructor-lithology": ("lithology", "constructor_assets/lithology/manifest.json"),
    "constructor-symbols": ("symbols", "constructor_assets/symbols/manifest.json"),
}
CLEARANCE_FIELDS = ("rights_holder", "license_basis", "evidence_reference")


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


def validate_provenance(path: Path = DEFAULT_PROVENANCE) -> tuple[list[str], list[str]]:
    """Return coverage errors and unresolved collection ids."""

    errors: list[str] = []
    unresolved: list[str] = []
    try:
        payload = _load_object(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [f"cannot read provenance manifest: {exc}"], unresolved

    if payload.get("schema") != "geolog.asset-provenance.v1":
        errors.append("unsupported asset provenance schema")
    collections = payload.get("collections")
    if not isinstance(collections, list):
        return errors + ["collections must be an array"], unresolved

    records: dict[str, dict[str, Any]] = {}
    for raw in collections:
        if not isinstance(raw, dict):
            errors.append("collection entries must be objects")
            continue
        collection_id = raw.get("id")
        if not isinstance(collection_id, str) or not collection_id:
            errors.append("collection id must be a non-empty string")
            continue
        if collection_id in records:
            errors.append(f"duplicate collection id: {collection_id}")
            continue
        records[collection_id] = raw

        expected = EXPECTED_COLLECTIONS.get(collection_id)
        if expected is None:
            errors.append(f"unexpected provenance collection: {collection_id}")
            continue
        expected_kind, expected_manifest_rel = expected
        kind = raw.get("kind")
        if kind != expected_kind:
            errors.append(
                f"{collection_id}: expected kind {expected_kind!r}, got {kind!r}"
            )

        manifest_rel = raw.get("manifest_path")
        if manifest_rel != expected_manifest_rel:
            errors.append(
                f"{collection_id}: manifest_path must be {expected_manifest_rel!r}"
            )
            continue
        manifest_path = _resolve_below(RESOURCES, expected_manifest_rel)
        if manifest_path is None:
            errors.append(f"{collection_id}: manifest_path escapes resources directory")
            continue
        try:
            asset_manifest = _load_object(manifest_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"{collection_id}: cannot read asset manifest: {exc}")
            continue

        if asset_manifest.get("kind") != expected_kind:
            errors.append(
                f"{collection_id}: asset manifest kind is {asset_manifest.get('kind')!r}, "
                f"expected {expected_kind!r}"
            )
        expected_archives = raw.get("source_archives")
        actual_archives = asset_manifest.get("source_archives")
        if not isinstance(expected_archives, list) or sorted(expected_archives) != sorted(
            actual_archives if isinstance(actual_archives, list) else []
        ):
            errors.append(f"{collection_id}: source_archives do not match the asset manifest")

        assets = asset_manifest.get("assets")
        if not isinstance(assets, list) or not assets:
            errors.append(f"{collection_id}: asset manifest has no assets")
        else:
            for index, asset in enumerate(assets):
                if not isinstance(asset, dict):
                    errors.append(f"{collection_id}: asset #{index} is not an object")
                    continue
                for field in ("asset_path", "thumbnail_path"):
                    rel = asset.get(field)
                    if not isinstance(rel, str) or not rel:
                        errors.append(f"{collection_id}: asset #{index} has no {field}")
                        continue
                    candidate = _resolve_below(CONSTRUCTOR_ASSETS, rel)
                    if candidate is None:
                        errors.append(
                            f"{collection_id}: referenced {field} escapes constructor assets: {rel}"
                        )
                    elif not candidate.is_file():
                        errors.append(
                            f"{collection_id}: referenced {field} does not exist: {rel}"
                        )

        status = raw.get("review_status")
        if status not in {"unresolved", "cleared"}:
            errors.append(f"{collection_id}: invalid review_status {status!r}")
        elif status == "unresolved":
            unresolved.append(collection_id)
        else:
            missing = [field for field in CLEARANCE_FIELDS if not raw.get(field)]
            if missing:
                errors.append(
                    f"{collection_id}: cleared record is missing {', '.join(missing)}"
                )

    expected_ids = set(EXPECTED_COLLECTIONS)
    missing_ids = expected_ids - set(records)
    if missing_ids:
        errors.append("missing provenance collections: " + ", ".join(sorted(missing_ids)))
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
