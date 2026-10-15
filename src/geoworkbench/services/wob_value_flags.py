"""Strict WOB source-sample selection for depth value flags.

This module does not mutate the dataset or infer force units from magnitude.
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from geoworkbench.domain.models import Dataset, IndexRole, IndexType

_WOB_NAMES = frozenset({"WOB", "WEIGHT_ON_BIT", "WEIGHTONBIT", "BIT_WEIGHT", "BITWEIGHT"})
_TO_TF = {
    "tf": 1.0, "тс": 1.0, "tonnef": 1.0, "tonne-force": 1.0,
    "kn": 1.0 / 9.80665, "n": 1.0 / 9806.65,
    "lbf": 1.0 / 2204.6226218488, "klbf": 1000.0 / 2204.6226218488,
}


@dataclass(frozen=True, slots=True)
class WobValueSample:
    mnemonic: str
    depth: float
    depth_unit: str
    source_value: float
    source_unit: str
    tonnes_force: float
    row_index: int

    @property
    def caption(self) -> str:
        return f"WOB: {self.tonnes_force:g} тс · MD {self.depth:g} {self.depth_unit} ({self.mnemonic})"


def _is_wob(curve) -> bool:
    meta = curve.metadata
    semantic = meta.semantic
    if semantic is not None and semantic.resolved:
        canonical = (meta.canonical_mnemonic or "").strip().upper()
        return canonical in _WOB_NAMES
    return any(
        (name or "").strip().upper() in _WOB_NAMES
        for name in (meta.original_mnemonic, meta.canonical_mnemonic)
    )


def wob_channels(dataset: Dataset) -> tuple[str, ...]:
    found = []
    for curve in dataset.curves.values():
        name = curve.metadata.original_mnemonic.strip()
        unit = (curve.metadata.unit or "").strip().casefold()
        if (
            name and _is_wob(curve) and unit in _TO_TF
            and np.asarray(curve.values).shape == dataset.depth.shape
            and np.any(np.isfinite(curve.values))
        ):
            found.append(name)
    return tuple(sorted(set(found), key=str.casefold))


def wob_value_at_depth(dataset: Dataset, mnemonic: str, requested_depth: float) -> WobValueSample | None:
    """Return an actual sampled WOB row; reject gaps, duplicates and unknown units."""
    if (
        dataset.active_index.role is not IndexRole.DEPTH
        or dataset.active_index.index_type is not IndexType.MD
        or not np.isfinite(requested_depth)
        or mnemonic not in wob_channels(dataset)
    ):
        return None
    curve = dataset.curve_by_mnemonic(mnemonic)
    if curve is None:
        return None
    depths = np.asarray(dataset.depth, dtype=np.float64)
    values = np.asarray(curve.values, dtype=np.float64)
    valid = np.flatnonzero(np.isfinite(depths))
    if not valid.size or values.shape != depths.shape:
        return None
    nearest = int(valid[np.argmin(np.abs(depths[valid] - requested_depth))])
    depth = float(depths[nearest])
    unique = np.unique(depths[valid])
    steps = np.diff(unique)
    positive = steps[steps > 0]
    tolerance = 0.5 * float(np.min(positive)) if positive.size else 1e-8
    if abs(depth - requested_depth) > max(tolerance, 1e-8):
        return None
    duplicates = values[valid[depths[valid] == depth]]
    if not np.all(np.isfinite(duplicates)) or not np.all(duplicates == duplicates[0]):
        return None
    source_value = float(values[nearest])
    unit = (curve.metadata.unit or "").strip()
    factor = _TO_TF.get(unit.casefold())
    if factor is None:
        return None
    return WobValueSample(
        mnemonic=mnemonic, depth=depth,
        depth_unit=(dataset.active_index.unit or "м").strip(),
        source_value=source_value, source_unit=unit,
        tonnes_force=source_value * factor, row_index=nearest,
    )
