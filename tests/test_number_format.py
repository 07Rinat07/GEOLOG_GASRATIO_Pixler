import pytest

from geoworkbench.data.number_format import format_decimal_number


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (5.2e-5, "0.000052"),
        (-3.2e-6, "-0.0000032"),
        (1e-15, "0.000000000000001"),
        (-0.0, "0"),
    ],
)
def test_format_decimal_number_never_uses_scientific_notation(
    value: float, expected: str
) -> None:
    result = format_decimal_number(value)

    assert result == expected
    assert "e" not in result.casefold()


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_format_decimal_number_rejects_non_finite_values(value: float) -> None:
    with pytest.raises(ValueError, match="конечное"):
        format_decimal_number(value)
