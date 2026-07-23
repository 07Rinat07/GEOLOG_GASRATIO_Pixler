from __future__ import annotations

from pathlib import Path

from geoworkbench.data.las_adapter import LasImportResult, import_las_with_report
from geoworkbench.domain.models import Dataset
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.daily_las_growth import (
    DailyLasGrowthOutcome,
    DailyLasGrowthPlan,
    analyze_daily_las_growth,
    apply_daily_las_growth,
)


class DailyLasGrowthController:
    """Project-facing safe daily append workflow for one selected dataset."""

    def __init__(self, session: ProjectSession) -> None:
        self.session = session
        self._source: LasImportResult | None = None
        self._source_path: Path | None = None
        self._plan: DailyLasGrowthPlan | None = None

    def datasets_for_current_well(self) -> tuple[Dataset, ...]:
        well = self.session.current_well
        if well is None:
            return ()
        return tuple(sorted(well.datasets.values(), key=lambda item: item.name.casefold()))

    def analyze(self, source_path: str | Path, target_dataset_id: str) -> DailyLasGrowthPlan:
        target = self._target(target_dataset_id)
        path = Path(source_path)
        imported = import_las_with_report(path, kind=target.kind)
        plan = analyze_daily_las_growth(
            target,
            imported.dataset,
            source_name=path.name,
            source_sha256=imported.report.source.sha256,
        )
        self._source = imported
        self._source_path = path
        self._plan = plan
        return plan

    def apply(self, plan: DailyLasGrowthPlan) -> DailyLasGrowthOutcome:
        if self._plan != plan or self._source is None or self._source_path is None:
            raise RuntimeError("Сначала повторно проанализируйте ежедневный LAS")
        target = self._target(plan.target_dataset_id)
        outcome = apply_daily_las_growth(target, self._source.dataset, plan)
        if outcome.record is not None:
            # A grown dataset is a composite history, not a lossless copy of one
            # source file. Keeping the old single-file artifact would be unsafe.
            self.session.source_documents.pop(target.dataset_id, None)
            self.session.import_reports.pop(target.dataset_id, None)
            self.session.dirty = True
        self._source = None
        self._source_path = None
        self._plan = None
        return outcome

    def _target(self, dataset_id: str) -> Dataset:
        well = self.session.current_well
        if well is None:
            raise RuntimeError("Сначала выберите скважину")
        try:
            return well.datasets[dataset_id]
        except KeyError as exc:
            raise KeyError(f"Dataset отсутствует в текущей скважине: {dataset_id}") from exc
