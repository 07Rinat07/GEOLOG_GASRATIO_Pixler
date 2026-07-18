from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import numpy as np


class NumberFormatMode(StrEnum):
    ADAPTIVE = "adaptive"
    FIXED = "fixed"
    SCIENTIFIC = "scientific"


@dataclass(frozen=True, slots=True)
class NumberDisplayFormat:
    mode: NumberFormatMode = NumberFormatMode.ADAPTIVE
    precision: int = 8

    def __post_init__(self) -> None:
        if not isinstance(self.mode, NumberFormatMode):
            raise ValueError("Режим отображения числа не поддерживается")
        if (
            isinstance(self.precision, bool)
            or not isinstance(self.precision, int)
            or not 0 <= self.precision <= 15
        ):
            raise ValueError("Точность отображения числа должна быть от 0 до 15")
        if self.mode is NumberFormatMode.ADAPTIVE and self.precision == 0:
            raise ValueError("Адаптивному формату нужна хотя бы одна значащая цифра")


def format_decimal_number(value: float, *, precision: int = 15) -> str:
    """Format a finite float without switching to scientific notation."""
    numeric = float(value)
    if not np.isfinite(numeric):
        raise ValueError("Для десятичного форматирования требуется конечное число")
    if not 1 <= precision <= 17:
        raise ValueError("Точность десятичного форматирования должна быть от 1 до 17")
    if numeric == 0.0:
        return "0"
    return np.format_float_positional(
        numeric,
        precision=precision,
        unique=False,
        fractional=False,
        trim="-",
    )


def format_display_number(value: float, settings: NumberDisplayFormat) -> str:
    numeric = float(value)
    if not np.isfinite(numeric):
        raise ValueError("Для отображения требуется конечное число")
    if settings.mode is NumberFormatMode.ADAPTIVE:
        return format_decimal_number(numeric, precision=settings.precision)
    if settings.mode is NumberFormatMode.SCIENTIFIC:
        return f"{numeric:.{settings.precision}e}"
    rounded = f"{numeric:.{settings.precision}f}"
    if numeric < 0.0 and float(rounded) == 0.0:
        return rounded.removeprefix("-")
    return rounded
