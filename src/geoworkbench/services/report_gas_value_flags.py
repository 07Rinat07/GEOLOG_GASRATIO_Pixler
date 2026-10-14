"""Fail-closed source-sample lookup for gas VALUE callouts in interpretation reports.

Only original dataset rows are eligible: no linear interpolation, gap-crossing,
curve-to-curve substitution, or extrapolation beyond sampled depths.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

import numpy as np

from geoworkbench.domain.models import CurveData, Dataset, IndexRole, IndexType
from geoworkbench.services.gas_curve_presentation import is_gas_ratio_mnemonic


_GAS_NAMES = frozenset({
    # Gas source channels and total-gas equivalents.
    "TG", "TGAS", "TOTALGAS", "TOTAL_GAS", "TG_CALC",
    "TG_NORM", "NORM_TG", "TGNORM", "TOTAL_GAS_NORM",
    "NORMALIZED_TOTAL_GAS", "OPUS_TG_PCT",
    "C1", "C2", "C3", "C4", "C5", "IC4", "NC4", "IC5", "NC5",
    "H2S", "CO2", "N2",
})
_NORMALIZED_GAS = re.compile(
    r"^(?:TG|C[1-5]|[IN]C[45])_NORM(?:_CALC|_REF)?$"
)


def _identifies_gas(identifier: str) -> bool:
    code = identifier.strip().upper()
    return (
        code in _GAS_NAMES
        or _NORMALIZED_GAS.fullmatch(code) is not None
        or is_gas_ratio_mnemonic(code)
    )


def _is_gas_curve(curve: CurveData) -> bool:
    """Accept curated gas mnemonics or resolved gas semantics, never units alone."""
    meta = curve.metadata
    semantic = meta.semantic
    if semantic is not None and semantic.resolved:
        # A high-confidence semantic binding can reject an ambiguous vendor
        # alias even if its raw source mnemonic looks like a gas channel.
        return semantic.family.casefold() == "gas" or (
            _identifies_gas(meta.canonical_mnemonic or "")
            and semantic.family.casefold() not in {"wob", "rop", "torque", "pressure"}
        )
    return any(_identifies_gas(name) for name in (
        meta.original_mnemonic,
        meta.canonical_mnemonic or "",
    ))


@dataclass(frozen=True, slots=True)
class ReportGasValueSample:
    mnemonic: str
    unit: str
    depth: float
    depth_unit: str
    value: float
    row_index: int

    @property
    def caption(self) -> str:
        value_unit = f" {self.unit}" if self.unit else ""
        depth_unit = f" {self.depth_unit}" if self.depth_unit else ""
        return f"{self.mnemonic}: {self.value:g}{value_unit} · MD {self.depth:g}{depth_unit}"


def report_gas_channels(dataset: Dataset) -> tuple[str, ...]:
    """Only clearly identified gas channels, preserving actual source spelling."""
    found: dict[str, str] = {}
    for curve in dataset.curves.values():
        name = curve.metadata.original_mnemonic.strip()
         if not name:
            continue
        if not _is_gas_curve(curve):
            continue
        values = np.asarray(curve.values, dtype=np.float64)
        if values.shape != dataset.depth.shape or not np.any(np.isfinite(values)):
            continue
        found.setdefault(name.casefold(), name)
    return tuple(sorted(found.values(), key=str.casefold))


def report_gas_value_at_depth(
    dataset: Dataset, mnemonic: str, requested_depth: float,
) -> ReportGasValueSample | None:
    """Snap to one nearest *actual row*, refusing holes and ambiguous MD."""
    if (
        dataset.active_index.role is not IndexRole.DEPTH
        or dataset.active_index.index_type is not IndexType.MD
        or not np.isfinite(requested_depth)
    ):
        return None
    if mnemonic not in report_gas_channels(dataset):
        return None
    curve = dataset.curve_by_mnemonic(mnemonic)
    if curve is None:
        return None
    depths = np.asarray(dataset.depth, dtype=np.float64)
    values = np.asarray(curve.values, dtype=np.float64)
    valid_depths = np.flatnonzero(np.isfinite(depths))
    if not valid_depths.size or values.shape != depths.shape:
        return None
    nearest = int(valid_depths[np.argmin(np.abs(depths[valid_depths] - requested_depth))])
    source_depth = float(depths[nearest])
    unique_depths = np.unique(depths[valid_depths])
    increments = np.diff(unique_depths)
    positive = increments[increments > 0]
    # Use the smallest source sampling step to fail closed at large depth gaps.
    # Median spacing could permit a pick deep inside an unsampled interval.
    tolerance = (0.5 * float(np.min(positive))) if positive.size else 1e-8
    if abs(source_depth - requested_depth) > max(tolerance, 1e-8):
        return None
    same_depth = valid_depths[depths[valid_depths] == source_depth]
    # The depth-only report cannot identify a unique TIME/MD row at a stop.
    # Never quietly choose first/last if gas readings at the same MD disagree.
    candidates = values[same_depth]
    if not np.all(np.isfinite(candidates)):
        return None
    if candidates.size > 1 and not np.all(candidates == candidates[0]):
        return None
    value = float(values[nearest])
    if not np.isfinite(value):
        return None
    return ReportGasValueSample(
        mnemonic=mnemonic, unit=(curve.metadata.unit or "").strip(),
        depth=source_depth, depth_unit=(dataset.active_index.unit or "м").strip(),
        value=value, row_index=nearest,
    )
