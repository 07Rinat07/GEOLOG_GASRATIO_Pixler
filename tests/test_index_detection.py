import numpy as np

from geoworkbench.domain.models import IndexRole, IndexType
from geoworkbench.services.index_detection import IndexColumn, detect_index_candidates


def test_detect_index_candidates_ranks_depth_mnemonic_and_unit() -> None:
    candidates = detect_index_candidates(
        [
            IndexColumn("gas", "C1", "%", "Methane", np.array([1.0, 2.0, 3.0])),
            IndexColumn("depth", "DEPT", "m", "Measured depth", np.array([100.0, 101.0, 102.0])),
        ]
    )

    assert candidates[0].curve_id == "depth"
    assert candidates[0].index_type is IndexType.MD
    assert candidates[0].role is IndexRole.DEPTH
    assert candidates[0].confidence == 1.0
    assert any("мнемоника" in item for item in candidates[0].evidence)


def test_detect_index_candidates_distinguishes_tvdss() -> None:
    candidate = detect_index_candidates(
        [IndexColumn("tvdss", "TVDSS", "m", None, np.array([-100.0, -101.0]))]
    )[0]

    assert candidate.index_type is IndexType.TVDSS
    assert candidate.role is IndexRole.DEPTH


def test_detect_index_candidates_recognizes_unix_milliseconds() -> None:
    candidate = detect_index_candidates(
        [
            IndexColumn(
                "timestamp",
                "TIMESTAMP",
                "ms",
                "record time",
                np.array([1_700_000_000_000.0, 1_700_000_001_000.0]),
            )
        ]
    )[0]

    assert candidate.index_type is IndexType.DATETIME
    assert candidate.role is IndexRole.TIME
    assert any("Unix timestamp (ms)" in item for item in candidate.evidence)
    assert candidate.datetime_format == "unix-ms"
    assert candidate.timezone == "UTC"


def test_detect_index_candidates_reports_mixed_direction_and_duplicates() -> None:
    candidate = detect_index_candidates(
        [IndexColumn("depth", "DEPTH", "m", None, np.array([1.0, 2.0, 1.0, 1.0]))]
    )[0]

    assert "значения имеют смешанное направление" in candidate.warnings
    assert "обнаружены повторяющиеся значения" in candidate.warnings


def test_datetime64_column_is_recognized_without_string_guessing() -> None:
    candidate = detect_index_candidates(
        [
            IndexColumn(
                "date",
                "DATE",
                None,
                None,
                np.array(["2026-01-01", "2026-01-02"], dtype="datetime64[D]"),
            )
        ]
    )[0]

    assert candidate.index_type is IndexType.DATETIME
    assert candidate.role is IndexRole.TIME
    assert candidate.confidence >= 0.85
    assert candidate.datetime_format == "datetime64[ns]"
    assert any("часовой пояс" in warning for warning in candidate.warnings)


def test_iso8601_string_column_is_recognized_with_timezone_provenance() -> None:
    candidate = detect_index_candidates(
        [
            IndexColumn(
                "date",
                "RECORD_TIME",
                None,
                "Record date",
                np.array(["2026-01-01T00:00:00+05:00", "2026-01-01T00:00:01+05:00"]),
            )
        ]
    )[0]

    assert candidate.index_type is IndexType.DATETIME
    assert candidate.role is IndexRole.TIME
    assert candidate.datetime_format == "ISO8601"
    assert candidate.timezone == "UTC+05:00"
    assert any("ISO 8601" in item for item in candidate.evidence)


def test_naive_iso8601_candidate_warns_about_missing_timezone() -> None:
    candidate = detect_index_candidates(
        [IndexColumn("date", "DATE", None, None, np.array(["2026-01-01", "2026-01-02"]))]
    )[0]

    assert candidate.index_type is IndexType.DATETIME
    assert candidate.timezone is None
    assert any("часовой пояс отсутствует" in warning for warning in candidate.warnings)
