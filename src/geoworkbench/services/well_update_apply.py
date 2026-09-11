"""Atomic in-memory application of reviewed numerical changes.

O(N + M*C) review time plus O(N*C) staging/hashing; O(N*C + M + 10000)
auxiliary storage, bounded by the resulting dataset and the selected cell diff.
No source array is mutated and no filesystem writes happen in this service.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from uuid import uuid4

import numpy as np

from geoworkbench.domain.models import CalculationState, Dataset
from geoworkbench.domain.geology_update import GeologyUpdateRecord
from geoworkbench.domain.numerical_update import (
    NumericalCellChange, NumericalUpdateKind, NumericalUpdateRecord,
)
from geoworkbench.services.daily_las_growth import (
    DailyLasGrowthError, _index_key, _is_local_derived, _is_local_project_curve,
    _refresh_las_range_headers, _validate_numerical_update_inputs, dataset_content_sha256,
)
from geoworkbench.services.well_update_plan import (
    WellNumericalUpdatePlan, revalidate_well_numerical_update,
)


@dataclass(frozen=True, slots=True)
class WellNumericalUpdateOutcome:
    plan: WellNumericalUpdatePlan
    record: NumericalUpdateRecord | None
    geology_record: GeologyUpdateRecord | None = None


def apply_well_numerical_update(
    target: Dataset,
    source: Dataset,
    plan: WellNumericalUpdatePlan,
    *,
    source_name: str,
    source_sha256: str,
    append_rows: bool = False,
    selected_changes: tuple[NumericalCellChange, ...] = (),
    imported_at: datetime | None = None,
) -> WellNumericalUpdateOutcome:
    """Apply only explicit selections present in a freshly revalidated preview.

    Selecting a CORRECT cell confirms its exact before/after diff. Hidden cells
    can never be selected, including in a truncated preview. Appending the full
    suffix is a separate choice and never changes historical measurements.
    Callers independently verify source bytes and own persistence/backup.
    """
    if type(append_rows) is not bool or not isinstance(selected_changes, tuple):
        raise DailyLasGrowthError("Некорректный выбор операций обновления")
    if len(selected_changes) > 10_000 or not all(isinstance(c, NumericalCellChange) for c in selected_changes):
        raise DailyLasGrowthError("Некорректный список выбранных ячеек")
    reviewed = set(plan.changes)
    if len(set(selected_changes)) != len(selected_changes) or any(
        c.kind is NumericalUpdateKind.APPEND or c not in reviewed for c in selected_changes
    ):
        raise DailyLasGrowthError("Выбраны повторяющиеся или непроверенные ячейки")
    revalidate_well_numerical_update(
        target, source, plan, source_name=source_name, source_sha256=source_sha256,
    )
    if not selected_changes and not (append_rows and plan.rows_added):
        return WellNumericalUpdateOutcome(plan, None)

    left, right, target_axis, source_axis, _ = _validate_numerical_update_inputs(target, source)
    existing = {_index_key(value) for value in target_axis}
    rows = np.asarray(
        [row for row, value in enumerate(source_axis) if _index_key(value) not in existing]
        if append_rows else [], dtype=np.int64,
    )
    # Copy wrappers/containers; copy arrays only when changing them. All fallible
    # work, including hashing and record construction, completes on this stage.
    staged = replace(
        target,
        indexes={key: replace(index) for key, index in target.indexes.items()},
        curves={key: replace(curve) for key, curve in target.curves.items()},
        headers=dict(target.headers),
        numerical_update_history=list(target.numerical_update_history),
        gas_conditioning_qc=None,
    )
    changed_ids: set[str] = set()
    if len(rows):
        staged.active_index.values = np.concatenate((target.active_index.values, source.active_index.values[rows]))
        staged.depth = np.asarray(staged.active_index.values, dtype=np.float64)
        source_by_id = {left[key].metadata.curve_id: right[key] for key in left}
        for key, curve in staged.curves.items():
            tail = (np.full(len(rows), np.nan) if _is_local_project_curve(curve)
                    else source_by_id[curve.metadata.curve_id].values[rows])
            curve.values = np.concatenate((curve.values, tail))
            changed_ids.add(key)
        _refresh_las_range_headers(staged)
    curves_by_id = {curve.metadata.curve_id: (key, curve) for key, curve in staged.curves.items()}
    for change in selected_changes:
        key, curve = curves_by_id[change.curve_id]
        if key not in changed_ids:
            curve.values = np.asarray(curve.values, dtype=np.float64).copy()
            changed_ids.add(key)
        curve.values[change.target_row] = change.after
    for key, curve in staged.curves.items():
        if key in changed_ids:
            curve.version += 1
        if _is_local_derived(curve):
            curve.state = CalculationState.STALE
    record = NumericalUpdateRecord(
        update_id=str(uuid4()), source_name=source_name.strip(), source_sha256=source_sha256,
        imported_at=(imported_at or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat(),
        dataset_sha256_before=dataset_content_sha256(target),
        dataset_sha256_after=dataset_content_sha256(staged),
        rows_added=len(rows), changes=selected_changes,
    )
    staged.numerical_update_history.append(record)
    # Commit prepared references only, retaining the original Dataset/curve IDs
    # and objects used by views. No validation, allocation or hashing after here.
    target.active_index.values = staged.active_index.values
    target.depth = staged.depth
    target.headers = staged.headers
    for key, curve in target.curves.items():
        prepared = staged.curves[key]
        curve.values, curve.version, curve.state = prepared.values, prepared.version, prepared.state
    target.gas_conditioning_qc = staged.gas_conditioning_qc
    target.numerical_update_history = staged.numerical_update_history
    return WellNumericalUpdateOutcome(plan, record)
