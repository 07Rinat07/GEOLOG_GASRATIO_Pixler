import numpy as np

import pytest

from geoworkbench.services.time_normalization import (
    normalize_date_time_columns,
    normalize_datetime_strings,
    normalize_iso8601_strings,
)


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


def test_combines_date_and_time_with_named_timezone() -> None:
    result = normalize_date_time_columns(
        np.array(["15.07.2026", "15.07.2026"]),
        np.array(["10:00:00", "10:00:01"]),
        date_format="%d.%m.%Y",
        time_format="%H:%M:%S",
        timezone_name="Asia/Oral",
    )

    np.testing.assert_array_equal(
        result.values,
        np.array(["2026-07-15T05:00:00", "2026-07-15T05:00:01"], dtype="datetime64[ns]"),
    )
    assert result.datetime_format == "%d.%m.%Y %H:%M:%S"
    assert result.timezone == "Asia/Oral"
    assert result.warnings == ()


def test_manual_format_without_timezone_remains_naive() -> None:
    result = normalize_datetime_strings(
        np.array(["15/07/2026 10:00"]),
        datetime_format="%d/%m/%Y %H:%M",
    )

    assert result.timezone is None
    assert result.values[0] == np.datetime64("2026-07-15T10:00:00", "ns")
    assert any("не преобразованы в UTC" in warning for warning in result.warnings)


def test_manual_format_supports_explicit_utc_offset() -> None:
    result = normalize_datetime_strings(
        np.array(["2026-07-15 10:00:00"]),
        datetime_format="%Y-%m-%d %H:%M:%S",
        timezone_name="UTC+05:00",
    )

    assert result.values[0] == np.datetime64("2026-07-15T05:00:00", "ns")
    assert result.timezone == "UTC+05:00"


def test_composite_time_preserves_empty_pair_as_nat() -> None:
    result = normalize_date_time_columns(
        np.array(["2026-07-15", ""]),
        np.array(["10:00:00", ""]),
        date_format="%Y-%m-%d",
        time_format="%H:%M:%S",
        timezone_name="UTC",
    )

    assert np.isnat(result.values[1])
    assert any("NaT" in warning for warning in result.warnings)


def test_manual_time_validates_shapes_formats_and_timezone() -> None:
    with pytest.raises(ValueError, match="одинаковую длину"):
        normalize_date_time_columns(
            np.array(["2026-01-01"]),
            np.array(["10:00", "11:00"]),
            date_format="%Y-%m-%d",
            time_format="%H:%M",
        )
    with pytest.raises(ValueError, match="Строка 1"):
        normalize_datetime_strings(
            np.array(["15.07.2026"]),
            datetime_format="%Y-%m-%d",
        )
    with pytest.raises(ValueError, match="Неизвестный часовой пояс"):
        normalize_datetime_strings(
            np.array(["2026-07-15"]),
            datetime_format="%Y-%m-%d",
            timezone_name="Mars/Olympus",
        )


def test_rejects_dst_ambiguous_local_time_without_explicit_offset() -> None:
    with pytest.raises(ValueError, match="неоднозначно"):
        normalize_datetime_strings(
            np.array(["2026-11-01 01:30:00"]),
            datetime_format="%Y-%m-%d %H:%M:%S",
            timezone_name="America/New_York",
        )
