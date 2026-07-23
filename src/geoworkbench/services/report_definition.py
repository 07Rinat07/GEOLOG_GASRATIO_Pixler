from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from hashlib import sha256
from math import isfinite
from typing import Any, Mapping

import numpy as np
from numpy.typing import NDArray

from geoworkbench.domain.models import Dataset, DatasetIndex, IndexType
from geoworkbench.services.coverage import ChannelCoverage, analyze_dataset_coverage


REPORT_DEFINITION_SCHEMA_VERSION = 2
_SUPPORTED_LANGUAGES = {"ru", "kk", "en"}


class ReportDefinitionError(RuntimeError):
    """Raised when a report definition cannot be resolved against a dataset."""


class ReportProfile(StrEnum):
    VIEW = "view"
    MASTERLOG = "masterlog"
    GEOLOGY = "geology"
    CUTTINGS = "cuttings"
    CALCIMETRY = "calcimetry"
    LBA = "lba"
    GAS = "gas"
    DRILLING = "drilling"
    EVENTS = "events"
    COMBINED = "combined"


class ReportSectionKind(StrEnum):
    GEOLOGY = "geology"
    CUTTINGS = "cuttings"
    CALCIMETRY = "calcimetry"
    LBA = "lba"
    GAS = "gas"
    DRILLING = "drilling"
    EVENTS = "events"
    CURVES = "curves"
    MASTERLOG = "masterlog"


class ReportIntervalMode(StrEnum):
    CURRENT = "current"
    FULL = "full"
    CUSTOM = "custom"
    SELECTION = "selection"


ReportBoundary = float | str
ReportRange = tuple[ReportBoundary, ReportBoundary]


@dataclass(frozen=True, slots=True)
class ReportIntervalSelection:
    mode: ReportIntervalMode = ReportIntervalMode.FULL
    start: ReportBoundary | None = None
    end: ReportBoundary | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.mode, ReportIntervalMode):
            raise ValueError("Режим интервала отчёта должен использовать ReportIntervalMode")
        if self.mode is ReportIntervalMode.CUSTOM:
            if self.start is None or self.end is None:
                raise ValueError("Пользовательский интервал отчёта требует начало и конец")
        elif self.start is not None or self.end is not None:
            raise ValueError("Границы задаются только для пользовательского интервала")


@dataclass(frozen=True, slots=True)
class ReportSectionDefinition:
    kind: ReportSectionKind
    enabled: bool = True
    curve_ids: tuple[str, ...] = ()
    channel_mnemonics: tuple[str, ...] = ()
    options: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ReportSectionKind):
            raise ValueError("Раздел отчёта должен использовать ReportSectionKind")
        _validate_string_tuple(self.curve_ids, "curve_ids раздела")
        _validate_string_tuple(self.channel_mnemonics, "channel_mnemonics раздела")
        _validate_options(self.options)


@dataclass(frozen=True, slots=True)
class ReportDefinition:
    definition_id: str
    name: str
    profile: ReportProfile
    dataset_id: str
    index_id: str
    interval: ReportIntervalSelection
    language: str = "ru"
    curve_ids: tuple[str, ...] = ()
    channel_mnemonics: tuple[str, ...] = ()
    sections: tuple[ReportSectionDefinition, ...] = ()
    form_kind: str | None = None
    form_id: str | None = None
    form_revision: str | None = None
    options: tuple[tuple[str, str], ...] = ()
    schema_version: int = REPORT_DEFINITION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != REPORT_DEFINITION_SCHEMA_VERSION:
            raise ValueError("Неподдерживаемая версия ReportDefinition")
        for label, value in (
            ("definition_id", self.definition_id),
            ("name", self.name),
            ("dataset_id", self.dataset_id),
            ("index_id", self.index_id),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{label} ReportDefinition не должен быть пустым")
        if not isinstance(self.profile, ReportProfile):
            raise ValueError("Профиль отчёта должен использовать ReportProfile")
        if not isinstance(self.interval, ReportIntervalSelection):
            raise ValueError("Интервал отчёта должен использовать ReportIntervalSelection")
        normalized_language = str(self.language).strip().casefold()
        if normalized_language not in _SUPPORTED_LANGUAGES:
            raise ValueError("Язык ReportDefinition должен быть ru, kk или en")
        object.__setattr__(self, "language", normalized_language)
        _validate_string_tuple(self.curve_ids, "curve_ids отчёта")
        _validate_string_tuple(self.channel_mnemonics, "channel_mnemonics отчёта")
        if not all(isinstance(item, ReportSectionDefinition) for item in self.sections):
            raise ValueError("Разделы отчёта должны использовать ReportSectionDefinition")
        _validate_options(self.options)
        form_values = (self.form_kind, self.form_id, self.form_revision)
        if any(value is not None for value in form_values) and not all(
            isinstance(value, str) and value.strip() for value in form_values
        ):
            raise ValueError("form_kind, form_id и form_revision задаются только вместе")

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> ReportDefinition:
        if not isinstance(payload, Mapping):
            raise ValueError("ReportDefinition должен быть объектом")
        try:
            interval_raw = payload["interval"]
            if not isinstance(interval_raw, Mapping):
                raise ValueError("interval ReportDefinition должен быть объектом")
            interval = ReportIntervalSelection(
                ReportIntervalMode(str(interval_raw["mode"])),
                interval_raw.get("start"),
                interval_raw.get("end"),
            )
            sections_raw = payload.get("sections", ())
            if not isinstance(sections_raw, (list, tuple)):
                raise ValueError("sections ReportDefinition должен быть массивом")
            if not all(isinstance(item, Mapping) for item in sections_raw):
                raise ValueError("Элементы sections ReportDefinition должны быть объектами")
            sections = tuple(
                ReportSectionDefinition(
                    kind=ReportSectionKind(str(item["kind"])),
                    enabled=bool(item.get("enabled", True)),
                    curve_ids=tuple(str(value) for value in item.get("curve_ids", ())),
                    channel_mnemonics=tuple(
                        str(value) for value in item.get("channel_mnemonics", ())
                    ),
                    options=tuple(
                        (str(option[0]), str(option[1]))
                        for option in item.get("options", ())
                    ),
                )
                for item in sections_raw
            )
            return cls(
                definition_id=str(payload["definition_id"]),
                name=str(payload["name"]),
                profile=ReportProfile(str(payload["profile"])),
                dataset_id=str(payload["dataset_id"]),
                index_id=str(payload["index_id"]),
                interval=interval,
                language=str(payload.get("language", "ru")),
                curve_ids=tuple(str(value) for value in payload.get("curve_ids", ())),
                channel_mnemonics=tuple(
                    str(value) for value in payload.get("channel_mnemonics", ())
                ),
                sections=sections,
                form_kind=_optional_text(payload.get("form_kind")),
                form_id=_optional_text(payload.get("form_id")),
                form_revision=_optional_text(payload.get("form_revision")),
                options=tuple(
                    (str(option[0]), str(option[1]))
                    for option in payload.get("options", ())
                ),
                schema_version=(
                    REPORT_DEFINITION_SCHEMA_VERSION
                    if int(payload.get("schema_version", REPORT_DEFINITION_SCHEMA_VERSION)) == 1
                    else int(payload.get("schema_version", REPORT_DEFINITION_SCHEMA_VERSION))
                ),
            )
        except (KeyError, TypeError, ValueError) as exc:
            if isinstance(exc, ValueError) and str(exc).startswith("ReportDefinition"):
                raise
            raise ValueError(f"Некорректный payload ReportDefinition: {exc}") from exc

    @property
    def selected_curve_ids(self) -> tuple[str, ...]:
        values = list(self.curve_ids)
        for section in self.sections:
            if section.enabled:
                values.extend(section.curve_ids)
        return tuple(dict.fromkeys(values))

    @property
    def selected_channel_mnemonics(self) -> tuple[str, ...]:
        values = list(self.channel_mnemonics)
        for section in self.sections:
            if section.enabled:
                values.extend(section.channel_mnemonics)
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            normalized = value.strip()
            key = normalized.casefold()
            if normalized and key not in seen:
                seen.add(key)
                result.append(normalized)
        return tuple(result)

    def payload(self) -> dict[str, Any]:
        return _json_ready(asdict(self))

    def canonical_json(self) -> str:
        return json.dumps(
            self.payload(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    @property
    def content_sha256(self) -> str:
        return sha256(self.canonical_json().encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ReportIntervalContext:
    current_range: ReportRange | None = None
    full_range: ReportRange | None = None
    selection_range: ReportRange | None = None


@dataclass(frozen=True, slots=True)
class ResolvedReportInterval:
    index_id: str
    start: ReportBoundary
    end: ReportBoundary
    sample_count: int
    indices: NDArray[np.int64] = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        values = np.asarray(self.indices, dtype=np.int64)
        if values.ndim != 1 or values.size == 0:
            raise ValueError("Разрешённый интервал должен содержать отсчёты")
        if self.sample_count != int(values.size):
            raise ValueError("sample_count не совпадает с индексами интервала")
        values = values.copy()
        values.setflags(write=False)
        object.__setattr__(self, "indices", values)

    @property
    def bounds(self) -> ReportRange:
        return self.start, self.end


@dataclass(frozen=True, slots=True)
class ResolvedReportDefinition:
    definition: ReportDefinition
    interval: ResolvedReportInterval
    curve_ids: tuple[str, ...]
    unavailable_channel_mnemonics: tuple[str, ...] = ()
    coverage: tuple[ChannelCoverage, ...] = field(default=(), repr=False, compare=False)

    @property
    def curve_count(self) -> int:
        return len(self.curve_ids)

    @property
    def requested_channel_count(self) -> int:
        return len(self.coverage)

    @property
    def requested_channel_mnemonics(self) -> tuple[str, ...]:
        values = [item.mnemonic for item in self.coverage]
        return tuple(dict.fromkeys(values))


def resolve_report_definition(
    dataset: Dataset,
    definition: ReportDefinition,
    *,
    context: ReportIntervalContext | None = None,
    require_curves: bool = False,
) -> ResolvedReportDefinition:
    """Resolve one immutable report definition against concrete dataset samples.

    The returned interval is the only range that downstream preview, PDF, passport and
    tabular exporters should use.  Resolution is inclusive and clamps user/view ranges to
    the selected index domain without silently switching to another index.
    """

    if dataset.dataset_id != definition.dataset_id:
        raise ReportDefinitionError("ReportDefinition относится к другому dataset")
    try:
        index = dataset.indexes[definition.index_id]
    except KeyError as exc:
        raise ReportDefinitionError(
            f"Индекс ReportDefinition не найден: {definition.index_id}"
        ) from exc

    resolved_context = context or ReportIntervalContext()
    full_range = _normalize_range(index, resolved_context.full_range or _index_bounds(index))
    requested = _requested_range(definition.interval, resolved_context, full_range)
    start, end = _clamp_range(index, requested, full_range)
    indices = _interval_indices(index, start, end)

    explicit_curve_ids = definition.selected_curve_ids
    missing_ids = tuple(
        curve_id for curve_id in explicit_curve_ids if curve_id not in dataset.curves
    )
    if missing_ids:
        raise ReportDefinitionError(
            "Каналы ReportDefinition не найдены по ID: " + ", ".join(missing_ids)
        )

    selected_ids = list(explicit_curve_ids)
    unavailable: list[str] = []
    for mnemonic in definition.selected_channel_mnemonics:
        curve = dataset.curve_by_mnemonic(mnemonic)
        if curve is None:
            unavailable.append(mnemonic)
        elif curve.metadata.curve_id not in selected_ids:
            selected_ids.append(curve.metadata.curve_id)

    if require_curves and not selected_ids and not unavailable:
        raise ReportDefinitionError("ReportDefinition не содержит запрошенных каналов")

    resolved_interval = ResolvedReportInterval(
        index_id=index.index_id,
        start=start,
        end=end,
        sample_count=int(indices.size),
        indices=indices,
    )
    coverage = analyze_dataset_coverage(
        dataset,
        selected_ids,
        indices,
        unavailable_mnemonics=unavailable,
    )
    return ResolvedReportDefinition(
        definition=definition,
        interval=resolved_interval,
        curve_ids=tuple(selected_ids),
        unavailable_channel_mnemonics=tuple(unavailable),
        coverage=coverage,
    )


def definition_interval_payload(resolved: ResolvedReportDefinition) -> dict[str, Any]:
    """Return the normalized interval fragment embedded into passports and logs."""

    return {
        "index_id": resolved.interval.index_id,
        "start": resolved.interval.start,
        "end": resolved.interval.end,
        "sample_count": resolved.interval.sample_count,
    }


def _requested_range(
    selection: ReportIntervalSelection,
    context: ReportIntervalContext,
    full_range: ReportRange,
) -> ReportRange:
    if selection.mode is ReportIntervalMode.FULL:
        return full_range
    if selection.mode is ReportIntervalMode.CURRENT:
        return context.current_range or full_range
    if selection.mode is ReportIntervalMode.SELECTION:
        if context.selection_range is None:
            raise ReportDefinitionError("Для режима selection отсутствует выбранный интервал")
        return context.selection_range
    assert selection.start is not None and selection.end is not None
    return selection.start, selection.end


def _index_bounds(index: DatasetIndex) -> ReportRange:
    values = np.asarray(index.values)
    if index.index_type is IndexType.DATETIME:
        normalized = values.astype("datetime64[ns]")
        valid = normalized[~np.isnat(normalized)]
        if valid.size == 0:
            raise ReportDefinitionError("Индекс отчёта не содержит допустимых значений")
        return _datetime_text(valid.min()), _datetime_text(valid.max())
    try:
        numeric = values.astype(np.float64)
    except (TypeError, ValueError) as exc:
        raise ReportDefinitionError("Индекс отчёта должен быть числовым или datetime") from exc
    valid = numeric[np.isfinite(numeric)]
    if valid.size == 0:
        raise ReportDefinitionError("Индекс отчёта не содержит допустимых значений")
    return float(np.min(valid)), float(np.max(valid))


def _normalize_range(index: DatasetIndex, values: ReportRange) -> ReportRange:
    start = _coerce_boundary(index, values[0])
    end = _coerce_boundary(index, values[1])
    if _boundary_key(index, start) > _boundary_key(index, end):
        start, end = end, start
    return start, end


def _clamp_range(
    index: DatasetIndex,
    requested: ReportRange,
    full_range: ReportRange,
) -> ReportRange:
    start, end = _normalize_range(index, requested)
    full_start, full_end = _normalize_range(index, full_range)
    start_key = max(_boundary_key(index, start), _boundary_key(index, full_start))
    end_key = min(_boundary_key(index, end), _boundary_key(index, full_end))
    if start_key > end_key:
        raise ReportDefinitionError("Интервал отчёта находится вне выбранного индекса")
    return _boundary_from_key(index, start_key), _boundary_from_key(index, end_key)


def _interval_indices(
    index: DatasetIndex,
    start: ReportBoundary,
    end: ReportBoundary,
) -> NDArray[np.int64]:
    values = np.asarray(index.values)
    if index.index_type is IndexType.DATETIME:
        normalized = values.astype("datetime64[ns]")
        start_value = np.datetime64(str(start), "ns")
        end_value = np.datetime64(str(end), "ns")
        mask = ~np.isnat(normalized) & (normalized >= start_value) & (normalized <= end_value)
    else:
        numeric = values.astype(np.float64)
        mask = np.isfinite(numeric) & (numeric >= float(start)) & (numeric <= float(end))
    indices = np.flatnonzero(mask).astype(np.int64)
    if indices.size == 0:
        raise ReportDefinitionError("Разрешённый интервал не содержит отсчётов")
    return indices


def _coerce_boundary(index: DatasetIndex, value: ReportBoundary) -> ReportBoundary:
    if index.index_type is IndexType.DATETIME:
        try:
            normalized = np.datetime64(str(value), "ns")
        except (TypeError, ValueError) as exc:
            raise ReportDefinitionError(f"Некорректная datetime-граница: {value}") from exc
        if np.isnat(normalized):
            raise ReportDefinitionError("Datetime-граница отчёта не может быть NaT")
        return _datetime_text(normalized)
    if isinstance(value, bool):
        raise ReportDefinitionError("Числовая граница отчёта не может быть логической")
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ReportDefinitionError(f"Некорректная числовая граница: {value}") from exc
    if not isfinite(numeric):
        raise ReportDefinitionError("Граница отчёта должна быть конечным числом")
    return numeric


def _boundary_key(index: DatasetIndex, value: ReportBoundary) -> int | float:
    if index.index_type is IndexType.DATETIME:
        return int(np.datetime64(str(value), "ns").astype(np.int64))
    return float(value)


def _boundary_from_key(index: DatasetIndex, value: int | float) -> ReportBoundary:
    if index.index_type is IndexType.DATETIME:
        return _datetime_text(np.datetime64(int(value), "ns"))
    return float(value)


def _datetime_text(value: np.datetime64) -> str:
    return str(value.astype("datetime64[ns]"))


def _validate_string_tuple(values: tuple[str, ...], label: str) -> None:
    if not isinstance(values, tuple) or not all(
        isinstance(value, str) and value.strip() for value in values
    ):
        raise ValueError(f"{label} должен быть tuple непустых строк")
    if len(set(values)) != len(values):
        raise ValueError(f"{label} не должен содержать дубликаты")


def _validate_options(values: tuple[tuple[str, str], ...]) -> None:
    if not isinstance(values, tuple) or not all(
        isinstance(item, tuple)
        and len(item) == 2
        and all(isinstance(value, str) and value.strip() for value in item)
        for item in values
    ):
        raise ValueError("Параметры ReportDefinition должны быть tuple пар непустых строк")
    keys = [key for key, _value in values]
    if len(set(keys)) != len(keys):
        raise ValueError("Параметры ReportDefinition не должны повторять ключи")


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _json_ready(value: Any) -> Any:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value
