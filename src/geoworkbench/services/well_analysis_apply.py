"""Atomic commit of a prepared WELL-02 late-analysis update."""
from __future__ import annotations

from dataclasses import asdict, replace

from geoworkbench.domain.analysis_update import AnalysisCellChange, AnalysisUpdateRecord
from geoworkbench.domain.models import CuttingsSample, Well
from geoworkbench.services.well_analysis_update import (
    AnalysisUpdateError,
    PreparedAnalysisUpdate,
    well_analysis_state_sha256,
)


def apply_prepared_analysis_update(
    well: Well,
    prepared: PreparedAnalysisUpdate,
) -> AnalysisUpdateRecord:
    """Commit one prepared analysis update without allowing partial mutation.

    The prepared payload is treated as untrusted mutable state: the live well is
    rechecked against the preview digest and every staged sample is compared with
    the exact state implied by the immutable audit changes before any assignment.
    """

    if not isinstance(prepared, PreparedAnalysisUpdate):
        raise AnalysisUpdateError("Некорректно подготовлено обновление отдельного анализа")

    record = prepared.record
    if record.well_id != well.well_id:
        raise AnalysisUpdateError("Обновление отдельного анализа относится к другой скважине")
    if any(item.update_id == record.update_id for item in well.analysis_update_history):
        raise AnalysisUpdateError("Обновление отдельного анализа уже применено")
    if prepared.revision != well.content_revision + 1:
        raise AnalysisUpdateError("Ревизия отдельного анализа устарела; повторите просмотр")
    if well_analysis_state_sha256(well) != record.well_sha256_before:
        raise AnalysisUpdateError("Скважина изменилась после просмотра анализа; повторите просмотр")

    expected = _expected_cuttings(well.cuttings, record.changes)
    _validate_prepared_cuttings(expected, prepared.cuttings)

    staged_well = replace(
        well,
        cuttings=list(prepared.cuttings),
        content_revision=prepared.revision,
    )
    if well_analysis_state_sha256(staged_well) != record.well_sha256_after:
        raise AnalysisUpdateError("Контрольная сумма подготовленного анализа не совпадает")

    # Allocate everything that can fail before mutating the live aggregate.
    committed_cuttings = list(prepared.cuttings)
    committed_history = [*well.analysis_update_history, record]

    well.cuttings = committed_cuttings
    well.analysis_update_history = committed_history
    well.content_revision = prepared.revision
    return record


def _expected_cuttings(
    current: list[CuttingsSample],
    changes: tuple[AnalysisCellChange, ...],
) -> list[dict[str, object]]:
    indexes = {sample.sample_id: index for index, sample in enumerate(current)}
    if len(indexes) != len(current):
        raise AnalysisUpdateError("В скважине повторяются ID образцов шлама")

    expected: list[dict[str, object]] = [asdict(sample) for sample in current]
    seen: set[tuple[str, str]] = set()
    for change in changes:
        key = (change.sample_id, change.field.value)
        if key in seen:
            raise AnalysisUpdateError("Изменение отдельного анализа указано повторно")
        seen.add(key)

        index = indexes.get(change.sample_id)
        if index is None:
            raise AnalysisUpdateError("Целевой образец отдельного анализа больше не существует")
        sample = current[index]
        if (
            float(sample.top_depth) != change.top_depth
            or float(sample.bottom_depth) != change.bottom_depth
        ):
            raise AnalysisUpdateError("Интервал целевого образца отдельного анализа изменился")

        current_value = getattr(sample, change.field.value)
        if current_value is not None and not (
            isinstance(current_value, str) and not current_value.strip()
        ):
            raise AnalysisUpdateError(
                "Целевая ячейка отдельного анализа уже заполнена; перезапись запрещена"
            )
        expected[index][change.field.value] = change.new_value
    return expected


def _validate_prepared_cuttings(
    expected: list[dict[str, object]],
    prepared: list[CuttingsSample],
) -> None:
    if len(expected) != len(prepared):
        raise AnalysisUpdateError("Подготовленный анализ изменяет состав образцов шлама")
    for expected_sample, staged_sample in zip(expected, prepared, strict=True):
        if expected_sample != asdict(staged_sample):
            raise AnalysisUpdateError(
                "Подготовленный анализ содержит неподтверждённые изменения"
            )
