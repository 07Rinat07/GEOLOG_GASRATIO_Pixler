import numpy as np

from geoworkbench.services.time_normalization import normalize_iso8601_strings


def test_normalizes_utc_and_explicit_offset_to_utc() -> None:
    result = normalize_iso8601_strings(
        np.array(["2026-01-01T00:00:00Z", "2026-01-01T05:00:01+05:00"])
    )

    assert result is not None
    np.testing.assert_array_equal(
        result.values,
        np.array(["2026-01-01T00:00:00", "2026-01-01T00:00:01"], dtype="datetime64[ns]"),
    )
    assert result.timezone == "mixed-offset"
    assert any("разные UTC offsets" in warning for warning in result.warnings)


def test_naive_time_is_not_silently_treated_as_utc() -> None:
    result = normalize_iso8601_strings(
        np.array(["2026-01-01 00:00:00", "2026-01-01 00:00:01"])
    )

    assert result is not None
    assert result.timezone is None
    assert any("не преобразованы в UTC" in warning for warning in result.warnings)
    assert result.values[0] == np.datetime64("2026-01-01T00:00:00", "ns")


def test_preserves_empty_values_as_nat() -> None:
    result = normalize_iso8601_strings(np.array(["2026-01-01T00:00:00+05:00", ""]))

    assert result is not None
    assert result.timezone == "UTC+05:00"
    assert np.isnat(result.values[1])
    assert any("NaT" in warning for warning in result.warnings)


def test_rejects_non_iso_and_mixed_timezone_awareness() -> None:
    assert normalize_iso8601_strings(np.array(["01/02/2026", "not-a-date"])) is None

    mixed = normalize_iso8601_strings(
        np.array(["2026-01-01T00:00:00Z", "2026-01-01T00:00:01"])
    )
    assert mixed is not None
    assert np.all(np.isnat(mixed.values))
    assert "смешаны значения с часовым поясом и без него" in mixed.warnings


def test_rejects_non_string_or_multidimensional_input() -> None:
    assert normalize_iso8601_strings(np.array([1.0, 2.0])) is None
    assert normalize_iso8601_strings(np.array([["2026-01-01"]])) is None
