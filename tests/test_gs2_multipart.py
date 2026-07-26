from __future__ import annotations

from pathlib import Path
import struct
import zipfile

import numpy as np
import pytest

from geoworkbench.importers.gs2 import Gs2ContainerError, inspect_gs2
from geoworkbench.importers.gs2.multipart import (
    Gs2MultipartError,
    read_gs2_multipart,
)
from geoworkbench.importers.paradox.progress import paradox_progress_state


def _encode_number(value: float) -> bytes:
    payload = bytearray(struct.pack(">d", value))
    if payload[0] & 0x80:
        return bytes((~byte) & 0xFF for byte in payload)
    payload[0] |= 0x80
    return bytes(payload)


def _paradox_time_table(
    times: tuple[float, ...],
    *,
    time_name: str = "Time",
    second_type: int = 6,
) -> bytes:
    header_size = 0x800
    block_size = 0x800
    record_size = 16
    header = bytearray(header_size)
    struct.pack_into("<HH", header, 0, record_size, header_size)
    header[4:6] = bytes((2, block_size // 1024))
    struct.pack_into("<I", header, 6, len(times))
    struct.pack_into("<HHH", header, 0x0C, 1, 1, 1)
    struct.pack_into("<H", header, 0x21, 2)
    header[0x39] = 12
    struct.pack_into("<H", header, 0x6A, 1251)
    header[0x78:0x7C] = bytes((6, 8, second_type, 8))
    cursor = 0x7C
    for value in (
        b"TIME_PART.db\x00",
        time_name.encode("ascii") + b"\x00",
        b"S103\x00",
    ):
        header[cursor : cursor + len(value)] = value
        cursor += len(value)
    header[cursor : cursor + 4] = struct.pack("<HH", 1, 2)

    block = bytearray(block_size)
    struct.pack_into("<HHh", block, 0, 0, 0, (len(times) - 1) * record_size)
    cursor = 6
    for index, moment in enumerate(times):
        payload = _encode_number(moment) + _encode_number(10.0 + index)
        block[cursor : cursor + record_size] = payload
        cursor += record_size
    return bytes(header + block)


def _write_multipart_gs2(
    path: Path,
    first_times: tuple[float, ...],
    second_times: tuple[float, ...],
) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("GS2.mdb", b"metadata")
        archive.writestr("GS2#1.db", _paradox_time_table(first_times))
        archive.writestr("GS2#1_1.db", _paradox_time_table(second_times))


def test_discovers_and_merges_ordered_time_parts(tmp_path: Path) -> None:
    source = tmp_path / "series.gs2"
    _write_multipart_gs2(source, (100.0, 101.0), (102.0, 103.0))
    manifest = inspect_gs2(source)

    assert len(manifest.multipart_groups) == 1
    group = manifest.multipart_groups[0]
    assert group.member_names == ("GS2#1.db", "GS2#1_1.db")
    assert group.record_count == 4

    table = read_gs2_multipart(source, member_names=group.member_names)

    assert table.source == source.resolve()
    assert table.rows_read == 4
    np.testing.assert_allclose(table.columns["Time"].values, [100, 101, 102, 103])
    np.testing.assert_allclose(table.columns["S103"].values, [10, 11, 10, 11])
    assert table.columns["Time"].raw_values is None
    assert not [issue for issue in table.issues if issue.code == "gs2-time-gap"]


def test_rejects_overlapping_time_parts(tmp_path: Path) -> None:
    source = tmp_path / "overlap.gs2"
    _write_multipart_gs2(source, (100.0, 101.0), (101.0, 102.0))
    group = inspect_gs2(source).multipart_groups[0]

    with pytest.raises(Gs2MultipartError, match="перекрывается"):
        read_gs2_multipart(source, member_names=group.member_names)


def test_reports_large_time_gap(tmp_path: Path) -> None:
    source = tmp_path / "gap.gs2"
    _write_multipart_gs2(source, (100.0, 101.0), (1000.0, 1001.0))
    group = inspect_gs2(source).multipart_groups[0]

    table = read_gs2_multipart(source, member_names=group.member_names)

    gaps = [issue for issue in table.issues if issue.code == "gs2-time-gap"]
    assert len(gaps) == 1
    assert gaps[0].details["gap_seconds"] == 899.0


def test_rejects_series_above_decoded_memory_limit(tmp_path: Path) -> None:
    source = tmp_path / "memory.gs2"
    _write_multipart_gs2(source, (100.0, 101.0), (102.0, 103.0))
    group = inspect_gs2(source).multipart_groups[0]

    with pytest.raises(Gs2MultipartError, match="лимит памяти"):
        read_gs2_multipart(
            source,
            member_names=group.member_names,
            max_output_bytes=1,
        )


def test_progress_is_monotonic_across_extraction_and_parts(tmp_path: Path) -> None:
    source = tmp_path / "progress.gs2"
    _write_multipart_gs2(source, (100.0, 101.0), (102.0, 103.0))
    group = inspect_gs2(source).multipart_groups[0]
    progress: list[float] = []

    read_gs2_multipart(
        source,
        member_names=group.member_names,
        progress=lambda phase, current, total: progress.append(
            paradox_progress_state(phase, current, total).overall_ratio
        ),
    )

    assert progress
    assert progress == sorted(progress)


def test_cancellation_is_checked_during_extraction(tmp_path: Path) -> None:
    source = tmp_path / "cancel.gs2"
    _write_multipart_gs2(source, (100.0, 101.0), (102.0, 103.0))
    group = inspect_gs2(source).multipart_groups[0]
    checks = 0

    def cancelled() -> bool:
        nonlocal checks
        checks += 1
        return checks >= 3

    with pytest.raises(Gs2ContainerError, match="отмен"):
        read_gs2_multipart(
            source,
            member_names=group.member_names,
            cancelled=cancelled,
        )


def test_does_not_group_tables_without_time_index(tmp_path: Path) -> None:
    source = tmp_path / "depth-parts.gs2"
    with zipfile.ZipFile(source, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("GS2.mdb", b"metadata")
        archive.writestr(
            "GS2#1.db",
            _paradox_time_table((100.0, 101.0), time_name="Depth"),
        )
        archive.writestr(
            "GS2#1_1.db",
            _paradox_time_table((102.0, 103.0), time_name="Depth"),
        )

    assert inspect_gs2(source).multipart_groups == ()


def test_does_not_group_parts_with_different_field_types(tmp_path: Path) -> None:
    source = tmp_path / "schema-parts.gs2"
    with zipfile.ZipFile(source, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("GS2.mdb", b"metadata")
        archive.writestr("GS2#1.db", _paradox_time_table((100.0, 101.0)))
        archive.writestr(
            "GS2#1_1.db",
            _paradox_time_table((102.0, 103.0), second_type=5),
        )

    assert inspect_gs2(source).multipart_groups == ()
