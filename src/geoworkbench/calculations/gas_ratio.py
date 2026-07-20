from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


Array = NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class GasRatioResult:
    mnemonic: str
    values: Array
    unit: str
    description: str


def safe_ratio(numerator: Array, denominator: Array) -> Array:
    numerator = np.asarray(numerator, dtype=np.float64)
    denominator = np.asarray(denominator, dtype=np.float64)
    if numerator.shape != denominator.shape:
        raise ValueError("Массивы газовых компонентов должны иметь одинаковую длину")

    result = np.full(numerator.shape, np.nan, dtype=np.float64)
    valid = np.isfinite(numerator) & np.isfinite(denominator) & (np.abs(denominator) > 0.0)
    np.divide(numerator, denominator, out=result, where=valid)
    return result


def sum_components(components: dict[str, Array]) -> Array:
    if not components:
        raise ValueError("Не переданы газовые компоненты")
    arrays = [np.asarray(values, dtype=np.float64) for values in components.values()]
    shape = arrays[0].shape
    if any(array.shape != shape for array in arrays):
        raise ValueError("Газовые компоненты имеют разную длину")
    return np.nansum(np.vstack(arrays), axis=0)


def calculate_basic_ratios(curves: dict[str, Array]) -> dict[str, GasRatioResult]:
    """Расчёт только однозначных арифметических отношений.

    Методики Wetness/Balance/Character/Pixler намеренно не зашиты здесь без
    подтверждённого профиля формул и источника.
    """
    normalized = {
        name.upper(): np.asarray(values, dtype=np.float64) for name, values in curves.items()
    }
    required = ("C1", "C2", "C3")
    missing = [name for name in required if name not in normalized]
    if missing:
        raise KeyError(f"Отсутствуют обязательные компоненты: {', '.join(missing)}")

    c1, c2, c3 = normalized["C1"], normalized["C2"], normalized["C3"]
    c2_c3 = c2 + c3
    results = {
        "C1_C2": GasRatioResult("C1_C2", safe_ratio(c1, c2), "ratio", "Отношение C1/C2"),
        "C1_C3": GasRatioResult("C1_C3", safe_ratio(c1, c3), "ratio", "Отношение C1/C3"),
        "C2_C3": GasRatioResult("C2_C3", safe_ratio(c2, c3), "ratio", "Отношение C2/C3"),
        "C1_C2C3": GasRatioResult(
            "C1_C2C3", safe_ratio(c1, c2_c3), "ratio", "Отношение C1/(C2+C3)"
        ),
    }

    available_components: dict[str, NDArray[np.float64]] = {
        name: normalized[name]
        for name in ("C1", "C2", "C3", "IC4", "NC4", "C4", "IC5", "NC5", "C5")
        if name in normalized
    }
    results["TG_CALC"] = GasRatioResult(
        "TG_CALC",
        sum_components(available_components),
        "%abs",
        "Расчётная сумма доступных углеводородных компонентов",
    )
    return results
