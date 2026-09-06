"""Read-only numerical WELL-02 review; no authorization to mutate a project.

O(N + M*C) time, O(N + M + preview_limit) auxiliary storage. Counts cover the
complete input; only the first preview_limit cell changes are retained.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np

from geoworkbench.domain.models import Dataset
from geoworkbench.services.daily_las_growth import (
    DailyLasGrowthError,
    _format_index_value,
    _index_key,
    _same_value,
    _validate_numerical_update_inputs,
    _validate_well_identity,
    dataset_append_state_sha256,
)


class NumericalUpdateKind(str, Enum):
    APPEND = "append"
    FILL = "fill"
    CORRECT = "correct"


@dataclass(frozen=True, slots=True)
class NumericalCellChange:
    kind: NumericalUpdateKind
    curve_id: str
    mnemonic: str
    source_row: int
    target_row: int | None
    index_value: str
    before: float | None
    after: float


@dataclass(frozen=True, slots=True)
class WellNumericalUpdatePlan:
    target_dataset_id: str
    source_name: str
    source_sha256: str
    target_state_sha256: str
    source_state_sha256: str
    rows_added: int
    cells_added: int
    gaps_filled: int
    corrections: int
    source_missing: int
    cells_unchanged: int
    changes: tuple[NumericalCellChange, ...]

    @property
    def preview_truncated(self) -> bool:
        return self.cells_added + self.gaps_filled + self.corrections > len(self.changes)


def analyze_well_numerical_update(
    target: Dataset,
    source: Dataset,
    *,
    source_name: str,
    source_sha256: str,
    preview_limit: int = 200,
) -> WellNumericalUpdatePlan:
    """Classify suffix, missing-value fills and corrections without applying any.

    Source NaN never clears an existing value; zero is a measurement. Infinite
    measurements and off-grid historical rows fail closed. Local project curves
    are excluded by the same contract as daily append. A truncated diff is only
    a summary and must not serve as correction approval.
    """
    if type(preview_limit) is not int or not 0 <= preview_limit <= 10_000:
        raise DailyLasGrowthError("Лимит предварительного просмотра должен быть от 0 до 10000")
    if target.dataset_id == source.dataset_id or not source_name.strip():
        raise DailyLasGrowthError("Требуются разные dataset и имя исходного LAS")
    if len(source_sha256) != 64 or any(c not in "0123456789abcdef" for c in source_sha256):
        raise DailyLasGrowthError("Некорректный SHA-256 исходного LAS")
    _validate_well_identity(target, source)
    if len(target.indexes) != 1 or len(source.indexes) != 1:
        raise DailyLasGrowthError("Обновление требует один исходный индекс")
    left, right, target_axis, source_axis, direction = _validate_numerical_update_inputs(
        target, source,
    )
    lookup = {_index_key(value): row for row, value in enumerate(target_axis)}
    if len(lookup) != len(target_axis):
        raise DailyLasGrowthError("Индекс содержит неоднозначные близкие значения")
    added_rows = added = filled = corrected = missing = unchanged = 0
    changes: list[NumericalCellChange] = []
    curve_keys = sorted(left)
    for source_row, value in enumerate(source_axis):
        target_row = lookup.get(_index_key(value))
        if target_row is None:
            if (direction > 0 and value <= target_axis[-1]) or (
                direction < 0 and value >= target_axis[-1]
            ):
                raise DailyLasGrowthError("Новая строка находится внутри уже сохранённого диапазона")
            added_rows += 1
        for key in curve_keys:
            curve = left[key]
            after = float(right[key].values[source_row])
            before = None if target_row is None else float(curve.values[target_row])
            if np.isinf(after) or (before is not None and np.isinf(before)):
                raise DailyLasGrowthError("Измерения содержат бесконечность")
            if np.isnan(after):
                missing += 1
                continue
            if target_row is None:
                kind = NumericalUpdateKind.APPEND
                added += 1
            elif before is not None and np.isnan(before):
                kind = NumericalUpdateKind.FILL
                before = None
                filled += 1
            elif before is not None and _same_value(before, after):
                unchanged += 1
                continue
            else:
                kind = NumericalUpdateKind.CORRECT
                corrected += 1
            if len(changes) < preview_limit:
                changes.append(NumericalCellChange(
                    kind, curve.metadata.curve_id, curve.metadata.original_mnemonic,
                    source_row, target_row,
                    _format_index_value(source.active_index.values[source_row]), before, after,
                ))
    return WellNumericalUpdatePlan(
        target.dataset_id, source_name.strip(), source_sha256,
        dataset_append_state_sha256(target), dataset_append_state_sha256(source),
        added_rows, added, filled, corrected, missing, unchanged, tuple(changes),
    )
