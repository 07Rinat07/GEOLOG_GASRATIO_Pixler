from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
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
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ProjectLithotype:
    lithotype_id: str
    code: str
    name_ru: str
    name_en: str
    category: str
    color: str
    pattern_key: str


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
