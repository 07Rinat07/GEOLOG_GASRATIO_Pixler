from __future__ import annotations

from io import BytesIO
from pathlib import Path

from geoworkbench.acquisition import (
    Wits0DiagnosticCode,
    Wits0Parser,
    Wits0SequenceStatus,
    Wits0StreamProcessor,
    iter_parsed_wits0_frames,
    load_builtin_wits0_catalog,
    load_builtin_wits0_profile,
    process_wits0_chunks,
)


ROOT = Path(__file__).resolve().parents[1]
MANUAL_SAMPLE = ROOT / "tests/fixtures/wits0/geoscape_manual_record11.wits"


def test_geosensor_catalog_contains_complete_vendor_dictionary() -> None:
    catalog = load_builtin_wits0_catalog()

    assert catalog.catalog_id == "geosensor-wits-level0"
    assert catalog.version == 1
    assert len(catalog.fields) == 963
    assert catalog.record_numbers == tuple(range(1, 26))

    sequence = catalog.field(1, 4)
    assert sequence is not None
    assert sequence.description == "Sequence Identifier"
    assert sequence.short_mnemonic == "SQID"
    assert sequence.long_mnemonic == "SEQID"
    assert sequence.value_kind == "integer"

    water_depth = catalog.field(25, 8)
    assert water_depth is not None
    assert water_depth.canonical_mnemonic == "WATDEPT"
    assert water_depth.value_kind == "float"


def test_builtin_profile_references_catalog_and_correct_header_contract() -> None:
    profile = load_builtin_wits0_profile()
    parser = Wits0Parser(profile)
    frame = parser.parse(
        b"&&\n0101SG-8\n010201\n010301\n010442\n0105260727\n0106021545\n01070\n!!"
    )

    assert profile.version == 2
    assert profile.field_catalog_id == "geosensor-wits-level0"
    assert frame.field(1, 1).canonical_mnemonic == "WELL_IDENTIFIER"  # type: ignore[union-attr]
    assert frame.field(1, 2).canonical_mnemonic == "SIDETRACK_HOLE_SECTION"  # type: ignore[union-attr]
    assert frame.field(1, 3).canonical_mnemonic == "WITS_RECORD_IDENTIFIER"  # type: ignore[union-attr]
    assert frame.field(1, 4).canonical_mnemonic == "WITS_SEQUENCE"  # type: ignore[union-attr]
    assert frame.sequence_no == 42


def test_manual_geoscape_record_uses_item_04_as_sequence() -> None:
    profile = load_builtin_wits0_profile()
    raw = MANUAL_SAMPLE.read_bytes()
    parsed = Wits0StreamProcessor(profile).append(raw)

    assert len(parsed) == 1
    frame = parsed[0]
    assert frame.record_no == 11
    assert frame.sequence_no == 3458
    assert frame.sequence_status is Wits0SequenceStatus.FIRST
    assert frame.field(11, 2).value == 0  # type: ignore[union-attr]
    assert frame.field(11, 3).value == 161  # type: ignore[union-attr]
    assert frame.field(11, 4).value == 3458  # type: ignore[union-attr]
    assert frame.field(11, 10).value == 23.3417854  # type: ignore[union-attr]
    assert not any(
        item.code is Wits0DiagnosticCode.INVALID_SEQUENCE for item in frame.diagnostics
    )


def test_catalog_fields_are_known_even_when_record_is_not_in_proxy_profile() -> None:
    profile = load_builtin_wits0_profile()
    frame = Wits0Parser(profile).parse(
        b"&&\n2501RIG-A\n250201\n250325\n25041\n2505260727\n2506021545\n25070\n2508123.5\n!!"
    )

    field = frame.field(25, 8)
    assert field is not None
    assert field.is_known
    assert field.canonical_mnemonic == "WATDEPT"
    assert field.value == 123.5
    assert not any(
        item.code is Wits0DiagnosticCode.UNKNOWN_RECORD for item in frame.diagnostics
    )


def test_manual_sample_is_deterministic_for_live_and_replay_chunking() -> None:
    profile = load_builtin_wits0_profile()
    raw = MANUAL_SAMPLE.read_bytes()
    live = process_wits0_chunks(
        (raw[:1], raw[1:9], raw[9:31], raw[31:77], raw[77:]),
        profile=profile,
        received_at="2026-07-27T08:00:00Z",
        source_ref="manual-record11",
    )
    replay = tuple(
        iter_parsed_wits0_frames(
            BytesIO(raw),
            profile=profile,
            chunk_size=11,
            received_at="2026-07-27T08:00:00Z",
            source_ref="manual-record11",
        )
    )

    assert live == replay
