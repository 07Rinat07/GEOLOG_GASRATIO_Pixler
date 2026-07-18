from __future__ import annotations

import numpy as np


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
