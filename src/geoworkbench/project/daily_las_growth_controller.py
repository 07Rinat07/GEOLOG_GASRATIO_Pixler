from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from geoworkbench.data.las_adapter import LasImportResult, import_las_with_report
from geoworkbench.domain.models import Dataset, DatasetSourceRevision
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.daily_las_growth import (
    DailyLasGrowthError,
    DailyLasGrowthOutcome,
    DailyLasGrowthPlan,
    analyze_daily_las_growth,
    apply_daily_las_growth,
    file_sha256,
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
        # A failed second preview must never leave the first file eligible for
        # confirmation.  Start every analysis from a clean transient state.
        self.reset_state()
        target = self._target(target_dataset_id)
        path = Path(source_path)
        imported = import_las_with_report(path, kind=target.kind)
        current_sha256 = self._stable_source_sha256(path)
        if current_sha256 != imported.report.source.sha256:
            raise DailyLasGrowthError(
                "Исходный LAS изменился во время анализа; проверьте прирост повторно"
            )
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
        source_result = self._source
        source_path = self._source_path
        provider_kind = self._provider_kind
        provider_location = self._provider_location
        try:
            if self._stable_source_sha256(source_path) != plan.source_sha256:
                raise DailyLasGrowthError(
                    "Исходный LAS изменился после анализа; "
                    "проверьте прирост повторно"
                )
            target = self._target(plan.target_dataset_id)
            outcome = apply_daily_las_growth(
                target,
                source_result.dataset,
                plan,
                provider_kind=provider_kind,
                provider_location=provider_location,
            )
            if outcome.record is not None:
                self._preserve_initial_source(target)
                artifact_id = outcome.record.source_artifact_id
                if artifact_id is None:
                    raise RuntimeError(
                        "История наращивания не содержит source artifact ID"
                    )
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
            return outcome
        finally:
            # A preview is a one-shot authorization for one exact source and
            # project state. Any failed commit must be analyzed again.
            self.reset_state()

    def reset_state(self) -> None:
        """Discard a preview that belongs to a previous file or project."""

        self._source = None
        self._source_path = None
        self._plan = None
        self._provider_kind = "manual_file"
        self._provider_location = None

    @staticmethod
    def _stable_source_sha256(path: Path) -> str:
        """Hash one stable on-disk revision before committing an append.

        A server synchronization client may replace a LAS between preview and
        confirmation.  Compare file identity around the hash read so that the
        audit record can never point at a different revision than the bytes
        already parsed into the append plan.
        """

        try:
            before = path.stat()
            digest = file_sha256(path)
            after = path.stat()
        except OSError as exc:
            raise DailyLasGrowthError(f"Не удалось повторно проверить LAS: {path.name}") from exc
        before_identity = (before.st_size, before.st_mtime_ns, before.st_ino)
        after_identity = (after.st_size, after.st_mtime_ns, after.st_ino)
        if before_identity != after_identity:
            raise DailyLasGrowthError(
                f"LAS изменился во время контрольного чтения: {path.name}"
            )
        return digest

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
