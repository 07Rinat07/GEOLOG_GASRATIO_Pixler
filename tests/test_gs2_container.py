from __future__ import annotations

from pathlib import Path
import random
import struct
import zipfile

import pytest

from geoworkbench.importers.gs2 import (
    Gs2ContainerError,
    Gs2ContainerLimits,
    extract_gs2,
    inspect_gs2,
)


def write_gs2(path: Path, members: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in members.items():
            archive.writestr(name, payload)


def paradox_depth_header() -> bytes:
    header = bytearray(2048)
    struct.pack_into("<HH", header, 0, 16, 2048)
    header[4:6] = bytes((2, 32))
    struct.pack_into("<I", header, 6, 1)
    struct.pack_into("<H", header, 0x21, 2)
    header[0x78:0x7C] = bytes((21, 8, 6, 8))
    names = b"Time\x00Depth\x00"
    start = 0x7C
    header[start : start + len(names)] = names
    marker = b"\x01\x00\x02\x00"
    header[start + len(names) : start + len(names) + len(marker)] = marker
    return bytes(header)


def test_inspect_and_extract_valid_gs2(tmp_path: Path) -> None:
    source = tmp_path / "well.gs2"
    write_gs2(
        source,
        {
            "GS2.mdb": b"access-metadata",
            "GS2#1.db": b"\x00\x01\x02",
            "GS2#1_1.db": b"\x03\x04",
            "notes.txt": b"source remains unchanged",
        },
    )
    original = source.read_bytes()

    manifest = inspect_gs2(source)

    assert manifest.metadata_member.name == "GS2.mdb"
    assert [item.name for item in manifest.data_members] == ["GS2#1.db", "GS2#1_1.db"]
    with extract_gs2(source) as (directory, extracted_manifest):
        assert extracted_manifest == manifest
        assert (directory / "GS2.mdb").read_bytes() == b"access-metadata"
        assert (directory / "GS2#1_1.db").read_bytes() == b"\x03\x04"
    assert not directory.exists()
    assert source.read_bytes() == original


@pytest.mark.parametrize(
    "members",
    [
        {"GS2#1.db": b"data"},
        {"GS2.mdb": b"metadata"},
        {"GS2.mdb": b"metadata", "../GS2#1.db": b"data"},
        {"GS2.mdb": b"metadata", "GS2#1.db": b"data", "gs2#1.DB": b"duplicate"},
    ],
)
def test_rejects_incomplete_or_unsafe_container(
    tmp_path: Path,
    members: dict[str, bytes],
) -> None:
    source = tmp_path / "invalid.gs2"
    write_gs2(source, members)

    with pytest.raises(Gs2ContainerError):
        inspect_gs2(source)


def test_rejects_non_zip_and_safety_limit(tmp_path: Path) -> None:
    source = tmp_path / "not-a-container.gs2"
    source.write_bytes(b"not zip")
    with pytest.raises(Gs2ContainerError, match="ZIP"):
        inspect_gs2(source)

    write_gs2(source, {"GS2.mdb": b"metadata", "GS2#1.db": b"123456"})
    with pytest.raises(Gs2ContainerError, match="лимит"):
        inspect_gs2(source, limits=Gs2ContainerLimits(max_member_size=5))


def test_accepts_legitimate_sparse_geoscape_table(tmp_path: Path) -> None:
    source = tmp_path / "sparse.gs2"
    write_gs2(
        source,
        {
            "GS2.mdb": b"metadata",
            # Real GS2 sparse tables can compress at approximately 589:1.
            "GS2#10.db": random.Random(0).randbytes(300) + b"\x00" * 599_700,
        },
    )

    assert inspect_gs2(source).data_members[0].size == 600_000


def test_identifies_paradox_depth_table_and_prefers_it(tmp_path: Path) -> None:
    source = tmp_path / "depth.gs2"
    write_gs2(
        source,
        {
            "GS2.mdb": b"metadata",
            "GS2#101.db": paradox_depth_header(),
        },
    )

    manifest = inspect_gs2(source)

    assert manifest.preferred_table is not None
    assert manifest.preferred_table.member_name == "GS2#101.db"
    assert manifest.preferred_table.field_names == ("Time", "Depth")
