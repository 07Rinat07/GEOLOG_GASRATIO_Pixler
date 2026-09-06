from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import cast
from uuid import uuid4

import numpy as np

from geoworkbench.domain.models import (
    CalculationState,
    CurveData,
    Dataset,
    DatasetAppendRecord,
    DatasetIndex,
    IndexRole,
)


class DailyLasGrowthError(ValueError):
    """Raised when a LAS file cannot be appended without changing history."""


_LOCAL_DERIVED_PROVENANCE_PREFIXES = ("calculation:", "custom-formula:")
_STABLE_WELL_ID_HEADERS = ("WELL", "UWI", "API")


@dataclass(frozen=True, slots=True)
class DailyLasGrowthPlan:
    target_dataset_id: str
    source_name: str
    source_sha256: str
    index_role: IndexRole
    index_mnemonic: str
    start_value: str
    stop_value: str
    rows_added: int
    rows_skipped: int
    new_row_indices: tuple[int, ...]
    curve_mnemonics: tuple[str, ...]
    target_state_sha256: str
    source_state_sha256: str
    duplicate_source: bool = False

    @property
    def changes_data(self) -> bool:
        return self.rows_added > 0


@dataclass(frozen=True, slots=True)
class DailyLasGrowthOutcome:
    plan: DailyLasGrowthPlan
    record: DatasetAppendRecord | None


def file_sha256(path: str | Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def dataset_content_sha256(dataset: Dataset) -> str:
    """Return a deterministic digest of the persisted numerical projection."""

    digest = sha256()
    digest.update(dataset.dataset_id.encode("utf-8"))
    for index in sorted(dataset.indexes.values(), key=lambda item: item.index_id):
        digest.update(index.index_id.encode("utf-8"))
        digest.update(index.mnemonic.encode("utf-8"))
        digest.update(index.index_type.value.encode("ascii"))
        digest.update(index.role.value.encode("ascii"))
        _update_array_digest(digest, np.asarray(index.values))
    curves = sorted(
        dataset.curves.values(),
        key=lambda item: (
            item.metadata.original_mnemonic.casefold(), item.metadata.curve_id
        ),
    )
    for curve in curves:
        digest.update(curve.metadata.curve_id.encode("utf-8"))
        digest.update(curve.metadata.original_mnemonic.encode("utf-8"))
        digest.update((curve.metadata.unit or "").encode("utf-8"))
        _update_array_digest(digest, np.asarray(curve.values))
    return digest.hexdigest()


def _update_array_digest(digest, values: np.ndarray) -> None:
    digest.update(values.dtype.str.encode("ascii"))
    digest.update(str(values.shape).encode("ascii"))
    # Preserve the historical C-order digest while bounding temporary copies,
    # including for strided arrays. A float64 buffer is at most 1 MiB.
    with np.nditer(
        values, flags=["external_loop", "buffered", "zerosize_ok"],
        op_flags=["readonly"], order="C", buffersize=131_072,
    ) as chunks:
        for chunk in chunks:
            digest.update(cast(np.ndarray, chunk).tobytes())


def dataset_append_state_sha256(dataset: Dataset) -> str:
    """Bind preview to all append inputs without changing persisted audit hashes.

    Cost is O(samples + metadata), with bounded array buffers; the plan retains
    only the digest. Presentation names and well-level authored layers are not
    append inputs and deliberately do not invalidate a numerical preview.
    """
    digest = sha256(b"daily-las-preview:1\0")
    digest.update(dataset_content_sha256(dataset).encode("ascii"))
    _update_array_digest(digest, np.asarray(dataset.depth))
    metadata = {
        "kind": dataset.kind,
        "depth_domain": dataset.depth_domain,
        "active_index_id": dataset.active_index_id,
        "headers": dataset.headers,
        "indexes": {
            key: (index.index_id, index.mnemonic, index.index_type, index.role,
                  index.unit, index.datetime_format, index.timezone)
            for key, index in dataset.indexes.items()
        },
        "curves": {
            key: (curve.metadata.curve_id, curve.metadata.original_mnemonic,
                  curve.metadata.unit, curve.metadata.source_dataset_id,
                  curve.metadata.provenance, curve.version, curve.state)
            for key, curve in dataset.curves.items()
        },
        "append_history": [asdict(record) for record in dataset.append_history],
        "source_revisions": [asdict(record) for record in dataset.source_revisions],
    }
    digest.update(json.dumps(metadata, sort_keys=True, ensure_ascii=True).encode("ascii"))
    return digest.hexdigest()


def analyze_daily_las_growth(
    target: Dataset,
    source: Dataset,
    *,
    source_name: str,
    source_sha256: str,
) -> DailyLasGrowthPlan:
    """Build a non-mutating append plan for one explicitly selected dataset.

    The contract is intentionally strict. DEPTH and TIME never cross, curve
    schemas must match, an already imported source is a no-op, equal overlap is
    skipped and conflicting overlap is rejected. New rows must form a suffix in
    the same monotonic direction as the target dataset.
    """

    if target.dataset_id == source.dataset_id:
        raise DailyLasGrowthError("Источник и приёмник не должны быть одним dataset")
    if not source_name.strip():
        raise DailyLasGrowthError("Не задано имя исходного LAS")
    if len(source_sha256) != 64 or any(ch not in "0123456789abcdef" for ch in source_sha256):
        raise DailyLasGrowthError("Некорректный SHA-256 исходного LAS")
    _validate_well_identity(target, source)
    if any(item.source_sha256 == source_sha256 for item in target.append_history) or any(
        item.source_sha256 == source_sha256 for item in target.source_revisions
    ):
        active = source.active_index
        return DailyLasGrowthPlan(
            target.dataset_id,
            source_name,
            source_sha256,
            active.role,
            active.mnemonic,
            _format_index_value(active.values[0]) if len(active.values) else "",
            _format_index_value(active.values[-1]) if len(active.values) else "",
            0,
            len(active.values),
            (),
            tuple(sorted(_curve_map(source))),
            dataset_append_state_sha256(target),
            dataset_append_state_sha256(source),
            True,
        )

    target_index = target.active_index
    source_index = source.active_index
    _validate_axis_compatibility(target_index, source_index)
    target_curves = _curve_map(target)
    target_native_curves = {
        key: curve
        for key, curve in target_curves.items()
        if not _is_local_project_curve(curve)
    }
    source_curves = _curve_map(source)
    _validate_curve_lengths(target, target_curves, label="целевого dataset")
    _validate_curve_lengths(source, source_curves, label="исходного LAS")
    if set(target_native_curves) != set(source_curves):
        missing = sorted(set(target_native_curves) - set(source_curves))
        extra = sorted(set(source_curves) - set(target_native_curves))
        parts: list[str] = []
        if missing:
            parts.append("нет обязательных кривых: " + ", ".join(missing))
        if extra:
            parts.append("лишние кривые: " + ", ".join(extra))
        raise DailyLasGrowthError("Схема LAS не совпадает с dataset (" + "; ".join(parts) + ")")
    for key in sorted(target_native_curves):
        left = _unit(target_native_curves[key].metadata.unit)
        right = _unit(source_curves[key].metadata.unit)
        if left != right:
            raise DailyLasGrowthError(
                f"Единица кривой {target_native_curves[key].metadata.original_mnemonic} "
                f"не совпадает: {left or '—'} / {right or '—'}"
            )

    target_values = _comparable_index(target_index)
    source_values = _comparable_index(source_index)
    direction = _strict_direction(target_values, "целевого dataset")
    source_direction = _strict_direction(source_values, "исходного LAS")
    if direction != source_direction:
        raise DailyLasGrowthError("Направление индекса исходного LAS не совпадает с dataset")

    existing_lookup = {_index_key(value): pos for pos, value in enumerate(target_values)}
    new_rows: list[int] = []
    skipped = 0
    new_phase = False
    terminal = target_values[-1]
    for source_row, value in enumerate(source_values):
        existing_row = existing_lookup.get(_index_key(value))
        if existing_row is not None:
            if new_phase:
                raise DailyLasGrowthError(
                    "Пересекающиеся строки должны находиться перед новым append-only суффиксом"
                )
            _validate_overlapping_row(
                target_native_curves,
                source_curves,
                existing_row=existing_row,
                source_row=source_row,
                index_text=_format_index_value(source_index.values[source_row]),
            )
            skipped += 1
            continue
        new_phase = True
        if direction > 0 and not value > terminal:
            raise DailyLasGrowthError("Новая строка находится внутри уже сохранённого диапазона")
        if direction < 0 and not value < terminal:
            raise DailyLasGrowthError("Новая строка находится внутри уже сохранённого диапазона")
        new_rows.append(source_row)

    start = _format_index_value(source_index.values[0]) if len(source_index.values) else ""
    stop = _format_index_value(source_index.values[-1]) if len(source_index.values) else ""
    return DailyLasGrowthPlan(
        target_dataset_id=target.dataset_id,
        source_name=source_name.strip(),
        source_sha256=source_sha256,
        index_role=source_index.role,
        index_mnemonic=source_index.mnemonic,
        start_value=start,
        stop_value=stop,
        rows_added=len(new_rows),
        rows_skipped=skipped,
        new_row_indices=tuple(new_rows),
        curve_mnemonics=tuple(
            target_native_curves[key].metadata.original_mnemonic
            for key in sorted(target_native_curves)
        ),
        target_state_sha256=dataset_append_state_sha256(target),
        source_state_sha256=dataset_append_state_sha256(source),
    )


def apply_daily_las_growth(
    target: Dataset,
    source: Dataset,
    plan: DailyLasGrowthPlan,
    *,
    imported_at: datetime | None = None,
    provider_kind: str = "manual_file",
    provider_location: str | None = None,
) -> DailyLasGrowthOutcome:
    """Atomically append the rows described by a fresh plan."""

    if target.dataset_id != plan.target_dataset_id:
        raise DailyLasGrowthError("План относится к другому dataset")
    normalized_provider_kind = provider_kind.strip()
    if not normalized_provider_kind or len(normalized_provider_kind) > 80:
        raise DailyLasGrowthError("Некорректный тип источника LAS")
    if provider_location is not None and len(provider_location) > 2_000:
        raise DailyLasGrowthError("Путь источника LAS слишком длинный")
    current = analyze_daily_las_growth(
        target,
        source,
        source_name=plan.source_name,
        source_sha256=plan.source_sha256,
    )
    if current != plan:
        raise DailyLasGrowthError("Dataset или источник изменились после предварительного анализа")
    if plan.duplicate_source or not plan.new_row_indices:
        return DailyLasGrowthOutcome(plan, None)

    if len(target.indexes) != 1 or len(source.indexes) != 1:
        raise DailyLasGrowthError(
            "Ежедневное наращивание поддерживает raw dataset с одним исходным индексом; "
            "derived-проекции пересчитываются отдельно"
        )

    rows = np.asarray(plan.new_row_indices, dtype=np.int64)
    target_curves = _curve_map(target)
    source_curves = _curve_map(source)

    # Prepare every resulting array before touching the target. This keeps the
    # operation transactional even if allocation or conversion fails.
    new_index_values = np.concatenate((target.active_index.values, source.active_index.values[rows]))
    prepared_curves: dict[str, np.ndarray] = {}
    for key, curve in target_curves.items():
        if _is_local_project_curve(curve):
            appended_values = np.full(len(rows), np.nan, dtype=np.float64)
        else:
            appended_values = source_curves[key].values[rows]
        prepared_curves[key] = np.concatenate((curve.values, appended_values))
    before_digest = dataset_content_sha256(target)
    moment = (imported_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    import_id = str(uuid4())

    target.active_index.values = new_index_values
    if target.active_index.role is IndexRole.DEPTH:
        target.depth = np.asarray(new_index_values, dtype=np.float64)
    else:
        # ``depth`` remains the legacy row coordinate for TIME datasets.
        target.depth = np.asarray(new_index_values, dtype=np.float64)
    for key, values in prepared_curves.items():
        curve = target_curves[key]
        curve.values = values
        curve.version += 1
        if _is_local_derived(curve):
            curve.state = CalculationState.STALE
    _refresh_las_range_headers(target)
    after_digest = dataset_content_sha256(target)
    record = DatasetAppendRecord(
        import_id=import_id,
        source_name=plan.source_name,
        source_sha256=plan.source_sha256,
        imported_at=moment.isoformat().replace("+00:00", "Z"),
        index_role=source.active_index.role,
        index_type=source.active_index.index_type,
        index_unit=source.active_index.unit,
        start_value=plan.start_value,
        stop_value=plan.stop_value,
        rows_added=plan.rows_added,
        rows_skipped=plan.rows_skipped,
        curve_mnemonics=plan.curve_mnemonics,
        source_artifact_id=import_id,
        provider_kind=normalized_provider_kind,
        provider_location=provider_location,
        dataset_sha256_before=before_digest,
        dataset_sha256_after=after_digest,
    )
    target.append_history.append(record)
    return DailyLasGrowthOutcome(plan, record)


def _validate_axis_compatibility(target: DatasetIndex, source: DatasetIndex) -> None:
    if target.role not in {IndexRole.DEPTH, IndexRole.TIME}:
        raise DailyLasGrowthError("Целевой dataset не имеет DEPTH/TIME оси")
    if source.role != target.role:
        raise DailyLasGrowthError(
            f"Импорт запрещён: источник {source.role.value.upper()}, "
            f"приёмник {target.role.value.upper()}"
        )
    if source.index_type != target.index_type:
        raise DailyLasGrowthError(
            f"Тип индекса не совпадает: {source.index_type.value} / {target.index_type.value}"
        )
    if _unit(source.unit) != _unit(target.unit):
        raise DailyLasGrowthError(
            f"Единица индекса не совпадает: {_unit(source.unit) or '—'} / "
            f"{_unit(target.unit) or '—'}"
        )


def _validate_well_identity(target: Dataset, source: Dataset) -> None:
    for header in _STABLE_WELL_ID_HEADERS:
        target_value = _header_value(target, header).strip().casefold()
        source_value = _header_value(source, header).strip().casefold()
        if target_value and source_value and target_value != source_value:
            raise DailyLasGrowthError(
                f"Идентификатор скважины {header} в LAS не совпадает с выбранной скважиной"
            )


def _header_value(dataset: Dataset, mnemonic: str) -> str:
    expected = mnemonic.casefold()
    for key, value in dataset.headers.items():
        if key.strip().casefold() == expected:
            return value
    return ""


def _is_local_derived(curve: CurveData) -> bool:
    provenance = curve.metadata.provenance.strip().casefold()
    return provenance.startswith(_LOCAL_DERIVED_PROVENANCE_PREFIXES)


def _is_local_project_curve(curve: CurveData) -> bool:
    """Distinguish original LAS channels from curves added inside the project."""

    return curve.metadata.provenance.strip().casefold() not in {"", "source"}


def _validate_curve_lengths(
    dataset: Dataset,
    curves: dict[str, CurveData],
    *,
    label: str,
) -> None:
    row_count = len(dataset.active_index.values)
    invalid = [
        curve.metadata.original_mnemonic
        for curve in curves.values()
        if np.asarray(curve.values).shape != (row_count,)
    ]
    if invalid:
        raise DailyLasGrowthError(
            f"Размер кривых {label} не совпадает с индексом: " + ", ".join(sorted(invalid))
        )


def _curve_map(dataset: Dataset) -> dict[str, CurveData]:
    result: dict[str, CurveData] = {}
    for curve in dataset.curves.values():
        key = curve.metadata.original_mnemonic.strip().casefold()
        if key in result:
            raise DailyLasGrowthError(
                f"Dataset содержит повторяющуюся мнемонику: {curve.metadata.original_mnemonic}"
            )
        result[key] = curve
    return result


def _unit(value: str | None) -> str:
    return (value or "").strip().casefold().replace(" ", "")


def _comparable_index(index: DatasetIndex) -> np.ndarray:
    values = np.asarray(index.values)
    if np.issubdtype(values.dtype, np.datetime64):
        comparable = values.astype("datetime64[ns]").astype(np.int64)
        if np.any(comparable == np.iinfo(np.int64).min):
            raise DailyLasGrowthError("Индекс содержит NaT")
        return comparable
    try:
        comparable = values.astype(np.float64)
    except (TypeError, ValueError) as exc:
        raise DailyLasGrowthError("Индекс должен быть числовым или datetime") from exc
    if comparable.ndim != 1 or len(comparable) == 0 or not np.all(np.isfinite(comparable)):
        raise DailyLasGrowthError("Индекс должен быть непустым и содержать конечные значения")
    return comparable


def _strict_direction(values: np.ndarray, label: str) -> int:
    if len(values) < 2:
        return 1
    differences = np.diff(values)
    if np.all(differences > 0):
        return 1
    if np.all(differences < 0):
        return -1
    raise DailyLasGrowthError(f"Индекс {label} должен быть строго монотонным")


def _index_key(value: object) -> tuple[str, int | float]:
    if isinstance(value, (np.integer, int)):
        return ("i", int(value))
    return ("f", round(float(cast(float, value)), 9))


def _same_value(left: float, right: float) -> bool:
    if np.isnan(left) and np.isnan(right):
        return True
    return bool(np.isclose(left, right, rtol=1e-9, atol=1e-9, equal_nan=True))


def _validate_overlapping_row(
    target_curves,
    source_curves,
    *,
    existing_row: int,
    source_row: int,
    index_text: str,
) -> None:
    conflicts = []
    for key in target_curves:
        left = float(target_curves[key].values[existing_row])
        right = float(source_curves[key].values[source_row])
        if not _same_value(left, right):
            conflicts.append(target_curves[key].metadata.original_mnemonic)
    if conflicts:
        raise DailyLasGrowthError(
            f"Конфликт в уже сохранённой точке {index_text}: " + ", ".join(conflicts)
        )


def _format_index_value(value: object) -> str:
    if isinstance(value, np.datetime64):
        return str(value.astype("datetime64[ns]"))
    try:
        return f"{float(cast(float, value)):.12g}"
    except (TypeError, ValueError):
        return str(value)


def _refresh_las_range_headers(dataset: Dataset) -> None:
    values = np.asarray(dataset.active_index.values)
    dataset.headers["STRT"] = _format_index_value(values[0])
    dataset.headers["STOP"] = _format_index_value(values[-1])
    if len(values) > 1 and not np.issubdtype(values.dtype, np.datetime64):
        step = float(np.median(np.diff(values.astype(np.float64))))
        dataset.headers["STEP"] = f"{step:.12g}"
