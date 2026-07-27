from __future__ import annotations

from datetime import date, time
from io import BytesIO

from geoworkbench.acquisition import (
    Wits0DiagnosticCode,
    Wits0Parser,
    Wits0SequenceStatus,
    Wits0StreamProcessor,
    iter_parsed_wits0_frames,
    load_builtin_wits0_profile,
    process_wits0_chunks,
)


def _frame(record: int, sequence: str, *lines: str) -> bytes:
    body = [
        "&&",
        f"{record:02d}01SG-8",
        f"{record:02d}0201",
        f"{record:02d}03{record}",
        f"{record:02d}04{sequence}",
        f"{record:02d}05260727",
        f"{record:02d}060215450",
        f"{record:02d}070",
        *lines,
        "!!",
    ]
    return ("\r\n".join(body)).encode("ascii")


def test_parser_returns_typed_header_and_profile_fields() -> None:
    profile = load_builtin_wits0_profile()
    parser = Wits0Parser(profile)

    parsed = parser.parse(
        _frame(1, "42", "0108123.40", "011340,5"),
        received_at="2026-07-27T02:15:45.000Z",
        source_ref="capture.wits",
    )

    assert parsed.record_no == 1
    assert parsed.sequence_no == 42
    assert parsed.sequence_status is Wits0SequenceStatus.UNAVAILABLE
    assert parsed.received_at == "2026-07-27T02:15:45.000Z"
    assert parsed.source_ref == "capture.wits"
    assert parsed.field(1, 1).value == "SG-8"  # type: ignore[union-attr]
    assert parsed.field(1, 2).value == 1  # type: ignore[union-attr]
    assert parsed.field(1, 3).value == 1  # type: ignore[union-attr]
    assert parsed.field(1, 4).value == 42  # type: ignore[union-attr]
    assert parsed.field(1, 5).value == date(2026, 7, 27)  # type: ignore[union-attr]
    assert parsed.field(1, 6).value == time(2, 15, 45)  # type: ignore[union-attr]
    assert parsed.field(1, 8).value == 123.4  # type: ignore[union-attr]
    assert parsed.field(1, 13).value == 40.5  # type: ignore[union-attr]
    assert parsed.field(1, 13).canonical_mnemonic == "ROP_AVG"  # type: ignore[union-attr]
    assert parsed.error_count == 0
    assert parsed.warning_count == 0


def test_parser_preserves_unknown_and_malformed_fields_with_diagnostics() -> None:
    profile = load_builtin_wits0_profile()
    parser = Wits0Parser(profile)
    raw = b"&&\n01041\n0108not-a-number\n019912.5\n019912.6\nbad\n990812\n!!"

    parsed = parser.parse(raw)
    codes = [item.code for item in parsed.diagnostics]

    assert parsed.field(1, 8).raw_value == "not-a-number"  # type: ignore[union-attr]
    assert parsed.field(1, 8).value is None  # type: ignore[union-attr]
    assert parsed.field(1, 99).raw_value == "12.5"  # type: ignore[union-attr]
    assert Wits0DiagnosticCode.VALUE_PARSE_ERROR in codes
    assert Wits0DiagnosticCode.UNKNOWN_FIELD in codes
    assert Wits0DiagnosticCode.DUPLICATE_FIELD in codes
    assert Wits0DiagnosticCode.INVALID_LINE in codes
    assert Wits0DiagnosticCode.UNKNOWN_RECORD in codes
    assert Wits0DiagnosticCode.MIXED_RECORDS in codes


def test_sequence_tracker_is_independent_per_record_and_reports_anomalies() -> None:
    profile = load_builtin_wits0_profile()
    processor = Wits0StreamProcessor(profile)
    payload = b"".join(
        (
            _frame(1, "10", "0108100"),
            _frame(2, "5", "0208100"),
            _frame(1, "11", "0108101"),
            _frame(1, "11", "0108101"),
            _frame(1, "14", "0108104"),
            _frame(1, "12", "0108102"),
            _frame(2, "6", "0208101"),
        )
    )

    parsed = processor.append(payload)

    assert [item.sequence_status for item in parsed] == [
        Wits0SequenceStatus.FIRST,
        Wits0SequenceStatus.FIRST,
        Wits0SequenceStatus.CONTIGUOUS,
        Wits0SequenceStatus.DUPLICATE,
        Wits0SequenceStatus.GAP,
        Wits0SequenceStatus.OUT_OF_ORDER,
        Wits0SequenceStatus.CONTIGUOUS,
    ]
    assert processor.last_sequence_by_record == {1: 14, 2: 6}
    assert any(
        item.code is Wits0DiagnosticCode.SEQUENCE_GAP
        and item.expected_sequence == 12
        and item.actual_sequence == 14
        for item in parsed[4].diagnostics
    )


def test_missing_and_invalid_sequence_are_diagnosed_without_dropping_frame() -> None:
    profile = load_builtin_wits0_profile()
    processor = Wits0StreamProcessor(profile)

    missing, invalid = processor.append(
        b"&&\n0108123\n!!&&\n0104abc\n0108124\n!!"
    )

    assert missing.sequence_status is Wits0SequenceStatus.UNAVAILABLE
    assert invalid.sequence_status is Wits0SequenceStatus.INVALID
    assert any(
        item.code is Wits0DiagnosticCode.MISSING_SEQUENCE
        for item in missing.diagnostics
    )
    assert any(
        item.code is Wits0DiagnosticCode.INVALID_SEQUENCE
        for item in invalid.diagnostics
    )


def test_live_chunking_and_replay_use_identical_parser_and_sequence_pipeline() -> None:
    profile = load_builtin_wits0_profile()
    raw = b"noise" + _frame(1, "1", "0108100") + _frame(1, "3", "0108102")
    chunks = (raw[:3], raw[3:17], raw[17:41], raw[41:])

    live = process_wits0_chunks(
        chunks,
        profile=profile,
        received_at="2026-07-27T00:00:00.000Z",
        source_ref="same-source",
    )
    replay = tuple(
        iter_parsed_wits0_frames(
            BytesIO(raw),
            profile=profile,
            chunk_size=7,
            received_at="2026-07-27T00:00:00.000Z",
            source_ref="same-source",
        )
    )

    assert live == replay
    assert [item.sequence_status for item in replay] == [
        Wits0SequenceStatus.FIRST,
        Wits0SequenceStatus.GAP,
    ]
