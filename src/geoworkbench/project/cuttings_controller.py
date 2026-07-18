from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from geoworkbench.domain.models import CuttingsComponent, CuttingsSample, Well, new_id
from geoworkbench.project.session import ProjectSession


@dataclass(slots=True)
class CuttingsController:
    session: ProjectSession

    def add(
        self,
        top_depth: float,
        bottom_depth: float,
        components: dict[str, float],
        *,
        description: str | None = None,
    ) -> CuttingsSample:
        top, bottom = self._validate_interval(top_depth, bottom_depth)
        normalized = self._validate_components(components)
        self._ensure_no_overlap(top, bottom)
        sample = CuttingsSample(
            new_id(),
            top,
            bottom,
            [CuttingsComponent(name, percentage) for name, percentage in normalized.items()],
            description=description.strip() if description and description.strip() else None,
        )
        self._require_well().cuttings.append(sample)
        self.session.dirty = True
        return sample

    def _validate_interval(self, top_depth: float, bottom_depth: float) -> tuple[float, float]:
        top, bottom = float(top_depth), float(bottom_depth)
        if not np.isfinite(top) or not np.isfinite(bottom) or top >= bottom:
            raise ValueError("Кровля шламового интервала должна быть меньше подошвы")
        dataset = self.session.current_dataset
        if dataset is not None:
            finite = dataset.depth[np.isfinite(dataset.depth)]
            if finite.size and (top < float(np.min(finite)) or bottom > float(np.max(finite))):
                raise ValueError("Шламовый интервал выходит за диапазон dataset")
        return top, bottom

    @staticmethod
    def _validate_components(components: dict[str, float]) -> dict[str, float]:
        normalized: dict[str, float] = {}
        for lithotype_id, percentage in components.items():
            name = lithotype_id.strip()
            value = float(percentage)
            if not name or not np.isfinite(value) or value < 0 or value > 100:
                raise ValueError("Компоненты шлама должны иметь долю от 0 до 100%")
            if value > 0:
                normalized[name] = value
        if not normalized:
            raise ValueError("Укажите хотя бы один компонент шлама")
        if not np.isclose(sum(normalized.values()), 100.0, atol=0.01):
            raise ValueError("Сумма компонентов шлама должна быть равна 100%")
        return normalized

    def _ensure_no_overlap(self, top: float, bottom: float) -> None:
        for sample in self._require_well().cuttings:
            if top < sample.bottom_depth and bottom > sample.top_depth:
                raise ValueError(
                    f"Интервал пересекается с пробой {sample.top_depth:g}–{sample.bottom_depth:g} м"
                )

    def _require_well(self) -> Well:
        well = self.session.current_well
        if well is None:
            raise RuntimeError("Сначала выберите скважину")
        return well
