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
    return [
        curve.metadata.original_mnemonic
        for curve in list(dataset.curves.values())[:maximum]
    ]
