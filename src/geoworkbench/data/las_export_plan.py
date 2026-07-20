from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

import numpy as np

from geoworkbench.data.lossless_las import LosslessLasDocument, section_role
from geoworkbench.domain.models import Dataset, DepthDomain, IndexRole, IndexType


class LasExportVersion(StrEnum):
    V1_2 = "1.2"
    V2_0 = "2.0"

    @property
    def writer_value(self) -> float:
        return float(self.value)


class ExportIssueSeverity(StrEnum):
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class LasExportPlan:
    version: LasExportVersion = LasExportVersion.V2_0
    wrap: bool = False
    null_value: float = -9999.25
    precision: int = 5
    preserve_custom_sections: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.version, LasExportVersion):
            raise ValueError("Версия экспорта LAS не поддерживается")
        if not isinstance(self.wrap, bool) or not isinstance(self.preserve_custom_sections, bool):
            raise ValueError("Параметры WRAP и сохранения секций должны быть логическими")
        if isinstance(self.null_value, bool) or not isinstance(
            self.null_value, (int, float, np.integer, np.floating)
        ):
            raise ValueError("NULL должен быть числом")
        if not isfinite(float(self.null_value)):
            raise ValueError("NULL должен быть конечным числом")
        if isinstance(self.precision, bool) or not isinstance(self.precision, int):
            raise ValueError("Точность LAS должна быть целым числом")
        if not 1 <= self.precision <= 15:
            raise ValueError("Точность LAS должна находиться в диапазоне 1–15")

    @property
    def number_format(self) -> str:
        return f"%.{self.precision}f"


@dataclass(frozen=True, slots=True)
class LasExportIssue:
    code: str
    severity: ExportIssueSeverity
    message: str


@dataclass(frozen=True, slots=True)
class LasExportLoss:
    field_id: str
    mnemonic: str
    index_type: IndexType
    role: IndexRole
    unit: str | None
    sample_count: int
    reason: str


@dataclass(frozen=True, slots=True)
class LasExportAnalysis:
    plan: LasExportPlan
    issues: tuple[LasExportIssue, ...]
    losses: tuple[LasExportLoss, ...] = ()

    @property
    def can_export(self) -> bool:
        return not any(issue.severity is ExportIssueSeverity.ERROR for issue in self.issues)

    @property
    def errors(self) -> tuple[LasExportIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity is ExportIssueSeverity.ERROR)

    @property
    def has_data_loss(self) -> bool:
        return bool(self.losses)


def analyze_las_export(
    dataset: Dataset,
    plan: LasExportPlan,
    source_document: LosslessLasDocument | None = None,
) -> LasExportAnalysis:
    issues: list[LasExportIssue] = []
    losses: list[LasExportLoss] = []
    if dataset.depth_domain is DepthDomain.TIME or dataset.active_index.role is IndexRole.TIME:
        issues.append(
            _error(
                "time-index-not-supported",
                "Временной индекс нельзя экспортировать как глубинный LAS без явного mapping",
            )
        )
    additional_indexes = [
        index for index_id, index in dataset.indexes.items() if index_id != dataset.active_index_id
    ]
    if additional_indexes:
        losses.extend(
            LasExportLoss(
                field_id=index.index_id,
                mnemonic=index.mnemonic,
                index_type=index.index_type,
                role=index.role,
                unit=index.unit,
                sample_count=int(index.values.size),
                reason="LAS 1.2/2.0 поддерживает одну индексную колонку",
            )
            for index in additional_indexes
        )
        details = "; ".join(
            f"{index.mnemonic} [id={index.index_id}, type={index.index_type.value}, "
            f"role={index.role.value}, unit={index.unit or '—'}]"
            for index in additional_indexes
        )
        issues.append(
            _warning(
                "additional-indexes-omitted",
                "LAS сохранит только активную индексную колонку; будут потеряны: "
                + details
                + ". Для сохранения всех индексов используйте JSON или Parquet.",
            )
        )
    if dataset.depth.ndim != 1 or dataset.depth.size == 0:
        issues.append(
            _error("invalid-index", "Индекс LAS должен быть непустым одномерным массивом")
        )
    elif not np.all(np.isfinite(dataset.depth)):
        issues.append(_error("non-finite-index", "Индекс LAS содержит NaN или бесконечность"))

    arrays = [("индексе", dataset.depth)] + [
        (curve.metadata.original_mnemonic, curve.values) for curve in dataset.curves.values()
    ]
    collisions = [name for name, values in arrays if np.any(values == plan.null_value)]
    if collisions:
        issues.append(
            _error(
                "null-collision",
                "NULL совпадает с реальными значениями: " + ", ".join(collisions),
            )
        )
    infinite_curves = [
        curve.metadata.original_mnemonic
        for curve in dataset.curves.values()
        if np.any(np.isinf(curve.values))
    ]
    if infinite_curves:
        issues.append(
            _error(
                "infinite-curve-values",
                "Кривые содержат бесконечные значения: " + ", ".join(infinite_curves),
            )
        )
    missing_curves = [
        curve.metadata.original_mnemonic
        for curve in dataset.curves.values()
        if np.any(np.isnan(curve.values))
    ]
    if missing_curves:
        issues.append(
            _warning(
                "missing-values-substituted",
                f"NaN будут записаны как NULL ({plan.null_value:g}): " + ", ".join(missing_curves),
            )
        )

    if plan.preserve_custom_sections and source_document is not None:
        roles = [
            role
            for section in source_document.sections
            if (role := section_role(section.name)) is not None
        ]
        counts = Counter(roles)
        repeated = sorted(role for role, count in counts.items() if count > 1)
        if repeated:
            issues.append(
                _error(
                    "ambiguous-source-sections",
                    "Неоднозначные стандартные секции источника: " + ", ".join(repeated),
                )
            )
        missing = {"version", "well", "curve", "ascii"} - set(roles)
        if missing:
            issues.append(
                _error(
                    "missing-source-sections",
                    "Для lossless-экспорта отсутствуют секции: " + ", ".join(sorted(missing)),
                )
            )
    if plan.version is LasExportVersion.V1_2:
        issues.append(
            _warning(
                "legacy-version",
                "LAS 1.2 выбран для совместимости; возможности LAS 2.0 в нём недоступны",
            )
        )
    return LasExportAnalysis(plan, tuple(issues), tuple(losses))


def _warning(code: str, message: str) -> LasExportIssue:
    return LasExportIssue(code, ExportIssueSeverity.WARNING, message)


def _error(code: str, message: str) -> LasExportIssue:
    return LasExportIssue(code, ExportIssueSeverity.ERROR, message)
