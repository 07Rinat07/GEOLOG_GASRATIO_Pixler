from __future__ import annotations

from pathlib import Path

from geoworkbench.data.las_adapter import LasImportResult, import_las_with_report
from datetime import datetime, timezone

from geoworkbench.domain.models import Dataset, DatasetSourceRevision
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
        self._provider_kind = "manual_file"
        self._provider_location: str | None = None

    def datasets_for_current_well(self) -> tuple[Dataset, ...]:
        well = self.session.current_well
        if well is None:
            return ()
        return tuple(sorted(well.datasets.values(), key=lambda item: item.name.casefold()))

    def analyze(
        self,
        source_path: str | Path,
        target_dataset_id: str,
        *,
        provider_kind: str = "manual_file",
        provider_location: str | None = None,
    ) -> DailyLasGrowthPlan:
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
        self._provider_kind = provider_kind
        self._provider_location = provider_location or str(path)
        return plan

    def apply(self, plan: DailyLasGrowthPlan) -> DailyLasGrowthOutcome:
        if self._plan != plan or self._source is None or self._source_path is None:
            raise RuntimeError("Сначала повторно проанализируйте ежедневный LAS")
        target = self._target(plan.target_dataset_id)
        source_result = self._source
        outcome = apply_daily_las_growth(
            target,
            source_result.dataset,
            plan,
            provider_kind=self._provider_kind,
            provider_location=self._provider_location,
        )
        if outcome.record is not None:
            self._preserve_initial_source(target)
            artifact_id = outcome.record.source_artifact_id
            if artifact_id is None:
                raise RuntimeError("История наращивания не содержит source artifact ID")
            self.session.source_documents[artifact_id] = source_result.source_document
            target.source_revisions.append(
                DatasetSourceRevision(
                    source_revision_id=outcome.record.import_id,
                    artifact_id=artifact_id,
                    source_name=outcome.record.source_name,
                    source_sha256=outcome.record.source_sha256,
                    size_bytes=source_result.source_document.size_bytes,
                    imported_at=outcome.record.imported_at,
                    provider_kind=outcome.record.provider_kind,
                    provider_location=outcome.record.provider_location,
                    start_value=outcome.record.start_value,
                    stop_value=outcome.record.stop_value,
                    rows_added=outcome.record.rows_added,
                    rows_skipped=outcome.record.rows_skipped,
                )
            )
            self.session.import_reports.pop(target.dataset_id, None)
            self.session.dirty = True
        self._source = None
        self._source_path = None
        self._plan = None
        self._provider_kind = "manual_file"
        self._provider_location = None
        return outcome

    def _preserve_initial_source(self, target: Dataset) -> None:
        document = self.session.source_documents.pop(target.dataset_id, None)
        if document is None:
            return
        artifact_id = f"initial-{document.sha256}"
        self.session.source_documents[artifact_id] = document
        if any(item.source_sha256 == document.sha256 for item in target.source_revisions):
            return
        index = target.active_index
        original_rows = max(0, len(index.values) - (target.append_history[-1].rows_added or 0))
        start = str(index.values[0]) if original_rows else ""
        stop = str(index.values[original_rows - 1]) if original_rows else ""
        target.source_revisions.insert(
            0,
            DatasetSourceRevision(
                source_revision_id=f"initial:{target.dataset_id}",
                artifact_id=artifact_id,
                source_name=(target.source_path.name if target.source_path is not None else target.name),
                source_sha256=document.sha256,
                size_bytes=document.size_bytes,
                imported_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                provider_kind="initial_import",
                provider_location=(str(target.source_path) if target.source_path else None),
                start_value=start,
                stop_value=stop,
                rows_added=original_rows,
                rows_skipped=0,
            ),
        )

    def _target(self, dataset_id: str) -> Dataset:
        well = self.session.current_well
        if well is None:
            raise RuntimeError("Сначала выберите скважину")
        try:
            return well.datasets[dataset_id]
        except KeyError as exc:
            raise KeyError(f"Dataset отсутствует в текущей скважине: {dataset_id}") from exc
