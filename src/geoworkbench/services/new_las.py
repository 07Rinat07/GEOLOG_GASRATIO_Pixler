from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

import numpy as np

from geoworkbench.data.las_export_plan import LasExportVersion
from geoworkbench.domain.models import (
    Dataset,
    DatasetIndex,
    DatasetKind,
    DepthDomain,
    IndexRole,
    IndexType,
    new_id,
)
from geoworkbench.services.depth_axis import build_depth_grid


@dataclass(frozen=True, slots=True)
class NewLasPlan:
    name: str
    version: LasExportVersion
    index_type: IndexType
    start: float
    stop: float
    step: float
    null_value: float = -9999.25

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Название dataset не может быть пустым")
        if not isinstance(self.version, LasExportVersion):
            raise ValueError("Версия LAS не поддерживается")
        if self.index_type not in {IndexType.MD, IndexType.TVD, IndexType.TVDSS}:
            raise ValueError("Новый LAS поддерживает индексы MD, TVD и TVDSS")
        numeric = (self.start, self.stop, self.step, self.null_value)
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in numeric):
            raise ValueError("Границы, шаг и NULL должны быть числами")
        if not isfinite(self.null_value):
            raise ValueError("NULL должен быть конечным числом")
        grid = build_depth_grid(self.start, self.stop, self.step)
        if np.any(grid == self.null_value):
            raise ValueError("NULL совпадает со значением глубинного индекса")

    @property
    def sample_count(self) -> int:
        return int(build_depth_grid(self.start, self.stop, self.step).size)


def create_empty_las_dataset(plan: NewLasPlan) -> Dataset:
    depth = build_depth_grid(plan.start, plan.stop, plan.step)
    dataset_id = new_id()
    index_id = f"{dataset_id}:primary-index"
    depth_domain = DepthDomain(plan.index_type.value)
    index = DatasetIndex(
        index_id=index_id,
        mnemonic=plan.index_type.value.upper(),
        index_type=plan.index_type,
        role=IndexRole.DEPTH,
        unit="m",
        values=depth,
        evidence=("user-created-las",),
    )
    return Dataset(
        dataset_id=dataset_id,
        name=plan.name.strip(),
        kind=DatasetKind.USER,
        depth_domain=depth_domain,
        depth=depth,
        headers={
            "WELL": plan.name.strip(),
            "STRT": f"{depth[0]:.15g}",
            "STOP": f"{depth[-1]:.15g}",
            "STEP": f"{plan.step:.15g}",
            "NULL": f"{plan.null_value:.15g}",
        },
        indexes={index_id: index},
        active_index_id=index_id,
        version_headers={"VERS": plan.version.value, "WRAP": "NO"},
    )
