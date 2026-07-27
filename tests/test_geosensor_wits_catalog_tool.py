from __future__ import annotations

import csv
import io
import json
import zipfile
from pathlib import Path

import pytest

from tools.build_geosensor_wits_catalog import (
    CatalogBuildError,
    build_from_archive,
    parse_wits_csv,
)


def _csv_bytes() -> bytes:
    stream = io.StringIO()
    writer = csv.writer(stream, delimiter=";", lineterminator="\r\n")
    writer.writerow(
        [
            "ID",
            "Index",
            "Description",
            "ShortMnemonic",
            "LongMnemonic",
            "Type",
            "Length",
        ]
    )
    writer.writerow([1, 1, "Well Identifier", "WID", "WELLID", "A", 16])
    writer.writerow([1, 4, "Sequence Identifier", "SQID", "SEQID", "L", 4])
    writer.writerow([2, 23, "Cost/Distance (inst)", "CPDI", "CPDI", "F", 0])
    return stream.getvalue().encode("ascii")


def test_tool_builds_deterministic_catalog_without_extracting_vendor_archive(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "GeoScape2.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as target:
        target.writestr("GeoScape/WITS.csv", _csv_bytes())
        target.writestr("GeoScape/GSWITSProxy.exe", b"not-executed")

    first = tmp_path / "first"
    second = tmp_path / "second"
    payload_first = build_from_archive(archive, first)
    payload_second = build_from_archive(archive, second)

    assert payload_first == payload_second
    assert payload_first["source"]["path"] == "GeoScape/WITS.csv"  # type: ignore[index]
    assert len(payload_first["fields"]) == 3  # type: ignore[arg-type]
    assert (first / "geosensor-wits-level0.json").read_bytes() == (
        second / "geosensor-wits-level0.json"
    ).read_bytes()
    summary = json.loads((first / "wits_level0_summary.json").read_text())
    assert summary["standardHeader"]["04"] == "Sequence Identifier"


def test_tool_rejects_duplicate_record_item() -> None:
    data = _csv_bytes() + b"1;4;Duplicate;SQID;SEQID;L;4\r\n"
    with pytest.raises(CatalogBuildError, match="Duplicate"):
        parse_wits_csv(data)


def test_tool_rejects_unsafe_archive_paths(tmp_path: Path) -> None:
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as target:
        target.writestr("../GeoScape/WITS.csv", _csv_bytes())
    with pytest.raises(CatalogBuildError, match="Unsafe ZIP path"):
        build_from_archive(archive, tmp_path / "out")
