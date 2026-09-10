"""Read-only numerical WELL-02 review; no authorization to mutate a project.

O(N + M*C) time, O(N + M + preview_limit) auxiliary storage. Counts cover the
complete input; only the first preview_limit cell changes are retained.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from geoworkbench.domain.numerical_update import NumericalCellChange, NumericalUpdateKind
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
    index_role: str
    index_mnemonic: str
    index_unit: str | None
    start_value: str
    stop_value: str
    append_start_value: str
    append_stop_value: str

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
    if len({curve.metadata.curve_id for curve in target.curves.values()}) != len(target.curves):
        raise DailyLasGrowthError("Dataset содержит неоднозначные ID кривых")
    if len({_index_key(value) for value in source_axis}) != len(source_axis):
        raise DailyLasGrowthError("Индекс источника содержит неоднозначные близкие значения")
    lookup = {_index_key(value): row for row, value in enumerate(target_axis)}
    if len(lookup) != len(target_axis):
        raise DailyLasGrowthError("Индекс содержит неоднозначные близкие значения")
    append_start = append_stop = ""
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
            append_stop = _format_index_value(source.active_index.values[source_row])
            if not added_rows:
                append_start = append_stop
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
        source.active_index.role.value, source.active_index.mnemonic, source.active_index.unit,
        _format_index_value(source.active_index.values[0]),
        _format_index_value(source.active_index.values[-1]), append_start, append_stop,
    )


def revalidate_well_numerical_update(
    target: Dataset,
    source: Dataset,
    plan: WellNumericalUpdatePlan,
    *,
    source_name: str,
    source_sha256: str,
) -> WellNumericalUpdatePlan:
    """Recompute a review against independently verified current source inputs.

    The caller must verify the file and supply its current digest, rather than
    copying the digest from the plan. This checks counts and the displayed diff
    as well as dataset fingerprints. It neither mutates data nor authorizes
    corrections, including when the reviewed diff is truncated.
    """
    current = analyze_well_numerical_update(
        target, source, source_name=source_name, source_sha256=source_sha256,
        preview_limit=len(plan.changes),
    )
    if current != plan:
        raise DailyLasGrowthError(
            "Данные или план обновления изменились; выполните повторный анализ LAS"
        )
    return current
