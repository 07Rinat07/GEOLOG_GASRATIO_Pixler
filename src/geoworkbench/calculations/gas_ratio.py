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
    """Sum available components without turning an all-NULL row into a real zero.

    LAS NULL values are represented as NaN. ``numpy.nansum`` alone returns ``0``
    when every component is NaN, which falsely looks like a measured zero gas
    reading. A row is therefore valid only when at least one component contains
    a finite measurement.
    """

    if not components:
        raise ValueError("Не переданы газовые компоненты")
    arrays = [np.asarray(values, dtype=np.float64) for values in components.values()]
    shape = arrays[0].shape
    if any(array.shape != shape for array in arrays):
        raise ValueError("Газовые компоненты имеют разную длину")
    matrix = np.vstack(arrays)
    result = np.nansum(matrix, axis=0)
    result[~np.any(np.isfinite(matrix), axis=0)] = np.nan
    return result


def relative_component_percent(component: Array, total: Array) -> Array:
    """Return a component share in percent of the available hydrocarbon sum."""

    return safe_ratio(component, total) * 100.0


def _family_components(
    curves: dict[str, Array],
    first_isomer: str,
    normal_isomer: str,
    aggregate: str,
) -> dict[str, Array]:
    """Select one non-duplicating representation of a C4 or C5 family.

    Some LAS files contain both an aggregate C4/C5 channel and split iC/nC
    channels. Summing all of them would count the same gas twice. A complete
    isomer pair therefore has priority, the aggregate is the fallback, and a
    lone split channel is used only when no aggregate exists.
    """

    if first_isomer in curves and normal_isomer in curves:
        return {
            first_isomer: curves[first_isomer],
            normal_isomer: curves[normal_isomer],
        }
    if aggregate in curves:
        return {aggregate: curves[aggregate]}
    return {
        name: curves[name]
        for name in (first_isomer, normal_isomer)
        if name in curves
    }


def _family_total(
    selected: dict[str, Array],
    first_isomer: str,
    normal_isomer: str,
    aggregate: str,
) -> Array | None:
    family = {
        name: selected[name]
        for name in (first_isomer, normal_isomer, aggregate)
        if name in selected
    }
    return sum_components(family) if family else None


def calculate_basic_ratios(curves: dict[str, Array]) -> dict[str, GasRatioResult]:
    """Calculate auditable C1-C5 sums, composition, Haworth and Pixler aliases.

    The function accepts either aggregate C4/C5 curves or split iC4/nC4 and
    iC5/nC5 curves. When both representations exist, split isomers are preferred
    so the total and relative composition never double-count hydrocarbons.
    """

    normalized = {
        name.upper(): np.asarray(values, dtype=np.float64) for name, values in curves.items()
    }
    required = ("C1", "C2", "C3")
    missing = [name for name in required if name not in normalized]
    if missing:
        raise KeyError(f"Отсутствуют обязательные компоненты: {', '.join(missing)}")

    c1, c2, c3 = normalized["C1"], normalized["C2"], normalized["C3"]
    c2_c3 = sum_components({"C2": c2, "C3": c3})
    results: dict[str, GasRatioResult] = {
        "C1_C2": GasRatioResult("C1_C2", safe_ratio(c1, c2), "ratio", "Отношение C1/C2"),
        "C1_C3": GasRatioResult("C1_C3", safe_ratio(c1, c3), "ratio", "Отношение C1/C3"),
        "C2_C3": GasRatioResult("C2_C3", safe_ratio(c2, c3), "ratio", "Отношение C2/C3"),
        "C1_C2C3": GasRatioResult(
            "C1_C2C3", safe_ratio(c1, c2_c3), "ratio", "Отношение C1/(C2+C3)"
        ),
    }

    selected_components: dict[str, Array] = {
        "C1": c1,
        "C2": c2,
        "C3": c3,
    }
    selected_components.update(_family_components(normalized, "IC4", "NC4", "C4"))
    selected_components.update(_family_components(normalized, "IC5", "NC5", "C5"))

    total = sum_components(selected_components)
    results["TG_CALC"] = GasRatioResult(
        "TG_CALC",
        total,
        "%abs",
        "Расчётная сумма доступных углеводородных компонентов без двойного учёта C4/C5",
    )

    for mnemonic, values in selected_components.items():
        relative_mnemonic = f"{mnemonic}_REL"
        results[relative_mnemonic] = GasRatioResult(
            relative_mnemonic,
            relative_component_percent(values, total),
            "%rel",
            f"Относительное содержание {mnemonic} в сумме углеводородных компонентов",
        )

    c4_total = _family_total(selected_components, "IC4", "NC4", "C4")
    c5_total = _family_total(selected_components, "IC5", "NC5", "C5")

    # Aggregate relative curves remain available for legacy forms, while the
    # complete form uses the seven split component curves.
    if c4_total is not None:
        results["C4_REL"] = GasRatioResult(
            "C4_REL",
            relative_component_percent(c4_total, total),
            "%rel",
            "Суммарное относительное содержание iC4+nC4",
        )
        c1_c4 = safe_ratio(c1, c4_total)
        results["C1_C4"] = GasRatioResult("C1_C4", c1_c4, "ratio", "Отношение C1/(iC4+nC4)")
        results["PIXLER_C1_C4"] = GasRatioResult(
            "PIXLER_C1_C4", c1_c4, "ratio", "Коэффициент Pixler C1/(iC4+nC4)"
        )
    if c5_total is not None:
        results["C5_REL"] = GasRatioResult(
            "C5_REL",
            relative_component_percent(c5_total, total),
            "%rel",
            "Суммарное относительное содержание iC5+nC5",
        )
        c1_c5 = safe_ratio(c1, c5_total)
        results["C1_C5"] = GasRatioResult("C1_C5", c1_c5, "ratio", "Отношение C1/(iC5+nC5)")
        results["PIXLER_C1_C5"] = GasRatioResult(
            "PIXLER_C1_C5", c1_c5, "ratio", "Коэффициент Pixler C1/(iC5+nC5)"
        )

    results["PIXLER_C1_C2"] = GasRatioResult(
        "PIXLER_C1_C2", results["C1_C2"].values, "ratio", "Коэффициент Pixler C1/C2"
    )
    results["PIXLER_C1_C3"] = GasRatioResult(
        "PIXLER_C1_C3", results["C1_C3"].values, "ratio", "Коэффициент Pixler C1/C3"
    )

    if "IC4" in selected_components and "NC4" in selected_components:
        results["IC4_NC4"] = GasRatioResult(
            "IC4_NC4",
            safe_ratio(selected_components["IC4"], selected_components["NC4"]),
            "ratio",
            "Отношение iC4/nC4",
        )
    if "IC5" in selected_components and "NC5" in selected_components:
        results["IC5_NC5"] = GasRatioResult(
            "IC5_NC5",
            safe_ratio(selected_components["IC5"], selected_components["NC5"]),
            "ratio",
            "Отношение iC5/nC5",
        )

    if c4_total is not None and c5_total is not None:
        heavy = sum_components({"C3": c3, "C4": c4_total, "C5": c5_total})
        wet_numerator = sum_components({"C2": c2, "HEAVY": heavy})
        haworth_total = sum_components({"C1": c1, "WET": wet_numerator})
        c4_c5 = sum_components({"C4": c4_total, "C5": c5_total})

        wetness = 100.0 * safe_ratio(wet_numerator, haworth_total)
        balance = safe_ratio(sum_components({"C1": c1, "C2": c2}), heavy)
        character = safe_ratio(c4_c5, c3)
        for canonical, alias, values, unit, description in (
            ("WH", "WETNESS", wetness, "%", "Haworth Wetness"),
            ("BH", "BALANCE", balance, "ratio", "Haworth Balance"),
            ("CH", "CHARACTER", character, "ratio", "Haworth Character"),
        ):
            results[canonical] = GasRatioResult(canonical, values, unit, description)
            results[alias] = GasRatioResult(alias, values, unit, description)

    return results
