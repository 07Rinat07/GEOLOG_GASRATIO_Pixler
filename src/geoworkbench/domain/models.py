from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from math import isfinite
from pathlib import Path
import re
from typing import Any
from uuid import uuid4

import numpy as np
from numpy.typing import NDArray


def new_id() -> str:
    return str(uuid4())


class DepthDomain(StrEnum):
    MD = "md"
    TVD = "tvd"
    TVDSS = "tvdss"
    TIME = "time"


class IndexType(StrEnum):
    MD = "md"
    TVD = "tvd"
    TVDSS = "tvdss"
    RELATIVE_TIME = "relative_time"
    DATETIME = "datetime"
    GENERIC = "generic"


class IndexRole(StrEnum):
    DEPTH = "depth"
    TIME = "time"
    GENERIC = "generic"


class TimeDepthAggregationPolicy(StrEnum):
    ERROR = "error"
    FIRST = "first"
    LAST = "last"
    MIN = "min"
    MAX = "max"
    MEAN = "mean"


class DatasetKind(StrEnum):
    GTI = "gti"
    GIS = "gis"
    CHROMATOGRAPHY = "chromatography"
    DERIVED = "derived"
    USER = "user"


class CalculationState(StrEnum):
    CURRENT = "current"
    STALE = "stale"
    CALCULATING = "calculating"
    ERROR = "error"
    FROZEN = "frozen"


class CanvasAnchorType(StrEnum):
    FREE = "free"
    DEPTH = "depth"
    TIME = "time"
    PARAMETER = "parameter"
    INTERVAL = "interval"
    TRACK = "track"
    PAGE = "page"


@dataclass(frozen=True, slots=True)
class CurveMetadata:
    curve_id: str
    original_mnemonic: str
    canonical_mnemonic: str | None
    unit: str | None
    description: str | None
    source_dataset_id: str
    provenance: str = "source"


@dataclass(slots=True)
class CurveData:
    metadata: CurveMetadata
    values: NDArray[np.float64]
    version: int = 1
    state: CalculationState = CalculationState.CURRENT


@dataclass(slots=True)
class DatasetIndex:
    index_id: str
    mnemonic: str
    index_type: IndexType
    role: IndexRole
    unit: str | None
    values: NDArray[Any]
    confidence: float = 1.0
    evidence: tuple[str, ...] = ()
    datetime_format: str | None = None
    timezone: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.index_id, str) or not self.index_id:
            raise ValueError("index_id должен быть непустой строкой")
        if not isinstance(self.mnemonic, str) or not self.mnemonic.strip():
            raise ValueError("Мнемоника индекса должна быть непустой строкой")
        if not isinstance(self.index_type, IndexType) or not isinstance(self.role, IndexRole):
            raise ValueError("Тип и роль индекса должны использовать поддерживаемые значения")
        if self.unit is not None and not isinstance(self.unit, str):
            raise ValueError("Единица индекса должна быть строкой")
        if not isinstance(self.evidence, tuple) or not all(
            isinstance(item, str) for item in self.evidence
        ):
            raise ValueError("Evidence индекса должен быть tuple строк")
        if self.datetime_format is not None and not isinstance(self.datetime_format, str):
            raise ValueError("Формат datetime должен быть строкой")
        if self.timezone is not None and not isinstance(self.timezone, str):
            raise ValueError("Часовой пояс должен быть строкой")
        values = np.asarray(self.values)
        if self.index_type is IndexType.DATETIME:
            if np.issubdtype(values.dtype, np.datetime64):
                values = values.astype("datetime64[ns]")
            elif np.issubdtype(values.dtype, np.integer):
                values = values.astype(np.int64).astype("datetime64[ns]")
            else:
                raise ValueError("DATETIME индекс должен содержать datetime64 или Unix ns")
        elif self.role in {IndexRole.DEPTH, IndexRole.TIME}:
            try:
                values = values.astype(np.float64)
            except (TypeError, ValueError) as exc:
                raise ValueError("Глубинный/временной индекс должен быть числовым") from exc
        self.values = values.copy()
        if self.values.ndim != 1:
            raise ValueError("Индекс dataset должен быть одномерным")
        if isinstance(self.confidence, bool) or not isinstance(
            self.confidence, (int, float, np.integer, np.floating)
        ):
            raise ValueError("Confidence индекса должен быть числом")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("Confidence индекса должен находиться в диапазоне 0–1")


@dataclass(slots=True)
class Dataset:
    dataset_id: str
    name: str
    kind: DatasetKind
    depth_domain: DepthDomain
    depth: NDArray[np.float64]
    curves: dict[str, CurveData] = field(default_factory=dict)
    source_path: Path | None = None
    headers: dict[str, str] = field(default_factory=dict)
    parameters: dict[str, str] = field(default_factory=dict)
    indexes: dict[str, DatasetIndex] = field(default_factory=dict)
    active_index_id: str | None = None
    version_headers: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.depth = np.asarray(self.depth, dtype=np.float64)
        if self.depth.ndim != 1:
            raise ValueError("Шкала depth должна быть одномерной")
        if not self.indexes:
            primary = _legacy_depth_index(self.dataset_id, self.depth_domain, self.depth)
            self.indexes[primary.index_id] = primary
            self.active_index_id = primary.index_id
        elif self.active_index_id is None:
            self.active_index_id = next(iter(self.indexes))
        self._validate_indexes()
        active = self.active_index
        if active.role is IndexRole.DEPTH:
            self.depth = np.asarray(active.values, dtype=np.float64)
            self.depth_domain = _depth_domain_for_index(active.index_type)

    @property
    def active_index(self) -> DatasetIndex:
        if self.active_index_id is None or self.active_index_id not in self.indexes:
            raise RuntimeError("Активный индекс dataset не определён")
        return self.indexes[self.active_index_id]

    def add_index(self, index: DatasetIndex, *, make_active: bool = False) -> None:
        if index.index_id in self.indexes:
            raise ValueError(f"Индекс уже существует: {index.index_id}")
        if index.values.shape != self.depth.shape:
            raise ValueError("Размер нового индекса не совпадает с dataset")
        self.indexes[index.index_id] = index
        if make_active:
            self.set_active_index(index.index_id)

    def set_active_index(self, index_id: str) -> None:
        try:
            index = self.indexes[index_id]
        except KeyError as exc:
            raise KeyError(f"Неизвестный индекс dataset: {index_id}") from exc
        self.active_index_id = index_id
        if index.role is IndexRole.DEPTH:
            self.depth = np.asarray(index.values, dtype=np.float64)
            self.depth_domain = _depth_domain_for_index(index.index_type)

    def _validate_indexes(self) -> None:
        if self.active_index_id not in self.indexes:
            raise ValueError("Активный индекс отсутствует в indexes")
        for index_id, index in self.indexes.items():
            if index.index_id != index_id:
                raise ValueError("Ключ indexes не совпадает с index_id")
            if index.values.shape != self.depth.shape:
                raise ValueError(f"Размер индекса {index.mnemonic} не совпадает с dataset")

    def curve_by_mnemonic(self, mnemonic: str) -> CurveData | None:
        wanted = mnemonic.casefold()
        for curve in self.curves.values():
            names = {
                curve.metadata.original_mnemonic.casefold(),
                (curve.metadata.canonical_mnemonic or "").casefold(),
            }
            if wanted in names:
                return curve
        return None

    def upsert_curve(
        self,
        mnemonic: str,
        values: NDArray[np.float64],
        *,
        unit: str | None = None,
        description: str | None = None,
        provenance: str = "derived",
    ) -> CurveData:
        existing = self.curve_by_mnemonic(mnemonic)
        if existing is not None:
            existing.values = np.asarray(values, dtype=np.float64)
            existing.version += 1
            existing.state = CalculationState.CURRENT
            return existing

        curve_id = new_id()
        curve = CurveData(
            metadata=CurveMetadata(
                curve_id=curve_id,
                original_mnemonic=mnemonic,
                canonical_mnemonic=mnemonic,
                unit=unit,
                description=description,
                source_dataset_id=self.dataset_id,
                provenance=provenance,
            ),
            values=np.asarray(values, dtype=np.float64),
        )
        self.curves[curve_id] = curve
        return curve


def _legacy_depth_index(
    dataset_id: str,
    depth_domain: DepthDomain,
    values: NDArray[np.float64],
) -> DatasetIndex:
    index_type = {
        DepthDomain.MD: IndexType.MD,
        DepthDomain.TVD: IndexType.TVD,
        DepthDomain.TVDSS: IndexType.TVDSS,
        DepthDomain.TIME: IndexType.RELATIVE_TIME,
    }[depth_domain]
    role = IndexRole.TIME if depth_domain is DepthDomain.TIME else IndexRole.DEPTH
    return DatasetIndex(
        index_id=f"{dataset_id}:primary-index",
        mnemonic="TIME" if role is IndexRole.TIME else "DEPT",
        index_type=index_type,
        role=role,
        unit="ms" if role is IndexRole.TIME else "m",
        values=values,
        evidence=("legacy depth/depth_domain compatibility",),
    )


def _depth_domain_for_index(index_type: IndexType) -> DepthDomain:
    try:
        return DepthDomain(index_type.value)
    except ValueError as exc:
        raise ValueError(f"Тип {index_type.value} не является глубинным") from exc


@dataclass(slots=True)
class LithologyInterval:
    interval_id: str
    top_depth: float
    bottom_depth: float
    lithotype_id: str
    description: str | None = None


@dataclass(slots=True)
class CuttingsComponent:
    lithotype_id: str
    percentage: float


@dataclass(slots=True)
class CuttingsSample:
    sample_id: str
    top_depth: float
    bottom_depth: float
    components: list[CuttingsComponent] = field(default_factory=list)
    lba_type_id: str | None = None
    lba_intensity: int | None = None
    description: str | None = None


@dataclass(slots=True)
class StratigraphyInterval:
    interval_id: str
    top_depth: float
    bottom_depth: float
    code: str
    name: str | None
    rank: str | None


@dataclass(slots=True)
class CanvasObject:
    object_id: str
    object_type: str
    anchor_type: str
    x: float
    y: float
    width: float
    height: float
    top_depth: float | None = None
    bottom_depth: float | None = None
    time_value: str | None = None
    parameter_mnemonic: str | None = None
    track_id: str | None = None
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class MasterlogHeaderElement:
    element_id: str
    element_type: str
    x_mm: float
    y_mm: float
    width_mm: float
    height_mm: float
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class MasterlogColumnTemplate:
    column_id: str
    title: str
    column_type: str
    width_mm: float
    curve_mnemonics: list[str] = field(default_factory=list)
    properties: dict[str, Any] = field(default_factory=dict)
    x_scale: str = "linear"
    x_min: float | None = None
    x_max: float | None = None
    show_legend: bool = True
    line_color: str = "#2563eb"
    line_width: float = 1.5
    line_style: str = "solid"

    def __post_init__(self) -> None:
        if self.x_scale not in {"linear", "logarithmic"}:
            raise ValueError("Шкала колонки должна быть linear или logarithmic")
        if (self.x_min is None) != (self.x_max is None):
            raise ValueError("Границы X колонки должны задаваться вместе")
        if self.x_min is not None and self.x_max is not None:
            if not isfinite(self.x_min) or not isfinite(self.x_max):
                raise ValueError("Границы X колонки должны быть конечными")
            if self.x_min >= self.x_max:
                raise ValueError("Минимум X колонки должен быть меньше максимума")
            if self.x_scale == "logarithmic" and self.x_min <= 0:
                raise ValueError("Логарифмический диапазон колонки должен быть положительным")
        if not isinstance(self.show_legend, bool):
            raise ValueError("Видимость легенды должна быть логическим значением")
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", self.line_color):
            raise ValueError("Цвет линии колонки должен быть в формате #RRGGBB")
        if isinstance(self.line_width, bool) or not isinstance(
            self.line_width, (int, float)
        ):
            raise ValueError("Толщина линии колонки должна быть числом")
        if not isfinite(self.line_width) or not 0.5 <= self.line_width <= 10.0:
            raise ValueError("Толщина линии колонки должна быть от 0.5 до 10 px")
        if self.line_style not in {"solid", "dash", "dot", "dash_dot"}:
            raise ValueError("Стиль линии колонки не поддерживается")


@dataclass(slots=True)
class MasterlogTemplate:
    template_id: str
    name: str
    page_format: str = "roll"
    depth_scale: int = 500
    header_height_mm: float = 45.0
    header_elements: list[MasterlogHeaderElement] = field(default_factory=list)
    columns: list[MasterlogColumnTemplate] = field(default_factory=list)
    properties: dict[str, Any] = field(default_factory=dict)
    version: int = 1

    def __post_init__(self) -> None:
        if not self.template_id.strip() or not self.name.strip():
            raise ValueError("ID и имя шаблона мастерлога не могут быть пустыми")
        if len(self.name) > 200:
            raise ValueError("Имя шаблона мастерлога не должно превышать 200 символов")
        if isinstance(self.version, bool) or not isinstance(self.version, int):
            raise ValueError("Версия шаблона мастерлога должна быть целым числом")
        if self.version < 1:
            raise ValueError("Версия шаблона мастерлога должна быть положительной")


@dataclass(frozen=True, slots=True)
class CustomFormulaDefinition:
    formula_id: str
    name: str
    expression: str
    output_mnemonic: str
    output_unit: str
    description: str = ""
    version: int = 1


@dataclass(frozen=True, slots=True)
class ExportProfile:
    profile_id: str
    name: str
    curve_mnemonics: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.profile_id.strip() or not self.name.strip():
            raise ValueError("ID и имя профиля экспорта не могут быть пустыми")
        if len(self.name) > 100:
            raise ValueError("Имя профиля экспорта не должно превышать 100 символов")
        if not self.curve_mnemonics:
            raise ValueError("Профиль экспорта должен содержать хотя бы одну кривую")
        if any(not mnemonic.strip() for mnemonic in self.curve_mnemonics):
            raise ValueError("Мнемоники профиля экспорта не могут быть пустыми")
        if len(set(self.curve_mnemonics)) != len(self.curve_mnemonics):
            raise ValueError("Мнемоники профиля экспорта не должны повторяться")


@dataclass(frozen=True, slots=True)
class TimeDepthMappingProfile:
    profile_id: str
    name: str
    dataset_id: str
    time_index_id: str
    depth_index_id: str
    aggregation_policy: TimeDepthAggregationPolicy
    version: int = 1

    def __post_init__(self) -> None:
        identifiers = (self.profile_id, self.dataset_id, self.time_index_id, self.depth_index_id)
        if any(not value.strip() for value in identifiers) or not self.name.strip():
            raise ValueError("ID и имя TIME↔DEPTH профиля не могут быть пустыми")
        if len(self.name) > 100:
            raise ValueError("Имя TIME↔DEPTH профиля не должно превышать 100 символов")
        if isinstance(self.version, bool) or not isinstance(self.version, int) or self.version < 1:
            raise ValueError("Версия TIME↔DEPTH профиля должна быть положительным целым числом")


@dataclass(frozen=True, slots=True)
class ProjectLithotype:
    lithotype_id: str
    code: str
    name_ru: str
    name_en: str
    category: str
    color: str
    pattern_key: str
    name_kk: str = ""


@dataclass(slots=True)
class Well:
    well_id: str
    name: str
    datasets: dict[str, Dataset] = field(default_factory=dict)
    lithology: list[LithologyInterval] = field(default_factory=list)
    cuttings: list[CuttingsSample] = field(default_factory=list)
    stratigraphy: list[StratigraphyInterval] = field(default_factory=list)
    canvas_objects: list[CanvasObject] = field(default_factory=list)


@dataclass(slots=True)
class Project:
    project_id: str
    name: str
    wells: dict[str, Well] = field(default_factory=dict)
    lithotypes: dict[str, ProjectLithotype] = field(default_factory=dict)
    description_templates: dict[str, str] = field(default_factory=dict)
    masterlog_templates: dict[str, MasterlogTemplate] = field(default_factory=dict)
    custom_formulas: dict[str, CustomFormulaDefinition] = field(default_factory=dict)
    export_profiles: dict[str, ExportProfile] = field(default_factory=dict)
    time_depth_mapping_profiles: dict[str, TimeDepthMappingProfile] = field(default_factory=dict)
