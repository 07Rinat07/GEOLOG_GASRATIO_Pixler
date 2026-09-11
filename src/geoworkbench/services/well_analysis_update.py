"""Fill-only preview and staged application for late cuttings analyses.

The service is deliberately source-format agnostic. File/network adapters convert their
payload into :class:`AnalysisSourceSample`; the core then owns interval matching, validation,
stale-preview protection and immutable audit preparation.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from hashlib import sha256
import json
from math import isfinite
import re
from uuid import uuid4

from geoworkbench.domain.analysis_update import (
    AnalysisCellChange,
    AnalysisField,
    AnalysisScalar,
    AnalysisUpdateRecord,
)
from geoworkbench.domain.models import CuttingsSample, Well
from geoworkbench.services.lba_standard import (
    assess_lba_standard,
    lba_color_code,
    lba_groups_for_color,
    lba_standard_type,
)


_MAX_REVIEW_ITEMS = 10_000
_NUMERIC_PERCENT_FIELDS = {
    AnalysisField.CALCITE_PERCENT,
    AnalysisField.DOLOMITE_PERCENT,
}
_INTEGER_FIELDS = {AnalysisField.LBA_GROUP, AnalysisField.LBA_INTENSITY}
_LBA_FIELDS = {
    AnalysisField.LBA_GROUP,
    AnalysisField.LBA_TYPE_ID,
    AnalysisField.LBA_INTENSITY,
    AnalysisField.LBA_COLOR,
    AnalysisField.LBA_DISTRIBUTION,
    AnalysisField.LBA_CUT,
    AnalysisField.LBA_CUT_SPEED,
    AnalysisField.LBA_CUT_COLOR,
    AnalysisField.LBA_RESIDUE_TYPE,
    AnalysisField.LBA_RESIDUE_COLOR,
    AnalysisField.LBA_ODOUR,
    AnalysisField.LBA_STAIN,
    AnalysisField.LBA_DESCRIPTION,
}


class AnalysisUpdateError(ValueError):
    """Raised when a late-analysis preview cannot be applied safely."""


@dataclass(frozen=True, slots=True)
class AnalysisSourceValue:
    field: AnalysisField
    value: AnalysisScalar | None

    def __post_init__(self) -> None:
        if not isinstance(self.field, AnalysisField):
            raise AnalysisUpdateError("Неизвестное поле отдельного анализа")


@dataclass(frozen=True, slots=True)
class AnalysisSourceSample:
    top_depth: float
    bottom_depth: float
    values: tuple[AnalysisSourceValue, ...]
    target_sample_id: str | None = None

    def __post_init__(self) -> None:
        if isinstance(self.top_depth, bool) or isinstance(self.bottom_depth, bool):
            raise AnalysisUpdateError("Границы отдельного анализа должны быть числами")
        if not isfinite(float(self.top_depth)) or not isfinite(float(self.bottom_depth)):
            raise AnalysisUpdateError("Границы отдельного анализа должны быть конечными")
        if float(self.bottom_depth) <= float(self.top_depth):
            raise AnalysisUpdateError("Нижняя граница анализа должна быть больше верхней")
        if not isinstance(self.values, tuple):
            raise AnalysisUpdateError("Значения отдельного анализа должны быть tuple")
        if len(self.values) > len(AnalysisField):
            raise AnalysisUpdateError("Слишком много полей в одной записи анализа")
        if not all(isinstance(item, AnalysisSourceValue) for item in self.values):
            raise AnalysisUpdateError("Некорректное значение отдельного анализа")
        fields = [item.field for item in self.values]
        if len(fields) != len(set(fields)):
            raise AnalysisUpdateError("Поле отдельного анализа указано повторно")
        if self.target_sample_id is not None and (
            not isinstance(self.target_sample_id, str)
            or not self.target_sample_id.strip()
            or len(self.target_sample_id) > 2000
        ):
            raise AnalysisUpdateError("Некорректный target_sample_id отдельного анализа")


@dataclass(frozen=True, slots=True)
class AnalysisConflict:
    sample_id: str
    field: AnalysisField
    existing_value: AnalysisScalar
    incoming_value: AnalysisScalar


@dataclass(frozen=True, slots=True)
class WellAnalysisUpdatePlan:
    well_id: str
    source_name: str
    source_sha256: str
    source_state_sha256: str
    target_state_sha256: str
    selected_fields: tuple[AnalysisField, ...]
    changes: tuple[AnalysisCellChange, ...]
    conflicts: tuple[AnalysisConflict, ...]
    missing_source_intervals: int
    ignored_empty_values: int
    equal_values: int

    @property
    def fill_count(self) -> int:
        return len(self.changes)

    @property
    def conflict_count(self) -> int:
        return len(self.conflicts)


@dataclass(slots=True)
class PreparedAnalysisUpdate:
    cuttings: list[CuttingsSample]
    revision: int
    record: AnalysisUpdateRecord


def analyze_well_analysis_update(
    well: Well,
    source_samples: tuple[AnalysisSourceSample, ...],
    *,
    selected_fields: tuple[AnalysisField, ...],
    source_name: str,
    source_sha256: str,
) -> WellAnalysisUpdatePlan:
    """Build a deterministic fill-only preview without mutating ``well``."""

    _validate_source_identity(source_name, source_sha256)
    fields = _validate_selected_fields(selected_fields)
    normalized_source = _normalize_source_samples(source_samples)
    target_by_id, target_by_interval = _target_indexes(well.cuttings)

    changes: list[AnalysisCellChange] = []
    conflicts: list[AnalysisConflict] = []
    missing = ignored_empty = equal = 0

    for source in normalized_source:
        target = _match_target(source, target_by_id, target_by_interval)
        if target is None:
            missing += 1
            continue
        patch_changes: list[AnalysisCellChange] = []
        for item in source.values:
            if item.field not in fields:
                continue
            incoming = item.value
            if _is_empty(incoming):
                ignored_empty += 1
                continue
            assert incoming is not None
            current = getattr(target, item.field.value)
            if _is_empty(current):
                change = AnalysisCellChange(
                    target.sample_id,
                    float(target.top_depth),
                    float(target.bottom_depth),
                    item.field,
                    _audit_scalar(current),
                    incoming,
                )
                patch_changes.append(change)
                continue
            if _values_equal(item.field, current, incoming):
                equal += 1
                continue
            existing = _audit_scalar(current)
            if existing is None:
                raise AnalysisUpdateError("Внутренняя ошибка нормализации анализа")
            conflicts.append(AnalysisConflict(target.sample_id, item.field, existing, incoming))
        _validate_proposed_patch(target, patch_changes)
        changes.extend(patch_changes)
        if len(changes) + len(conflicts) > _MAX_REVIEW_ITEMS:
            raise AnalysisUpdateError(
                "Более 10000 изменений/конфликтов анализа: разделите источник"
            )

    return WellAnalysisUpdatePlan(
        well_id=well.well_id,
        source_name=source_name,
        source_sha256=source_sha256,
        source_state_sha256=_source_state_sha256(normalized_source),
        target_state_sha256=well_analysis_state_sha256(well),
        selected_fields=fields,
        changes=tuple(changes),
        conflicts=tuple(conflicts),
        missing_source_intervals=missing,
        ignored_empty_values=ignored_empty,
        equal_values=equal,
    )


def prepare_well_analysis_update(
    well: Well,
    source_samples: tuple[AnalysisSourceSample, ...],
    plan: WellAnalysisUpdatePlan,
    *,
    source_name: str,
    source_sha256: str,
    selected_changes: tuple[AnalysisCellChange, ...],
) -> PreparedAnalysisUpdate | None:
    """Revalidate a preview and prepare one atomic replacement of ``well.cuttings``."""

    if well.well_id != plan.well_id:
        raise AnalysisUpdateError("План отдельного анализа относится к другой скважине")
    current = analyze_well_analysis_update(
        well,
        source_samples,
        selected_fields=plan.selected_fields,
        source_name=source_name,
        source_sha256=source_sha256,
    )
    if current != plan:
        raise AnalysisUpdateError("Анализы, источник или скважина изменились; повторите просмотр")
    if not selected_changes:
        return None
    if len(selected_changes) > _MAX_REVIEW_ITEMS:
        raise AnalysisUpdateError("Выбрано слишком много изменений анализа")
    if len(set(selected_changes)) != len(selected_changes):
        raise AnalysisUpdateError("Одно изменение анализа выбрано повторно")
    available = set(plan.changes)
    if any(item not in available for item in selected_changes):
        raise AnalysisUpdateError("Выбрано изменение, отсутствующее в подтверждённом плане")

    selected = set(selected_changes)
    ordered_changes = tuple(item for item in plan.changes if item in selected)
    changes_by_sample: dict[str, dict[str, AnalysisScalar]] = {}
    changed_fields_by_sample: dict[str, set[AnalysisField]] = {}
    for change in ordered_changes:
        changes_by_sample.setdefault(change.sample_id, {})[change.field.value] = change.new_value
        changed_fields_by_sample.setdefault(change.sample_id, set()).add(change.field)

    staged: list[CuttingsSample] = []
    for sample in well.cuttings:
        values = changes_by_sample.get(sample.sample_id)
        if values is None:
            staged.append(sample)
            continue
        updated = replace(sample, **values)
        _validate_staged_sample(updated, changed_fields_by_sample[sample.sample_id])
        staged.append(updated)

    if len(staged) != len(well.cuttings):
        raise AnalysisUpdateError("Не удалось подготовить все образцы анализа")
    staged_well = replace(
        well,
        cuttings=staged,
        content_revision=well.content_revision + 1,
    )
    applied_fields = tuple(
        field for field in plan.selected_fields if any(change.field is field for change in ordered_changes)
    )
    record = AnalysisUpdateRecord(
        update_id=str(uuid4()),
        well_id=well.well_id,
        source_name=source_name,
        source_sha256=source_sha256,
        imported_at=datetime.now(timezone.utc).isoformat(),
        selected_fields=applied_fields,
        changes=ordered_changes,
        well_sha256_before=plan.target_state_sha256,
        well_sha256_after=well_analysis_state_sha256(staged_well),
    )
    return PreparedAnalysisUpdate(staged, staged_well.content_revision, record)


def well_analysis_state_sha256(well: Well) -> str:
    """Hash the complete cuttings context that a late-analysis preview was based on."""

    payload = {
        "well_id": well.well_id,
        "content_revision": well.content_revision,
        "cuttings": [asdict(sample) for sample in well.cuttings],
    }
    try:
        encoded = json.dumps(
            payload,
            sort_keys=True,
            ensure_ascii=True,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise AnalysisUpdateError("Сохранённые образцы содержат некорректные значения") from exc
    return sha256(encoded).hexdigest()


def _validate_source_identity(source_name: str, source_sha256: str) -> None:
    if not isinstance(source_name, str) or not source_name.strip() or len(source_name) > 2000:
        raise AnalysisUpdateError("Некорректное имя источника отдельного анализа")
    if not isinstance(source_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", source_sha256):
        raise AnalysisUpdateError("Некорректный SHA-256 источника отдельного анализа")


def _validate_selected_fields(
    selected_fields: tuple[AnalysisField, ...],
) -> tuple[AnalysisField, ...]:
    if (
        not isinstance(selected_fields, tuple)
        or not selected_fields
        or not all(isinstance(item, AnalysisField) for item in selected_fields)
    ):
        raise AnalysisUpdateError("Выберите хотя бы одно поддерживаемое поле анализа")
    if len(set(selected_fields)) != len(selected_fields):
        raise AnalysisUpdateError("Поле анализа выбрано повторно")
    return selected_fields


def _normalize_source_samples(
    source_samples: tuple[AnalysisSourceSample, ...],
) -> tuple[AnalysisSourceSample, ...]:
    if not isinstance(source_samples, tuple):
        raise AnalysisUpdateError("Источник анализов должен быть неизменяемым tuple")
    if len(source_samples) > _MAX_REVIEW_ITEMS:
        raise AnalysisUpdateError("Более 10000 записей анализа: разделите источник")
    normalized: list[AnalysisSourceSample] = []
    identities: set[tuple[str, str | float, float | None]] = set()
    for source in source_samples:
        if not isinstance(source, AnalysisSourceSample):
            raise AnalysisUpdateError("Источник содержит неизвестный тип записи анализа")
        identity: tuple[str, str | float, float | None]
        if source.target_sample_id is not None:
            identity = ("id", source.target_sample_id, None)
        else:
            identity = ("interval", float(source.top_depth), float(source.bottom_depth))
        if identity in identities:
            raise AnalysisUpdateError("Источник содержит повтор одного образца анализа")
        identities.add(identity)
        values = tuple(
            AnalysisSourceValue(item.field, _normalize_value(item.field, item.value))
            for item in source.values
        )
        _validate_source_lba(values)
        normalized.append(
            AnalysisSourceSample(
                float(source.top_depth),
                float(source.bottom_depth),
                values,
                source.target_sample_id,
            )
        )
    return tuple(normalized)


def _target_indexes(
    samples: list[CuttingsSample],
) -> tuple[dict[str, CuttingsSample], dict[tuple[float, float], CuttingsSample]]:
    by_id: dict[str, CuttingsSample] = {}
    by_interval: dict[tuple[float, float], CuttingsSample] = {}
    for sample in samples:
        if sample.sample_id in by_id:
            raise AnalysisUpdateError("Скважина содержит повтор sample_id")
        by_id[sample.sample_id] = sample
        key = (float(sample.top_depth), float(sample.bottom_depth))
        if key in by_interval:
            raise AnalysisUpdateError("Скважина содержит одинаковые интервалы образцов")
        by_interval[key] = sample
    return by_id, by_interval


def _match_target(
    source: AnalysisSourceSample,
    by_id: dict[str, CuttingsSample],
    by_interval: dict[tuple[float, float], CuttingsSample],
) -> CuttingsSample | None:
    if source.target_sample_id is not None:
        target = by_id.get(source.target_sample_id)
        if target is None:
            return None
        if (
            float(target.top_depth) != float(source.top_depth)
            or float(target.bottom_depth) != float(source.bottom_depth)
        ):
            raise AnalysisUpdateError("sample_id источника не совпадает с интервалом проекта")
        return target
    return by_interval.get((float(source.top_depth), float(source.bottom_depth)))


def _normalize_value(
    field: AnalysisField,
    value: AnalysisScalar | None,
) -> AnalysisScalar | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise AnalysisUpdateError(f"Поле {field.value} не принимает bool")
    if field in _NUMERIC_PERCENT_FIELDS:
        if not isinstance(value, (int, float)) or not isfinite(float(value)):
            raise AnalysisUpdateError(f"Поле {field.value} должно быть конечным числом")
        number = float(value)
        if not 0.0 <= number <= 100.0:
            raise AnalysisUpdateError(f"Поле {field.value} должно быть в диапазоне 0–100")
        return number
    if field in _INTEGER_FIELDS:
        if not isinstance(value, int):
            raise AnalysisUpdateError(f"Поле {field.value} должно быть целым числом")
        if field is AnalysisField.LBA_GROUP and not 1 <= value <= 5:
            raise AnalysisUpdateError("Группа ЛБА должна быть от 1 до 5")
        if field is AnalysisField.LBA_INTENSITY and not 1 <= value <= 5:
            raise AnalysisUpdateError("Интенсивность ЛБА должна быть от 1 до 5")
        return value
    if not isinstance(value, str):
        raise AnalysisUpdateError(f"Поле {field.value} должно быть строкой")
    text = value.strip()
    if not text:
        return None
    if len(text) > 20_000:
        raise AnalysisUpdateError(f"Поле {field.value} слишком длинное")
    if field is AnalysisField.LBA_TYPE_ID:
        standard = lba_standard_type(text)
        if standard is None:
            raise AnalysisUpdateError(f"Неизвестный тип ЛБА: {text}")
        return standard.type_id
    if field is AnalysisField.LBA_COLOR:
        code = lba_color_code(text)
        if not lba_groups_for_color(code):
            raise AnalysisUpdateError(f"Неизвестный цвет ЛБА: {text}")
        return code
    return text


def _validate_source_lba(values: tuple[AnalysisSourceValue, ...]) -> None:
    provided = {item.field: item.value for item in values if not _is_empty(item.value)}
    if not any(field in _LBA_FIELDS for field in provided):
        return
    group = provided.get(AnalysisField.LBA_GROUP)
    type_id = provided.get(AnalysisField.LBA_TYPE_ID)
    color = provided.get(AnalysisField.LBA_COLOR)
    intensity = provided.get(AnalysisField.LBA_INTENSITY)
    assessment = assess_lba_standard(
        group=int(group) if isinstance(group, int) else None,
        type_id=str(type_id) if isinstance(type_id, str) else None,
        color=str(color) if isinstance(color, str) else None,
        intensity=int(intensity) if isinstance(intensity, int) else None,
    )
    if assessment is not None and assessment.conflicts:
        raise AnalysisUpdateError("Несогласованные поля ЛБА в источнике: " + "; ".join(assessment.conflicts))


def _validate_proposed_patch(
    target: CuttingsSample,
    changes: list[AnalysisCellChange],
) -> None:
    if not changes:
        return
    values = {change.field.value: change.new_value for change in changes}
    staged = replace(target, **values)
    _validate_staged_sample(staged, {change.field for change in changes})


def _validate_staged_sample(sample: CuttingsSample, changed_fields: set[AnalysisField]) -> None:
    if changed_fields & _NUMERIC_PERCENT_FIELDS:
        calcite = sample.calcite_percent
        dolomite = sample.dolomite_percent
        for value, label in ((calcite, "calcite_percent"), (dolomite, "dolomite_percent")):
            if value is not None and (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not isfinite(float(value))
                or not 0.0 <= float(value) <= 100.0
            ):
                raise AnalysisUpdateError(f"Некорректное значение {label}")
        if calcite is not None and dolomite is not None and calcite + dolomite > 100.0 + 1e-9:
            raise AnalysisUpdateError("Сумма кальцита и доломита не может превышать 100%")

    if changed_fields & _LBA_FIELDS:
        if sample.lba_group is not None and not 1 <= sample.lba_group <= 5:
            raise AnalysisUpdateError("Группа ЛБА должна быть от 1 до 5")
        if sample.lba_intensity is not None and not 1 <= sample.lba_intensity <= 5:
            raise AnalysisUpdateError("Интенсивность ЛБА должна быть от 1 до 5")
        if sample.lba_type_id and lba_standard_type(sample.lba_type_id) is None:
            raise AnalysisUpdateError("Сохранённый тип ЛБА не поддерживается стандартом")
        if sample.lba_color and not lba_groups_for_color(sample.lba_color):
            raise AnalysisUpdateError("Сохранённый цвет ЛБА не поддерживается стандартом")
        assessment = assess_lba_standard(
            group=sample.lba_group,
            type_id=sample.lba_type_id,
            color=sample.lba_color,
            intensity=sample.lba_intensity,
        )
        if assessment is not None and assessment.conflicts:
            raise AnalysisUpdateError(
                "Late-analysis создаёт несогласованный ЛБА: " + "; ".join(assessment.conflicts)
            )


def _values_equal(field: AnalysisField, current: object, incoming: AnalysisScalar) -> bool:
    try:
        normalized = _normalize_value(field, _audit_scalar(current))
    except AnalysisUpdateError:
        return False
    return normalized == incoming


def _audit_scalar(value: object) -> AnalysisScalar | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise AnalysisUpdateError("Сохранённое значение анализа имеет неподдерживаемый тип")
    if isinstance(value, float) and not isfinite(value):
        raise AnalysisUpdateError("Сохранённое значение анализа не является конечным")
    return value


def _is_empty(value: object) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _source_state_sha256(samples: tuple[AnalysisSourceSample, ...]) -> str:
    payload = [
        {
            "top_depth": sample.top_depth,
            "bottom_depth": sample.bottom_depth,
            "target_sample_id": sample.target_sample_id,
            "values": [(item.field.value, item.value) for item in sample.values],
        }
        for sample in samples
    ]
    encoded = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("ascii")
    return sha256(encoded).hexdigest()
