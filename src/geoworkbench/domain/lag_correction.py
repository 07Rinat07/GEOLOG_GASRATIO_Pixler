from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from typing import TypeAlias

from geoworkbench.domain.acquisition import canonical_acquisition_timestamp
from geoworkbench.domain.models import TimeDepthAggregationPolicy


LAG_CORRECTION_SCHEMA_VERSION = 1
LAG_CORRECTION_FORMULA_ID = "geoworkbench.lag_depth"
LAG_CORRECTION_FORMULA_VERSION = 1


class LagCorrectionTarget(StrEnum):
    GAS = "gas"
    CUTTINGS = "cuttings"
    GENERIC = "generic"


class LagCorrectionMethod(StrEnum):
    CONSTANT_TIME = "constant_time"
    ANNULAR_VOLUME_FLOW = "annular_volume_flow"
    PUMP_STROKES = "pump_strokes"
    CONTROL_POINTS = "control_points"


class LagCorrectionAxisMode(StrEnum):
    SOURCE = "source"
    CORRECTED = "corrected"


@dataclass(frozen=True, slots=True)
class ConstantTimeLagParameters:
    lag_seconds: float

    def __post_init__(self) -> None:
        _positive_number(self.lag_seconds, "lag_seconds", allow_zero=True)


@dataclass(frozen=True, slots=True)
class AnnularVolumeFlowLagParameters:
    annular_volume_m3: float
    flow_rate_m3_per_s: float

    def __post_init__(self) -> None:
        _positive_number(self.annular_volume_m3, "annular_volume_m3")
        _positive_number(self.flow_rate_m3_per_s, "flow_rate_m3_per_s")


@dataclass(frozen=True, slots=True)
class PumpStrokeLagParameters:
    annular_volume_m3: float
    pump_output_m3_per_stroke: float
    strokes_per_minute: float

    def __post_init__(self) -> None:
        _positive_number(self.annular_volume_m3, "annular_volume_m3")
        _positive_number(self.pump_output_m3_per_stroke, "pump_output_m3_per_stroke")
        _positive_number(self.strokes_per_minute, "strokes_per_minute")


@dataclass(frozen=True, slots=True)
class LagDepthControlPoint:
    row: int
    corrected_depth_m: float

    def __post_init__(self) -> None:
        if isinstance(self.row, bool) or not isinstance(self.row, int) or self.row < 0:
            raise ValueError("row контрольной точки должен быть неотрицательным целым числом")
        _finite_number(self.corrected_depth_m, "corrected_depth_m")


@dataclass(frozen=True, slots=True)
class ControlPointLagParameters:
    points: tuple[LagDepthControlPoint, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.points, tuple) or len(self.points) < 2:
            raise ValueError("Ручная lag correction требует минимум две контрольные точки")
        if not all(isinstance(item, LagDepthControlPoint) for item in self.points):
            raise ValueError("points должен содержать LagDepthControlPoint")
        rows = [item.row for item in self.points]
        if rows != sorted(rows) or len(rows) != len(set(rows)):
            raise ValueError("Контрольные точки должны иметь уникальные возрастающие row")


LagCorrectionParameters: TypeAlias = (
    ConstantTimeLagParameters
    | AnnularVolumeFlowLagParameters
    | PumpStrokeLagParameters
    | ControlPointLagParameters
)

_PARAMETER_TYPE_BY_METHOD: dict[LagCorrectionMethod, type[LagCorrectionParameters]] = {
    LagCorrectionMethod.CONSTANT_TIME: ConstantTimeLagParameters,
    LagCorrectionMethod.ANNULAR_VOLUME_FLOW: AnnularVolumeFlowLagParameters,
    LagCorrectionMethod.PUMP_STROKES: PumpStrokeLagParameters,
    LagCorrectionMethod.CONTROL_POINTS: ControlPointLagParameters,
}


@dataclass(frozen=True, slots=True)
class LagCorrectionRevision:
    revision: int
    method: LagCorrectionMethod
    parameters: LagCorrectionParameters
    source_time_index_id: str | None
    source_depth_index_id: str
    target_curve_ids: tuple[str, ...]
    aggregation_policy: TimeDepthAggregationPolicy
    output_dataset_id: str
    output_source_index_id: str
    output_index_id: str
    source_row_count: int
    source_fingerprint: str
    output_dataset_digest: str
    source_sequence: int | None
    source_audit_digest: str | None
    formula_id: str
    formula_version: int
    created_at: str
    created_by: str
    comment: str = ""
    schema_version: int = LAG_CORRECTION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != LAG_CORRECTION_SCHEMA_VERSION:
            raise ValueError("Неподдерживаемая версия lag correction revision schema")
        if (
            isinstance(self.revision, bool)
            or not isinstance(self.revision, int)
            or self.revision < 1
        ):
            raise ValueError("revision lag correction должна быть положительным целым числом")
        if not isinstance(self.method, LagCorrectionMethod):
            raise ValueError("method должен использовать LagCorrectionMethod")
        expected_type = _PARAMETER_TYPE_BY_METHOD[self.method]
        if not isinstance(self.parameters, expected_type):
            raise ValueError("Параметры lag correction не соответствуют method")
        if self.method is LagCorrectionMethod.CONTROL_POINTS:
            if self.source_time_index_id is not None:
                raise ValueError("Ручная correction по row не использует source_time_index_id")
        else:
            _required_text(self.source_time_index_id, "source_time_index_id")
        for value, name in (
            (self.source_depth_index_id, "source_depth_index_id"),
            (self.output_dataset_id, "output_dataset_id"),
            (self.output_source_index_id, "output_source_index_id"),
            (self.output_index_id, "output_index_id"),
            (self.formula_id, "formula_id"),
            (self.created_by, "created_by"),
        ):
            _required_text(value, name)
        if self.output_source_index_id == self.output_index_id:
            raise ValueError("Исходный и скорректированный output index должны различаться")
        if not isinstance(self.target_curve_ids, tuple) or not self.target_curve_ids:
            raise ValueError("target_curve_ids должен содержать хотя бы одну кривую")
        if not all(isinstance(item, str) and item.strip() for item in self.target_curve_ids):
            raise ValueError("target_curve_ids должен содержать непустые строки")
        if len(set(self.target_curve_ids)) != len(self.target_curve_ids):
            raise ValueError("target_curve_ids не должны повторяться")
        if not isinstance(self.aggregation_policy, TimeDepthAggregationPolicy):
            raise ValueError("aggregation_policy имеет неверный тип")
        if (
            isinstance(self.source_row_count, bool)
            or not isinstance(self.source_row_count, int)
            or self.source_row_count < 1
        ):
            raise ValueError("source_row_count должен быть положительным целым числом")
        _digest(self.source_fingerprint, "source_fingerprint")
        _digest(self.output_dataset_digest, "output_dataset_digest")
        if (self.source_sequence is None) != (self.source_audit_digest is None):
            raise ValueError("source_sequence и source_audit_digest задаются только вместе")
        if self.source_sequence is not None:
            if (
                isinstance(self.source_sequence, bool)
                or not isinstance(self.source_sequence, int)
                or self.source_sequence < 0
            ):
                raise ValueError("source_sequence должен быть неотрицательным целым числом")
            _digest(self.source_audit_digest, "source_audit_digest")
        if (
            isinstance(self.formula_version, bool)
            or not isinstance(self.formula_version, int)
            or self.formula_version < 1
        ):
            raise ValueError("formula_version должна быть положительным целым числом")
        object.__setattr__(self, "created_at", canonical_acquisition_timestamp(self.created_at))
        if not isinstance(self.comment, str):
            raise ValueError("comment должен быть строкой")


@dataclass(frozen=True, slots=True)
class LagCorrectionProfile:
    profile_id: str
    well_id: str
    name: str
    target: LagCorrectionTarget
    source_dataset_id: str
    revisions: tuple[LagCorrectionRevision, ...]
    active_revision: int
    schema_version: int = LAG_CORRECTION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != LAG_CORRECTION_SCHEMA_VERSION:
            raise ValueError("Неподдерживаемая версия lag correction profile schema")
        for value, name in (
            (self.profile_id, "profile_id"),
            (self.well_id, "well_id"),
            (self.name, "name"),
            (self.source_dataset_id, "source_dataset_id"),
        ):
            _required_text(value, name)
        if len(self.name.strip()) > 120:
            raise ValueError("Имя lag correction профиля не должно превышать 120 символов")
        if not isinstance(self.target, LagCorrectionTarget):
            raise ValueError("target должен использовать LagCorrectionTarget")
        if not isinstance(self.revisions, tuple) or not self.revisions:
            raise ValueError("Lag correction профиль требует хотя бы одну revision")
        if not all(isinstance(item, LagCorrectionRevision) for item in self.revisions):
            raise ValueError("revisions должен содержать LagCorrectionRevision")
        numbers = [item.revision for item in self.revisions]
        if numbers != list(range(1, len(self.revisions) + 1)):
            raise ValueError("Lag correction revisions должны быть непрерывными от 1")
        if self.active_revision not in set(numbers):
            raise ValueError("active_revision отсутствует в revisions")
        output_ids = [item.output_dataset_id for item in self.revisions]
        if len(output_ids) != len(set(output_ids)):
            raise ValueError("Каждая revision должна иметь отдельный output dataset")

    @property
    def latest_revision(self) -> int:
        return len(self.revisions)

    def revision_by_number(self, revision: int) -> LagCorrectionRevision:
        if isinstance(revision, bool) or not isinstance(revision, int):
            raise KeyError(f"Неизвестная lag correction revision: {revision}")
        if revision < 1 or revision > len(self.revisions):
            raise KeyError(f"Неизвестная lag correction revision: {revision}")
        return self.revisions[revision - 1]

    @property
    def active(self) -> LagCorrectionRevision:
        return self.revision_by_number(self.active_revision)


def lag_seconds(parameters: LagCorrectionParameters) -> float | None:
    if isinstance(parameters, ConstantTimeLagParameters):
        return float(parameters.lag_seconds)
    if isinstance(parameters, AnnularVolumeFlowLagParameters):
        return float(parameters.annular_volume_m3 / parameters.flow_rate_m3_per_s)
    if isinstance(parameters, PumpStrokeLagParameters):
        strokes = parameters.annular_volume_m3 / parameters.pump_output_m3_per_stroke
        return float(strokes / parameters.strokes_per_minute * 60.0)
    if isinstance(parameters, ControlPointLagParameters):
        return None
    raise TypeError("Неизвестные параметры lag correction")


def _required_text(value: object, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} должен быть непустой строкой")


def _finite_number(value: object, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} должен быть числом")
    if not isfinite(float(value)):
        raise ValueError(f"{name} должен быть конечным")


def _positive_number(value: object, name: str, *, allow_zero: bool = False) -> None:
    _finite_number(value, name)
    minimum_ok = float(value) >= 0.0 if allow_zero else float(value) > 0.0
    if not minimum_ok:
        qualifier = "неотрицательным" if allow_zero else "положительным"
        raise ValueError(f"{name} должен быть {qualifier}")


def _digest(value: object, name: str) -> None:
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError(f"{name} должен быть SHA-256 hex digest")
    try:
        int(value, 16)
    except ValueError as exc:
        raise ValueError(f"{name} должен быть SHA-256 hex digest") from exc
