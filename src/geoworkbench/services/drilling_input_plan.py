from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Iterable, Mapping

import numpy as np

from geoworkbench.catalogs.sensors import SensorCatalog, normalize_unit
from geoworkbench.domain.models import CurveData, CurveMetadata, Dataset
from geoworkbench.services.las_parameter_resolver import (
    DatasetParameterResolution,
    LasParameterResolver,
    ParameterMatch,
    ParameterResolutionError,
)
from geoworkbench.services.uom_dictionary import UomDictionary, default_uom_dictionary


class InputSourceMode(StrEnum):
    AUTO = "auto"
    CURVE = "curve"
    CONSTANT = "constant"
    SECTIONS = "sections"


@dataclass(frozen=True, slots=True)
class ParameterSource:
    mode: InputSourceMode = InputSourceMode.AUTO
    curve_id: str | None = None
    value: float | None = None
    unit: str = ""

    def validate(self, canonical: str) -> None:
        if self.mode is InputSourceMode.CURVE and not self.curve_id:
            raise ValueError(f"Для {canonical} не выбрана кривая")
        if self.mode is InputSourceMode.CONSTANT:
            if self.value is None or not np.isfinite(self.value) or self.value <= 0.0:
                raise ValueError(f"Постоянное значение {canonical} должно быть больше нуля")
            if not self.unit.strip():
                raise ValueError(f"Для постоянного значения {canonical} не указана единица")


@dataclass(frozen=True, slots=True)
class DepthValueSection:
    top_md: float
    bottom_md: float
    value: float
    unit: str = "mm"
    comment: str = ""

    def validate(self) -> None:
        values = (self.top_md, self.bottom_md, self.value)
        if not all(np.isfinite(item) for item in values):
            raise ValueError("Границы и значение секции должны быть конечными числами")
        if self.bottom_md <= self.top_md:
            raise ValueError(
                f"Нижняя граница секции {self.bottom_md:g} должна быть больше верхней "
                f"{self.top_md:g}"
            )
        if self.value <= 0.0:
            raise ValueError("Диаметр секции должен быть больше нуля")
        if not self.unit.strip():
            raise ValueError("Для диаметра секции не указана единица")


@dataclass(frozen=True, slots=True)
class DrillingInputPlan:
    """Explicit drilling inputs shared by normalized-gas and d-exponent calculations."""

    rop: ParameterSource = field(default_factory=ParameterSource)
    flow: ParameterSource = field(default_factory=ParameterSource)
    rpm: ParameterSource = field(default_factory=ParameterSource)
    wob: ParameterSource = field(default_factory=ParameterSource)
    mud_density: ParameterSource = field(default_factory=ParameterSource)
    bit: ParameterSource = field(default_factory=ParameterSource)
    bit_sections: tuple[DepthValueSection, ...] = ()

    def source_for(self, canonical: str) -> ParameterSource:
        key = canonical.strip().upper()
        return {
            "ROP": self.rop,
            "FLOW_IN": self.flow,
            "FLOW_OUT": self.flow,
            "RPM": self.rpm,
            "WOB": self.wob,
            "MW_IN": self.mud_density,
            "MW_OUT": self.mud_density,
            "BIT": self.bit,
        }.get(key, ParameterSource())

    def validate(self) -> None:
        for canonical, source in (
            ("ROP", self.rop),
            ("FLOW", self.flow),
            ("RPM", self.rpm),
            ("WOB", self.wob),
            ("MW", self.mud_density),
            ("BIT", self.bit),
        ):
            source.validate(canonical)
        if self.bit.mode is InputSourceMode.SECTIONS:
            if not self.bit_sections:
                raise ValueError("Добавьте хотя бы одну секцию диаметра ствола")
            for section in self.bit_sections:
                section.validate()


class DrillingInputResolver(LasParameterResolver):
    """Resolver that collapses exact duplicates and applies explicit field inputs."""

    def __init__(
        self,
        catalog: SensorCatalog | None = None,
        *,
        plan: DrillingInputPlan | None = None,
        uom: UomDictionary | None = None,
    ) -> None:
        super().__init__(catalog)
        self.plan = plan or DrillingInputPlan()
        self.uom = uom or default_uom_dictionary()

    def set_plan(self, plan: DrillingInputPlan) -> None:
        plan.validate()
        self.plan = plan

    def resolve_dataset(
        self,
        dataset: Dataset,
        *,
        targets: Iterable[str] | None = None,
        user_mappings: Mapping[str, str] | None = None,
        minimum_confidence: float = 0.65,
    ) -> DatasetParameterResolution:
        base = super().resolve_dataset(
            dataset,
            targets=targets,
            user_mappings=user_mappings,
            minimum_confidence=minimum_confidence,
        )
        matches = dict(base.matches)
        ambiguities = dict(base.ambiguities)

        for canonical, candidates in tuple(ambiguities.items()):
            selected = _collapse_equivalent_duplicates(canonical, candidates)
            if selected is not None:
                matches[canonical] = selected
                ambiguities.pop(canonical, None)

        target_set = {item.strip().upper() for item in targets or () if item.strip()}
        plan_targets = target_set or {
            "ROP",
            "FLOW_IN",
            "FLOW_OUT",
            "RPM",
            "WOB",
            "MW_IN",
            "MW_OUT",
            "BIT",
        }
        for canonical in plan_targets:
            source = self.plan.source_for(canonical)
            if source.mode is InputSourceMode.AUTO:
                continue
            match = self._planned_match(dataset, canonical, source)
            matches[canonical] = match
            ambiguities.pop(canonical, None)

        return DatasetParameterResolution(
            MappingProxyType(matches),
            MappingProxyType(ambiguities),
            base.unresolved_curve_ids,
        )

    def _planned_match(
        self,
        dataset: Dataset,
        canonical: str,
        source: ParameterSource,
    ) -> ParameterMatch:
        source.validate(canonical)
        if source.mode is InputSourceMode.CURVE:
            curve = dataset.curves.get(source.curve_id or "")
            if curve is None:
                raise ParameterResolutionError(
                    f"Выбранная кривая для {canonical} больше не существует",
                    code="missing",
                    values={"parameter": canonical},
                )
            return ParameterMatch(
                canonical,
                curve,
                1.0,
                "user_mapping",
                (f"явно выбрана кривая {curve.metadata.original_mnemonic}",),
            )

        if canonical == "BIT" and source.mode is InputSourceMode.SECTIONS:
            values = build_section_values(
                dataset.depth,
                self.plan.bit_sections,
                target_unit="in",
                uom=self.uom,
            )
            return _synthetic_match(
                dataset,
                canonical,
                values,
                "in",
                "BIT_SECTIONS",
                "интервальная таблица фактического диаметра ствола",
            )

        if source.mode is InputSourceMode.CONSTANT:
            values = np.full(dataset.depth.shape, float(source.value), dtype=np.float64)
            return _synthetic_match(
                dataset,
                canonical,
                values,
                source.unit,
                f"{canonical}_MANUAL",
                "постоянное ручное значение",
            )

        raise ParameterResolutionError(
            f"Неподдерживаемый источник {canonical}: {source.mode}",
            code="generic",
        )


def build_section_values(
    depth: np.ndarray,
    sections: Iterable[DepthValueSection],
    *,
    target_unit: str,
    uom: UomDictionary | None = None,
) -> np.ndarray:
    """Build one depth-aligned array from non-overlapping field sections."""

    dictionary = uom or default_uom_dictionary()
    axis = np.asarray(depth, dtype=np.float64)
    if axis.ndim != 1:
        raise ValueError("Глубинная ось должна быть одномерной")
    finite_depth = np.isfinite(axis)
    if not np.any(finite_depth):
        raise ValueError("В наборе нет корректных глубин для секций")

    rows = tuple(sorted(sections, key=lambda item: (item.top_md, item.bottom_md)))
    if not rows:
        raise ValueError("Таблица секций пуста")
    for row in rows:
        row.validate()
    for previous, current in zip(rows, rows[1:], strict=False):
        if current.top_md < previous.bottom_md:
            raise ValueError(
                f"Секции {previous.top_md:g}–{previous.bottom_md:g} и "
                f"{current.top_md:g}–{current.bottom_md:g} перекрываются"
            )

    result = np.full(axis.shape, np.nan, dtype=np.float64)
    hit_count = np.zeros(axis.shape, dtype=np.int16)
    for index, row in enumerate(rows):
        upper_inclusive = index == len(rows) - 1
        mask = finite_depth & (axis >= row.top_md)
        mask &= axis <= row.bottom_md if upper_inclusive else axis < row.bottom_md
        conversion = dictionary.conversion(row.unit, target_unit)
        if conversion is None:
            raise ValueError(
                f"Нельзя преобразовать диаметр секции из {row.unit or 'неизвестной единицы'} "
                f"в {target_unit}"
            )
        result[mask] = conversion.convert_scalar(row.value)
        hit_count[mask] += 1

    if np.any(hit_count > 1):
        raise ValueError("Интервалы секций перекрываются на глубинной оси")
    missing = finite_depth & (hit_count == 0)
    if np.any(missing):
        missing_depth = axis[missing]
        raise ValueError(
            "Таблица секций не покрывает глубины "
            f"{float(np.nanmin(missing_depth)):g}–{float(np.nanmax(missing_depth)):g}"
        )
    return result


def candidate_curves(
    dataset: Dataset,
    canonical: str,
    *,
    resolver: LasParameterResolver | None = None,
    minimum_confidence: float = 0.65,
) -> tuple[ParameterMatch, ...]:
    """Return all plausible source curves for an explicit user selector."""

    service = resolver or LasParameterResolver()
    result: list[ParameterMatch] = []
    for curve in dataset.curves.values():
        match = next(
            (
                item
                for item in service.infer_curve(curve)
                if item.canonical_mnemonic == canonical and item.confidence >= minimum_confidence
            ),
            None,
        )
        if match is not None:
            result.append(match)
    return tuple(
        sorted(
            result,
            key=lambda item: (
                -item.confidence,
                _technology_copy_penalty(item.source_mnemonic),
                len(item.source_mnemonic),
                item.source_mnemonic.casefold(),
            ),
        )
    )


def _collapse_equivalent_duplicates(
    canonical: str,
    candidates: tuple[ParameterMatch, ...],
) -> ParameterMatch | None:
    if len(candidates) < 2:
        return candidates[0] if candidates else None
    reference = candidates[0]
    reference_unit = normalize_unit(reference.unit)
    reference_values = np.asarray(reference.curve.values, dtype=np.float64)
    for candidate in candidates[1:]:
        if normalize_unit(candidate.unit) != reference_unit:
            return None
        values = np.asarray(candidate.curve.values, dtype=np.float64)
        if values.shape != reference_values.shape:
            return None
        if not np.array_equal(np.isfinite(values), np.isfinite(reference_values)):
            return None
        finite = np.isfinite(values) & np.isfinite(reference_values)
        if np.any(finite) and not np.allclose(
            values[finite],
            reference_values[finite],
            rtol=1.0e-9,
            atol=1.0e-12,
        ):
            return None

    selected = min(
        candidates,
        key=lambda item: (
            _technology_copy_penalty(item.source_mnemonic),
            len(item.source_mnemonic),
            item.source_mnemonic.casefold(),
            item.curve_id,
        ),
    )
    aliases = ", ".join(item.source_mnemonic for item in candidates)
    return ParameterMatch(
        canonical,
        selected.curve,
        selected.confidence,
        "equivalent_duplicate",
        (*selected.evidence, f"идентичные дубли автоматически объединены: {aliases}"),
    )


def _technology_copy_penalty(mnemonic: str) -> int:
    value = mnemonic.upper()
    markers = ("TEHNOLOGIYA", "TECHNOLOGY", "TECHNOLOG", "_COPY", "_DUP")
    return 1 if any(marker in value for marker in markers) else 0


def _synthetic_match(
    dataset: Dataset,
    canonical: str,
    values: np.ndarray,
    unit: str,
    mnemonic: str,
    evidence: str,
) -> ParameterMatch:
    curve = CurveData(
        CurveMetadata(
            curve_id=f"manual:{dataset.dataset_id}:{canonical}",
            original_mnemonic=mnemonic,
            canonical_mnemonic=canonical,
            unit=unit,
            description=evidence,
            source_dataset_id=dataset.dataset_id,
            provenance="manual:drilling-input-plan",
        ),
        np.asarray(values, dtype=np.float64),
    )
    return ParameterMatch(canonical, curve, 1.0, "manual_input", (evidence,))


__all__ = [
    "DepthValueSection",
    "DrillingInputPlan",
    "DrillingInputResolver",
    "InputSourceMode",
    "ParameterSource",
    "build_section_values",
    "candidate_curves",
]
