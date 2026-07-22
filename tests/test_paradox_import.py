from __future__ import annotations

from pathlib import Path
import struct

import numpy as np
import pytest

from geoworkbench.importers.paradox import (
    DatasetClassification,
    ParadoxImportPlan,
    ParadoxReadError,
    analyze_table,
    discover_bundle,
    import_paradox,
    probe_db_format,
    read_paradox,
)
from geoworkbench.importers.paradox.importer import default_mappings


def _encode_sorted(payload: bytes) -> bytes:
    data = bytearray(payload)
    if data[0] & 0x80:
        return bytes((~byte) & 0xFF for byte in data)
    data[0] |= 0x80
    return bytes(data)


def _encode_long(value: int | None) -> bytes:
    if value is None:
        return b"\x00" * 4
    return _encode_sorted(int(value).to_bytes(4, "big", signed=True))


def _encode_number(value: float | None) -> bytes:
    if value is None:
        return b"\x00" * 8
    return _encode_sorted(struct.pack(">d", value))


def write_synthetic_paradox(path: Path) -> None:
    header_size = 0x1000
    block_size = 0x800
    record_size = 12
    rows = ((100, 1.5), (101, None), (102, 3.5))
    header = bytearray(header_size)
    struct.pack_into("<H", header, 0x00, record_size)
    struct.pack_into("<H", header, 0x02, header_size)
    header[0x04] = 2
    header[0x05] = block_size // 1024
    struct.pack_into("<I", header, 0x06, len(rows))
    struct.pack_into("<H", header, 0x0C, 1)
    struct.pack_into("<H", header, 0x0E, 1)
    struct.pack_into("<H", header, 0x10, 1)
    struct.pack_into("<H", header, 0x21, 2)
    header[0x39] = 12
    struct.pack_into("<H", header, 0x6A, 1251)
    header[0x78:0x7C] = bytes((4, 4, 6, 8))
    cursor = 0x7C
    for value in (b"SYNTH.db\x00", b"DEPT\x00", b"VALUE\x00"):
        header[cursor : cursor + len(value)] = value
        cursor += len(value)
    header[cursor : cursor + 4] = struct.pack("<HH", 1, 2)

    block = bytearray(block_size)
    struct.pack_into("<HHh", block, 0, 0, 0, (len(rows) - 1) * record_size)
    cursor = 6
    for depth, value in rows:
        payload = _encode_long(depth) + _encode_number(value)
        block[cursor : cursor + record_size] = payload
        cursor += record_size
    path.write_bytes(header + block)


def test_format_detector_distinguishes_paradox_sqlite_and_invalid(tmp_path: Path) -> None:
    paradox = tmp_path / "sample.db"
    write_synthetic_paradox(paradox)
    sqlite = tmp_path / "sqlite.db"
    sqlite.write_bytes(b"SQLite format 3\x00" + b"\x00" * 100)
    random = tmp_path / "random.db"
    random.write_bytes(b"not a database")
    empty = tmp_path / "empty.db"
    empty.write_bytes(b"")

    assert probe_db_format(paradox).is_paradox
    assert probe_db_format(sqlite).format_name == "sqlite"
    assert probe_db_format(random).format_name == "unknown"
    assert probe_db_format(empty).format_name == "unknown"

    with pytest.raises(ParadoxReadError, match="SQLite DB"):
        read_paradox(sqlite)


def test_reader_reads_schema_records_and_nulls(tmp_path: Path) -> None:
    source = tmp_path / "sample.db"
    write_synthetic_paradox(source)

    table = read_paradox(source)

    assert table.header.record_count == 3
    assert table.header.record_size == 12
    assert table.header.table_name == "SYNTH.db"
    assert [field.name for field in table.fields] == ["DEPT", "VALUE"]
    np.testing.assert_allclose(table.columns["DEPT"].values, [100, 101, 102])
    np.testing.assert_allclose(
        table.columns["VALUE"].values,
        [1.5, np.nan, 3.5],
        equal_nan=True,
    )
    assert table.columns["VALUE"].null_count == 1


def test_analysis_and_import_use_existing_dataset_model(tmp_path: Path) -> None:
    source = tmp_path / "sample.db"
    write_synthetic_paradox(source)
    table = read_paradox(source)
    quality = analyze_table(table)
    plan = ParadoxImportPlan(
        classification=DatasetClassification.DEPTH,
        depth_field="DEPT",
        active_role="depth",
        mappings=default_mappings(table),
    )

    result = import_paradox(source, plan, table=table)

    assert quality.depth_candidates[0].field_name == "DEPT"
    assert result.dataset.active_index.mnemonic == "DEPT"
    assert result.dataset.parameters["SOURCE_FORMAT"] == "GeoScape/Paradox DB"
    assert result.dataset.parameters["SOURCE_READ_ONLY"] == "true"
    assert result.dataset.curve_by_mnemonic("VALUE") is not None
    assert result.imported_channels == 2
    assert result.dataset.parameters["PARADOX_IMPORTED_CHANNELS"] == "2"
    assert result.dataset.parameters["PARADOX_SKIPPED_CHANNELS"] == "0"
    assert result.dataset.parameters["PARADOX_EMPTY_CHANNELS"] == "0"
    assert result.dataset.headers["STEP"] == "1"
    assert result.dataset.parameters["GEOSCAPE_STANDARD_DEPTH_STEP_M"] == "0.2"
    assert result.dataset.parameters["PARADOX_ACTUAL_DEPTH_STEP_M"] == "1"
    assert result.dataset.parameters["PARADOX_DEPTH_STEP_MATCHES_STANDARD"] == "false"
    assert len(result.dataset.parameters["PARADOX_SCHEMA_SIGNATURE"]) == 64


def test_numeric_time_preserves_raw_source_values(tmp_path: Path) -> None:
    source = tmp_path / "time.db"
    write_synthetic_paradox(source)
    table = read_paradox(source)
    plan = ParadoxImportPlan(
        classification=DatasetClassification.TIME_WITH_DEPTH,
        depth_field="DEPT",
        time_field="VALUE",
        active_role="time",
        mappings=default_mappings(table),
    )

    result = import_paradox(source, plan, table=table)

    raw_name = result.dataset.parameters["PARADOX_TIME_RAW_CURVE"]
    raw_curve = result.dataset.curve_by_mnemonic(raw_name)
    assert raw_curve is not None
    np.testing.assert_allclose(raw_curve.values, [1.5, np.nan, 3.5], equal_nan=True)
    assert result.dataset.active_index.mnemonic == "TIME"


def test_bundle_lookup_is_case_insensitive(tmp_path: Path) -> None:
    db = tmp_path / "BLData.db"
    db.write_bytes(b"")
    for name in ("BLDATA.PX", "bldata.tv", "BLData.Fam"):
        (tmp_path / name).write_bytes(b"")

    bundle = discover_bundle(db)

    assert bundle.primary_index is not None
    assert bundle.table_view is not None
    assert bundle.family is not None


@pytest.mark.parametrize(
    ("sample_name", "records", "fields"),
    (("BLData(1).db", 3488, 70), ("D250(1).db", 1739, 101)),
)
def test_external_reference_samples_when_available(
    sample_name: str,
    records: int,
    fields: int,
) -> None:
    source = Path("/mnt/data") / sample_name
    if not source.exists():
        pytest.skip("external user-provided verification sample is not present")

    table = read_paradox(source)

    assert table.rows_read == records
    assert len(table.fields) == fields
    assert not [issue for issue in table.issues if issue.severity.value == "critical"]


def test_profile_round_trip_and_schema_guard(tmp_path: Path) -> None:
    from geoworkbench.importers.paradox.profiles import (
        ImportProfile,
        load_profile,
        save_profile,
        schema_signature,
    )

    source = tmp_path / "sample.db"
    write_synthetic_paradox(source)
    table = read_paradox(source)
    plan = ParadoxImportPlan(
        classification=DatasetClassification.DEPTH,
        depth_field="DEPT",
        active_role="depth",
        sort_by_index=True,
        mappings=default_mappings(table),
        profile_name="Synthetic",
    )
    target = tmp_path / "synthetic.paradox-profile.json"

    save_profile(ImportProfile("Synthetic", schema_signature(table), plan), target)
    restored = load_profile(target)

    assert restored.name == "Synthetic"
    assert restored.schema_signature == schema_signature(table)
    assert restored.plan.depth_field == "DEPT"
    assert restored.plan.sort_by_index is True
    assert restored.plan.language == "ru"
    assert [item.source_name for item in restored.plan.mappings] == ["DEPT", "VALUE"]


def test_reader_never_modifies_source(tmp_path: Path) -> None:
    import hashlib

    source = tmp_path / "sample.db"
    write_synthetic_paradox(source)
    before = hashlib.sha256(source.read_bytes()).hexdigest()

    read_paradox(source)

    after = hashlib.sha256(source.read_bytes()).hexdigest()
    assert after == before


def test_channel_dictionary_user_mapping_has_priority_and_round_trips(tmp_path: Path) -> None:
    from geoworkbench.importers.paradox.channel_dictionary import (
        ChannelDefinition,
        GeoScapeChannelDictionary,
    )

    system = ChannelDefinition("S200", "HKLD", "Вес", "Салмақ", "Hook load", "t", "drilling")
    user = ChannelDefinition("S200", "CUSTOM", "Пользователь", "Пайдаланушы", "User", "kN", "user")
    dictionary = GeoScapeChannelDictionary({"S200": system})
    dictionary.set_user(user)
    target = tmp_path / "channels.json"
    dictionary.export_user(target)

    restored = GeoScapeChannelDictionary.load(target)

    assert dictionary.resolve("s200") == user
    assert restored.resolve("S200") == user


def test_duplicate_depth_policy_is_explicit_and_logged(tmp_path: Path) -> None:
    from geoworkbench.importers.paradox.models import DuplicateDepthPolicy

    source = tmp_path / "duplicate.db"
    write_synthetic_paradox(source)
    payload = bytearray(source.read_bytes())
    second_record = 0x1000 + 6 + 12
    payload[second_record : second_record + 4] = _encode_long(100)
    source.write_bytes(payload)
    table = read_paradox(source)
    plan = ParadoxImportPlan(
        classification=DatasetClassification.DEPTH,
        depth_field="DEPT",
        active_role="depth",
        mappings=default_mappings(table),
        duplicate_depth_policy=DuplicateDepthPolicy.MEAN,
    )

    result = import_paradox(source, plan, table=table)

    np.testing.assert_allclose(result.dataset.depth, [100.0, 102.0])
    np.testing.assert_allclose(result.dataset.curve_by_mnemonic("VALUE").values, [1.5, 3.5])
    assert result.skipped_records == 1
    assert result.dataset.parameters["PARADOX_DUPLICATE_DEPTH_POLICY"] == "mean"
    assert result.dataset.parameters["PARADOX_DUPLICATE_ROWS_REMOVED"] == "1"


def test_drop_empty_channels_is_opt_in(tmp_path: Path) -> None:
    source = tmp_path / "empty-channel.db"
    write_synthetic_paradox(source)
    payload = bytearray(source.read_bytes())
    for row in range(3):
        offset = 0x1000 + 6 + row * 12 + 4
        payload[offset : offset + 8] = b"\x00" * 8
    source.write_bytes(payload)
    table = read_paradox(source)

    kept = import_paradox(
        source,
        ParadoxImportPlan(
            classification=DatasetClassification.DEPTH,
            depth_field="DEPT",
            active_role="depth",
            mappings=default_mappings(table),
        ),
        table=table,
    )
    dropped = import_paradox(
        source,
        ParadoxImportPlan(
            classification=DatasetClassification.DEPTH,
            depth_field="DEPT",
            active_role="depth",
            mappings=default_mappings(table),
            drop_empty_channels=True,
        ),
        table=table,
    )

    assert kept.dataset.curve_by_mnemonic("VALUE") is not None
    assert dropped.dataset.curve_by_mnemonic("VALUE") is None
    assert kept.imported_channels == 2
    assert dropped.imported_channels == 1


def test_unknown_channel_descriptions_follow_selected_language(tmp_path: Path) -> None:
    source = tmp_path / "localized.db"
    write_synthetic_paradox(source)
    table = read_paradox(source)

    english = default_mappings(table, language="en")
    kazakh = default_mappings(table, language="kk")

    assert english[0].description == "Source channel DEPT"
    assert english[1].description == "Source channel VALUE"
    assert kazakh[0].description == "Бастапқы арна DEPT"

    result = import_paradox(
        source,
        ParadoxImportPlan(
            classification=DatasetClassification.TIME_WITH_DEPTH,
            depth_field="DEPT",
            time_field="VALUE",
            active_role="time",
            language="en",
        ),
        table=table,
    )
    raw_name = result.dataset.parameters["PARADOX_TIME_RAW_CURVE"]
    raw_curve = result.dataset.curve_by_mnemonic(raw_name)
    assert raw_curve is not None
    assert raw_curve.metadata.description.startswith("Original numeric time value VALUE")


def test_temporal_numeric_normalization_is_platform_independent() -> None:
    from datetime import date, datetime

    from geoworkbench.importers.paradox.decoder import numeric_value

    assert numeric_value(date(1899, 12, 30)) == 0.0
    assert numeric_value(date(2014, 4, 11)) == 41740.0
    assert numeric_value(datetime(1970, 1, 1, 0, 0, 1)) == 1.0


def test_field_decoders_cover_supported_paradox_types() -> None:
    from datetime import date, datetime, time
    from decimal import Decimal

    from geoworkbench.importers.paradox.decoder import decode_field
    from geoworkbench.importers.paradox.models import ParadoxField, ParadoxFieldType

    def field(field_type: ParadoxFieldType, size: int) -> ParadoxField:
        return ParadoxField(1, "F", int(field_type), size, 0)

    def encode_integer(value: int, size: int) -> bytes:
        return _encode_sorted(value.to_bytes(size, "big", signed=True))

    assert (
        decode_field(
            field(ParadoxFieldType.ALPHA, 8),
            "Тест".encode("cp1251"),
            encoding="cp1251",
        )
        == "Тест"
    )
    assert decode_field(
        field(ParadoxFieldType.DATE, 4),
        encode_integer(date(2014, 4, 11).toordinal(), 4),
        encoding="cp1251",
    ) == date(2014, 4, 11)
    assert (
        decode_field(
            field(ParadoxFieldType.SHORT, 2),
            encode_integer(-7, 2),
            encoding="cp1251",
        )
        == -7
    )
    assert (
        decode_field(
            field(ParadoxFieldType.LONG, 4),
            encode_integer(250, 4),
            encoding="cp1251",
        )
        == 250
    )
    assert (
        decode_field(
            field(ParadoxFieldType.NUMBER, 8),
            _encode_number(12.5),
            encoding="cp1251",
        )
        == 12.5
    )
    assert (
        decode_field(
            field(ParadoxFieldType.CURRENCY, 8),
            _encode_number(3.25),
            encoding="cp1251",
        )
        == 3.25
    )
    assert (
        decode_field(
            field(ParadoxFieldType.LOGICAL, 1),
            _encode_sorted(b"\x01"),
            encoding="cp1251",
        )
        is True
    )
    millis = (5 * 3600 + 43 * 60 + 29) * 1000
    assert decode_field(
        field(ParadoxFieldType.TIME, 4), encode_integer(millis, 4), encoding="cp1251"
    ) == time(5, 43, 29)
    moment = datetime(2014, 4, 11, 5, 43, 29)
    epoch = datetime(1, 1, 1)
    stored_millis = (moment - epoch).total_seconds() * 1000 + 86_400_000
    assert decode_field(
        field(ParadoxFieldType.TIMESTAMP, 8),
        _encode_number(stored_millis),
        encoding="cp1251",
    ) == moment
    assert decode_field(
        field(ParadoxFieldType.AUTOINCREMENT, 4), encode_integer(42, 4), encoding="cp1251"
    ) == 42
    assert decode_field(
        field(ParadoxFieldType.BCD, 4), bytes((4, 2, 0x12, 0x34)), encoding="cp1251"
    ) == Decimal("12.34")
    assert decode_field(
        field(ParadoxFieldType.BYTES, 2), b"\x01\x02", encoding="cp1251"
    ) == b"\x01\x02"
    assert decode_field(field(ParadoxFieldType.NUMBER, 8), b"\x00" * 8, encoding="cp1251") is None


def test_external_samples_keep_column_alignment_and_index_candidates() -> None:
    bl_source = Path("/mnt/data/BLData(1).db")
    d250_source = Path("/mnt/data/D250(1).db")
    if not bl_source.exists() or not d250_source.exists():
        pytest.skip("external user-provided verification samples are not present")

    bl = read_paradox(bl_source)
    bl_quality = analyze_table(bl)
    np.testing.assert_allclose(bl.columns["S113"].values[[0, -1]], [309.2, 1717.6])
    assert bl_quality.depth_candidates[0].field_name == "S113"
    assert bl_quality.time_candidates[0].field_name == "S0"
    assert bl_quality.classification is DatasetClassification.TIME_WITH_DEPTH
    bl_result = import_paradox(
        bl_source,
        ParadoxImportPlan(
            classification=DatasetClassification.TIME_WITH_DEPTH,
            depth_field="S113",
            time_field="S0",
            active_role="depth",
            mappings=default_mappings(bl),
        ),
        table=bl,
        quality=bl_quality,
    )
    # The source file really stores rows at about 0.4 m, while the confirmed
    # GeoScape server standard is 0.2 m.  Never write a false LAS STEP=0.2
    # unless a separate, explicit resampling operation has created that grid.
    assert bl_result.dataset.headers["STEP"] == "0.4"
    assert bl_result.dataset.parameters["GEOSCAPE_STANDARD_DEPTH_STEP_M"] == "0.2"
    assert bl_result.dataset.parameters["PARADOX_ACTUAL_DEPTH_STEP_M"] == "0.4"
    assert bl_result.dataset.parameters["PARADOX_DEPTH_STEP_MATCHES_STANDARD"] == "false"

    d250 = read_paradox(d250_source)
    d250_quality = analyze_table(d250)
    np.testing.assert_allclose(d250.columns["S101"].values[[0, -1]], [250.4, 661.8])
    assert d250_quality.time_candidates[0].field_name == "S0"
    assert {item.field_name for item in d250_quality.depth_candidates[:3]} == {
        "S101",
        "S115",
        "S108",
    }
    assert d250_quality.classification is DatasetClassification.MIXED


def test_import_plan_normalizes_qt_string_enum_values(tmp_path: Path) -> None:
    """PySide may return StrEnum user data as plain str on Windows."""
    from geoworkbench.importers.paradox.models import DuplicateDepthPolicy

    source = tmp_path / "qt-plan.db"
    write_synthetic_paradox(source)
    table = read_paradox(source)
    plan = ParadoxImportPlan(
        classification="depth",
        depth_field="DEPT",
        active_role="depth",
        duplicate_depth_policy="keep_all",
        mappings=default_mappings(table),
    )

    assert plan.classification is DatasetClassification.DEPTH
    assert plan.duplicate_depth_policy is DuplicateDepthPolicy.KEEP_ALL

    result = import_paradox(source, plan, table=table)

    assert result.dataset.parameters["PARADOX_CLASSIFICATION"] == "depth"
    assert result.dataset.parameters["PARADOX_DUPLICATE_DEPTH_POLICY"] == "keep_all"


def test_import_plan_rejects_unknown_qt_string_enum_values() -> None:
    with pytest.raises(ValueError, match="классификация"):
        ParadoxImportPlan(classification="not-a-classification")

    with pytest.raises(ValueError, match="повторяющейся глубины"):
        ParadoxImportPlan(duplicate_depth_policy="not-a-policy")
