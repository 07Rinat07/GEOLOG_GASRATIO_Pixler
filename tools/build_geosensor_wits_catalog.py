"""Build a deterministic WITS Level 0 field catalog from GeoSensor GeoScape2.zip.

The tool never executes vendor binaries and never extracts the full archive. It reads only the
machine-readable ``GeoScape/WITS.csv`` entry and writes factual derived JSON/CSV artifacts.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import zipfile
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Iterable


CATALOG_SCHEMA_VERSION = 1
CATALOG_ID = "geosensor-wits-level0"
WITS_ENTRY = "GeoScape/WITS.csv"
EXPECTED_COLUMNS = (
    "ID",
    "Index",
    "Description",
    "ShortMnemonic",
    "LongMnemonic",
    "Type",
    "Length",
)
TYPE_TO_VALUE_KIND = {
    "A": "text",
    "S": "integer",
    "L": "integer",
    "F": "float",
    "D": "date",
    "T": "time",
}


class CatalogBuildError(ValueError):
    """Raised when the vendor archive cannot be converted safely."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_zip_path(name: str) -> None:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        raise CatalogBuildError(f"Unsafe ZIP path: {name!r}")


def read_wits_csv_from_archive(archive_path: Path) -> tuple[bytes, zipfile.ZipInfo]:
    try:
        archive = zipfile.ZipFile(archive_path)
    except (OSError, zipfile.BadZipFile) as exc:
        raise CatalogBuildError(f"Cannot open GeoScape archive {archive_path}: {exc}") from exc
    with archive:
        names = [item.filename for item in archive.infolist()]
        for name in names:
            _validate_zip_path(name)
        matches = [item for item in archive.infolist() if item.filename == WITS_ENTRY]
        if len(matches) != 1:
            raise CatalogBuildError(
                f"Expected exactly one {WITS_ENTRY!r} entry, found {len(matches)}"
            )
        info = matches[0]
        if info.flag_bits & 0x1:
            raise CatalogBuildError("Encrypted WITS.csv is not supported")
        if info.file_size > 10 * 1024 * 1024:
            raise CatalogBuildError("WITS.csv exceeds the 10 MiB safety limit")
        return archive.read(info), info


def parse_wits_csv(data: bytes) -> list[dict[str, object]]:
    try:
        text = data.decode("ascii")
    except UnicodeDecodeError as exc:
        raise CatalogBuildError(f"WITS.csv is not ASCII: {exc}") from exc
    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    if tuple(reader.fieldnames or ()) != EXPECTED_COLUMNS:
        raise CatalogBuildError(
            f"Unexpected WITS.csv columns: {reader.fieldnames!r}; expected {EXPECTED_COLUMNS!r}"
        )
    fields: list[dict[str, object]] = []
    seen: set[tuple[int, int]] = set()
    for line_no, row in enumerate(reader, start=2):
        try:
            record = int((row["ID"] or "").strip())
            item = int((row["Index"] or "").strip())
            description = (row["Description"] or "").strip()
            short = (row["ShortMnemonic"] or "").strip()
            long = (row["LongMnemonic"] or "").strip()
            declared_type = (row["Type"] or "").strip()
            declared_length = int((row["Length"] or "").strip())
        except (KeyError, ValueError) as exc:
            raise CatalogBuildError(f"Invalid WITS.csv row {line_no}: {exc}") from exc
        if not (0 <= record <= 99 and 0 <= item <= 99):
            raise CatalogBuildError(f"Invalid record/item at row {line_no}: {record}/{item}")
        if not description or not short or not long:
            raise CatalogBuildError(f"Empty description or mnemonic at row {line_no}")
        if declared_type not in TYPE_TO_VALUE_KIND:
            raise CatalogBuildError(
                f"Unsupported WITS declared type {declared_type!r} at row {line_no}"
            )
        if declared_length < 0:
            raise CatalogBuildError(f"Negative declared length at row {line_no}")
        key = (record, item)
        if key in seen:
            raise CatalogBuildError(f"Duplicate WITS record/item at row {line_no}: {key}")
        seen.add(key)
        fields.append(
            {
                "record": record,
                "item": item,
                "description": description,
                "shortMnemonic": short,
                "longMnemonic": long,
                "declaredType": declared_type,
                "valueKind": TYPE_TO_VALUE_KIND[declared_type],
                "declaredLength": declared_length,
            }
        )
    if not fields:
        raise CatalogBuildError("WITS.csv contains no fields")
    fields.sort(key=lambda item: (int(item["record"]), int(item["item"])))
    return fields


def build_catalog_payload(
    *,
    archive_path: Path,
    csv_bytes: bytes,
    fields: Iterable[dict[str, object]],
) -> dict[str, object]:
    return {
        "schemaVersion": CATALOG_SCHEMA_VERSION,
        "catalogId": CATALOG_ID,
        "title": "GeoSensor GeoScape WITS Level 0 field catalog",
        "version": 1,
        "source": {
            "vendor": "GeoSensor",
            "archive": archive_path.name,
            "archiveSha256": sha256_file(archive_path),
            "path": WITS_ENTRY,
            "fileSha256": sha256_bytes(csv_bytes),
            "notes": "Derived factual field dictionary. No executable code is included.",
        },
        "fields": list(fields),
    }


def write_outputs(payload: dict[str, object], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    fields = list(payload["fields"])  # type: ignore[arg-type]
    json_path = output_dir / "geosensor-wits-level0.json"
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    csv_path = output_dir / "wits_level0_fields.csv"
    columns = (
        "record",
        "item",
        "description",
        "shortMnemonic",
        "longMnemonic",
        "declaredType",
        "valueKind",
        "declaredLength",
    )
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(fields)  # type: ignore[arg-type]
    record_counts = Counter(int(item["record"]) for item in fields)  # type: ignore[index]
    type_counts = Counter(str(item["declaredType"]) for item in fields)  # type: ignore[index]
    summary = {
        "catalogId": payload["catalogId"],
        "fieldCount": len(fields),
        "recordCount": len(record_counts),
        "records": {str(key): value for key, value in sorted(record_counts.items())},
        "declaredTypes": dict(sorted(type_counts.items())),
        "standardHeader": {
            "01": "Well Identifier",
            "02": "Sidetrack/Hole Sect No.",
            "03": "Record Identifier",
            "04": "Sequence Identifier",
            "05": "Date",
            "06": "Time",
            "07": "Activity Code",
        },
    }
    (output_dir / "wits_level0_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def build_from_archive(archive_path: Path, output_dir: Path) -> dict[str, object]:
    csv_bytes, _info = read_wits_csv_from_archive(archive_path)
    fields = parse_wits_csv(csv_bytes)
    payload = build_catalog_payload(
        archive_path=archive_path,
        csv_bytes=csv_bytes,
        fields=fields,
    )
    write_outputs(payload, output_dir)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path, help="Path to the original GeoScape2.zip")
    parser.add_argument("output", type=Path, help="Directory for derived catalog artifacts")
    args = parser.parse_args()
    payload = build_from_archive(args.archive, args.output)
    print(
        json.dumps(
            {
                "catalogId": payload["catalogId"],
                "fields": len(payload["fields"]),  # type: ignore[arg-type]
                "output": str(args.output.resolve()),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
