import pytest

from geoworkbench.data.number_format import (
    NumberDisplayFormat,
    NumberFormatMode,
    format_decimal_number,
    format_display_number,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (5.2e-5, "0.000052"),
        (-3.2e-6, "-0.0000032"),
        (1e-15, "0.000000000000001"),
        (-0.0, "0"),
    ],
)
def test_format_decimal_number_never_uses_scientific_notation(value: float, expected: str) -> None:
    result = format_decimal_number(value)

    assert result == expected
    assert "e" not in result.casefold()


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_format_decimal_number_rejects_non_finite_values(value: float) -> None:
    with pytest.raises(ValueError, match="конечное"):
        format_decimal_number(value)


@pytest.mark.parametrize(
    ("settings", "expected"),
    [
        (NumberDisplayFormat(), "0.000052"),
        (NumberDisplayFormat(NumberFormatMode.FIXED, 7), "0.0000520"),
        (NumberDisplayFormat(NumberFormatMode.FIXED, 3), "0.000"),
        (NumberDisplayFormat(NumberFormatMode.SCIENTIFIC, 2), "5.20e-05"),
    ],
)
def test_format_display_number_supports_engineering_table_modes(
    settings: NumberDisplayFormat, expected: str
) -> None:
    assert format_display_number(5.2e-5, settings) == expected


def test_fixed_display_format_does_not_show_negative_zero() -> None:
    settings = NumberDisplayFormat(NumberFormatMode.FIXED, 3)

    assert format_display_number(-1e-9, settings) == "0.000"


@pytest.mark.parametrize(
    "settings",
    [
        (NumberFormatMode.ADAPTIVE, 0),
        (NumberFormatMode.FIXED, -1),
        (NumberFormatMode.SCIENTIFIC, 16),
    ],
)
def test_number_display_format_rejects_invalid_precision(
    settings: tuple[NumberFormatMode, int],
) -> None:
    with pytest.raises(ValueError, match="Точность|Адаптивному"):
        NumberDisplayFormat(*settings)
