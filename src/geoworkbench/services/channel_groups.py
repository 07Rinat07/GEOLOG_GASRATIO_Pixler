from __future__ import annotations

from geoworkbench.domain.models import Dataset


GAS_MNEMONIC_ORDER = (
    "TG",
    "TGAS",
    "TOTALGAS",
    "TOTAL_GAS",
    "TG_CALC",
    "C1",
    "C2",
    "C3",
    "IC4",
    "NC4",
    "C4",
    "IC5",
    "NC5",
    "C5",
)

DEXP_MNEMONIC_ORDER = ("DEXP", "DEXPC", "NCT", "DEXPC_NCT")
GAS_RATIO_PIXLER_MNEMONIC_ORDER = (
    "WH",
    "BH",
    "CH",
    "C1_C2",
    "C1_C3",
    "C1_C4",
    "C1_C5",
    "C1_C2C3",
    "C2_C3",
)
NORMALIZED_GAS_MNEMONIC_ORDER = (
    "TG_NORM",
    "NORMALIZED_TOTAL_GAS",
    "TOTAL_GAS_NORM",
    "NORM_TG",
    "TGNORM",
    "TG_NORM_CALC",
    "C1_NORM",
    "C1_NORM_REF",
    "C2_NORM",
    "C3_NORM",
    "IC4_NORM",
    "NC4_NORM",
    "IC5_NORM",
    "NC5_NORM",
)


def available_mnemonics(dataset: Dataset, order: tuple[str, ...]) -> list[str]:
    result: list[str] = []
    seen_curve_ids: set[str] = set()
    for mnemonic in order:
        curve = dataset.curve_by_mnemonic(mnemonic)
        if curve is None or curve.metadata.curve_id in seen_curve_ids:
            continue
        result.append(curve.metadata.original_mnemonic)
        seen_curve_ids.add(curve.metadata.curve_id)
    return result


def default_curve_mnemonics(dataset: Dataset, maximum: int = 6) -> list[str]:
    if maximum <= 0:
        return []
    gas = available_mnemonics(dataset, GAS_MNEMONIC_ORDER)
    if gas:
        return gas[:maximum]
    return [curve.metadata.original_mnemonic for curve in list(dataset.curves.values())[:maximum]]
