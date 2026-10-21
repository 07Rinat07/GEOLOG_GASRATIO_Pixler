"""Coverage of complete, current Pixler profiles without changing source curves."""
from dataclasses import dataclass

import numpy as np

from geoworkbench.domain.models import CalculationState, Dataset


@dataclass(frozen=True, slots=True)
class PixlerCoverage:
    total_rows: int
    complete_rows: int
    first_index: str = ""
    last_index: str = ""
    unavailable_ratios: tuple[str, ...] = ()


def pixler_coverage(dataset: Dataset) -> PixlerCoverage:
    """Count positive finite ratios paired on the same active-index row.

    Index bounds describe the span, not continuity. Stale, failed and calculating
    curves cannot certify an updated profile; no components are synthesized.
    """
    index = dataset.active_index.values
    valid = np.ones(len(index), dtype=bool)
    if np.issubdtype(index.dtype, np.datetime64):
        valid &= ~np.isnat(index)
    elif np.issubdtype(index.dtype, np.number):
        valid &= np.isfinite(index)
    unavailable = []
    for number in range(2, 6):
        mnemonic = f"C1_C{number}"
        aliases = {mnemonic, f"PIXLER_{mnemonic}"}
        candidates = [curve for curve in dataset.curves.values() if aliases & {
            str(curve.metadata.original_mnemonic or "").strip().upper(),
            str(curve.metadata.canonical_mnemonic or "").strip().upper(),
        }]
        # Match the report's deterministic last-alias selection.
        curve = candidates[-1] if candidates else None
        if (curve is None or curve.state != CalculationState.CURRENT
                or curve.values.shape != index.shape):
            unavailable.append(mnemonic)
            valid[:] = False
            continue
        valid &= np.isfinite(curve.values) & (curve.values > 0)
    positions = np.flatnonzero(valid)
    return PixlerCoverage(
        total_rows=len(index), complete_rows=int(positions.size),
        first_index=str(index[positions[0]]) if positions.size else "",
        last_index=str(index[positions[-1]]) if positions.size else "",
        unavailable_ratios=tuple(unavailable),
    )
