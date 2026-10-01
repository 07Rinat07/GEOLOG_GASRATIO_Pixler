from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
from math import isfinite
from typing import Any, Mapping

from geoworkbench.project.lithotype_catalog_controller import LithotypeCatalogController
from geoworkbench.project.lithotype_catalog_models import CatalogLithotype
from geoworkbench.project.session import ProjectSession


@dataclass(frozen=True, slots=True)
class ReportGeologyComponent:
    lithotype_id: str
    percentage: float


@dataclass(frozen=True, slots=True)
class ReportGeologyInterval:
    interval_id: str
    top_depth: float
    bottom_depth: float
    lithotype_id: str
    description: str | None
    description_i18n: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class ReportCuttingsSample:
    sample_id: str
    top_depth: float
    bottom_depth: float
    components: tuple[ReportGeologyComponent, ...]
    lba_group: int | None
    lba_type_id: str | None
    lba_intensity: int | None
    lba_color: str | None
    lba_distribution: str | None
    lba_cut: str | None
    lba_cut_speed: str | None
    lba_cut_color: str | None
    lba_residue_type: str | None
    lba_residue_color: str | None
    lba_odour: str | None
    lba_stain: str | None
    lba_description: str | None
    calcite_percent: float | None
    dolomite_percent: float | None
    total_carbonate_percent: float | None
    description: str | None
    analysis_interpretation: str | None
    description_i18n: tuple[tuple[str, str], ...]
    lba_description_i18n: tuple[tuple[str, str], ...]
    analysis_interpretation_i18n: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class ReportGeologySnapshot:
    well_id: str
    lithology: tuple[ReportGeologyInterval, ...]
    cuttings: tuple[ReportCuttingsSample, ...]
    lithotypes: tuple[CatalogLithotype, ...]
    geology_sha256: str = ""

    @property
    def has_data(self) -> bool:
        return bool(self.lithology or self.cuttings)

    def payload(self, *, include_digest: bool = True) -> dict[str, Any]:
        payload = asdict(self)
        if not include_digest:
            payload.pop("geology_sha256", None)
        return payload

    def canonical_json(self, *, include_digest: bool = True) -> str:
        return json.dumps(
            self.payload(include_digest=include_digest),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    def verify(self) -> bool:
        return bool(self.geology_sha256) and self.geology_sha256 == _snapshot_digest(self)


def build_report_geology_snapshot(
    session: ProjectSession,
    *,
    interval: tuple[float, float] | None = None,
) -> ReportGeologySnapshot:
    """Freeze current project geology for deterministic report rendering.

    LAS geology is already materialized into the project model by import_las_geology().
    This builder reads only that project state and never reparses or mutates source LAS.
    """

    well = session.current_well
    if well is None:
        raise ValueError("Для геологического снимка требуется выбранная скважина")

    normalized_interval = _normalized_interval(interval)
    lithology = tuple(
        sorted(
            (
                ReportGeologyInterval(
                    interval_id=str(item.interval_id),
                    top_depth=min(float(item.top_depth), float(item.bottom_depth)),
                    bottom_depth=max(float(item.top_depth), float(item.bottom_depth)),
                    lithotype_id=str(item.lithotype_id),
                    description=_optional_text(item.description),
                    description_i18n=_i18n_items(item.description_i18n),
                )
                for item in well.lithology
                if _valid_depth_interval(item.top_depth, item.bottom_depth)
                and _overlaps(item.top_depth, item.bottom_depth, normalized_interval)
            ),
            key=lambda item: (item.top_depth, item.bottom_depth, item.interval_id),
        )
    )
    cuttings = tuple(
        sorted(
            (
                ReportCuttingsSample(
                    sample_id=str(sample.sample_id),
                    top_depth=min(float(sample.top_depth), float(sample.bottom_depth)),
                    bottom_depth=max(float(sample.top_depth), float(sample.bottom_depth)),
                    components=tuple(
                        ReportGeologyComponent(
                            lithotype_id=str(component.lithotype_id),
                            percentage=float(component.percentage),
                        )
                        for component in sample.components
                        if isfinite(float(component.percentage))
                    ),
                    lba_group=sample.lba_group,
                    lba_type_id=_optional_text(sample.lba_type_id),
                    lba_intensity=sample.lba_intensity,
                    lba_color=_optional_text(sample.lba_color),
                    lba_distribution=_optional_text(sample.lba_distribution),
                    lba_cut=_optional_text(sample.lba_cut),
                    lba_cut_speed=_optional_text(sample.lba_cut_speed),
                    lba_cut_color=_optional_text(sample.lba_cut_color),
                    lba_residue_type=_optional_text(sample.lba_residue_type),
                    lba_residue_color=_optional_text(sample.lba_residue_color),
                    lba_odour=_optional_text(sample.lba_odour),
                    lba_stain=_optional_text(sample.lba_stain),
                    lba_description=_optional_text(sample.lba_description),
                    calcite_percent=_optional_float(sample.calcite_percent),
                    dolomite_percent=_optional_float(sample.dolomite_percent),
                    total_carbonate_percent=_optional_float(sample.total_carbonate_percent),
                    description=_optional_text(sample.description),
                    analysis_interpretation=_optional_text(sample.analysis_interpretation),
                    description_i18n=_i18n_items(sample.description_i18n),
                    lba_description_i18n=_i18n_items(sample.lba_description_i18n),
                    analysis_interpretation_i18n=_i18n_items(
                        sample.analysis_interpretation_i18n
                    ),
                )
                for sample in well.cuttings
                if _valid_depth_interval(sample.top_depth, sample.bottom_depth)
                and _overlaps(sample.top_depth, sample.bottom_depth, normalized_interval)
            ),
            key=lambda item: (item.top_depth, item.bottom_depth, item.sample_id),
        )
    )

    used_lithotype_ids = {item.lithotype_id for item in lithology} | {
        component.lithotype_id
        for sample in cuttings
        for component in sample.components
    }
    catalog_by_id = {
        item.lithotype_id: item
        for item in LithotypeCatalogController(session).available()
    }
    lithotypes = tuple(
        catalog_by_id[lithotype_id]
        for lithotype_id in sorted(used_lithotype_ids)
        if lithotype_id in catalog_by_id
    )

    unsigned = ReportGeologySnapshot(
        well_id=well.well_id,
        lithology=lithology,
        cuttings=cuttings,
        lithotypes=lithotypes,
    )
    return replace(unsigned, geology_sha256=_snapshot_digest(unsigned))


def _snapshot_digest(snapshot: ReportGeologySnapshot) -> str:
    payload = snapshot.canonical_json(include_digest=False).encode("utf-8")
    return sha256(payload).hexdigest()


def _normalized_interval(
    interval: tuple[float, float] | None,
) -> tuple[float, float] | None:
    if interval is None:
        return None
    first, second = (float(interval[0]), float(interval[1]))
    if not isfinite(first) or not isfinite(second):
        raise ValueError("Интервал геологического снимка должен быть конечным")
    low, high = sorted((first, second))
    if low == high:
        raise ValueError("Интервал геологического снимка должен иметь ненулевую мощность")
    return low, high


def _valid_depth_interval(top: float, bottom: float) -> bool:
    top_value = float(top)
    bottom_value = float(bottom)
    return isfinite(top_value) and isfinite(bottom_value) and top_value != bottom_value


def _overlaps(
    top: float,
    bottom: float,
    interval: tuple[float, float] | None,
) -> bool:
    if interval is None:
        return True
    low, high = sorted((float(top), float(bottom)))
    return high >= interval[0] and low <= interval[1]


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _optional_float(value: float | None) -> float | None:
    if value is None:
        return None
    converted = float(value)
    return converted if isfinite(converted) else None


def _i18n_items(mapping: Mapping[str, str]) -> tuple[tuple[str, str], ...]:
    return tuple(
        sorted(
            (str(key).strip(), str(value).strip())
            for key, value in mapping.items()
            if str(key).strip() and str(value).strip()
        )
    )


__all__ = [
    "ReportCuttingsSample",
    "ReportGeologyComponent",
    "ReportGeologyInterval",
    "ReportGeologySnapshot",
    "build_report_geology_snapshot",
]
