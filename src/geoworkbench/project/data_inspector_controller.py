from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from geoworkbench.data.las_import_report import LasImportIssue, LasIssueSeverity
from geoworkbench.domain.models import Dataset, DatasetIndex, IndexRole, IndexType
from geoworkbench.project.session import ProjectSession


@dataclass(frozen=True, slots=True)
class DatasetSummary:
    well_name: str
    dataset_name: str
    source_path: str | None
    sample_count: int
    curve_count: int
    index_count: int
    active_index_id: str
    headers: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class IndexInspection:
    index_id: str
    mnemonic: str
    index_type: IndexType
    role: IndexRole
    unit: str | None
    sample_count: int
    start: str | None
    stop: str | None
    confidence: float
    evidence: tuple[str, ...]
    warnings: tuple[str, ...]
    active: bool


@dataclass(frozen=True, slots=True)
class CurveInspection:
    curve_id: str
    mnemonic: str
    unit: str | None
    description: str | None
    sample_count: int
    missing_count: int


@dataclass(frozen=True, slots=True)
class LasSourceInspection:
    path: str
    version: str | None
    wrap: str | None
    null_value: float | None
    encoding: str
    newline_style: str
    size_bytes: int
    sha256: str
    sections: tuple[str, ...]
    artifact_status: str
    info_count: int
    warning_count: int
    error_count: int


@dataclass(slots=True)
class DataInspectorController:
    session: ProjectSession

    def summary(self) -> DatasetSummary:
        dataset = self._dataset()
        well = self.session.current_well
        if well is None:
            raise RuntimeError("Сначала выберите скважину")
        return DatasetSummary(
            well_name=well.name,
            dataset_name=dataset.name,
            source_path=str(dataset.source_path) if dataset.source_path is not None else None,
            sample_count=len(dataset.depth),
            curve_count=len(dataset.curves),
            index_count=len(dataset.indexes),
            active_index_id=dataset.active_index.index_id,
            headers=tuple(sorted(dataset.headers.items(), key=lambda item: item[0].casefold())),
        )

    def indexes(self) -> tuple[IndexInspection, ...]:
        dataset = self._dataset()
        return tuple(
            self._inspect_index(index, index.index_id == dataset.active_index_id)
            for index in dataset.indexes.values()
        )

    def curves(self) -> tuple[CurveInspection, ...]:
        dataset = self._dataset()
        return tuple(
            CurveInspection(
                curve_id=curve.metadata.curve_id,
                mnemonic=curve.metadata.original_mnemonic,
                unit=curve.metadata.unit,
                description=curve.metadata.description,
                sample_count=len(curve.values),
                missing_count=int(np.count_nonzero(~np.isfinite(curve.values))),
            )
            for curve in dataset.curves.values()
        )

    def import_issues(self) -> tuple[LasImportIssue, ...]:
        dataset = self._dataset()
        report = self.session.import_reports.get(dataset.dataset_id)
        return report.issues if report is not None else ()

    def source_inspection(self) -> LasSourceInspection | None:
        dataset = self._dataset()
        report = self.session.import_reports.get(dataset.dataset_id)
        if report is None:
            return None
        source = report.source
        artifact = self.session.source_documents.get(dataset.dataset_id)
        if artifact is None:
            artifact_status = "отсутствует"
        elif artifact.size_bytes == source.size_bytes and artifact.sha256 == source.sha256:
            artifact_status = "проверен"
        else:
            artifact_status = "не совпадает с fingerprint"
        return LasSourceInspection(
            path=str(source.path),
            version=source.las_version,
            wrap=source.wrap,
            null_value=source.null_value,
            encoding=source.encoding,
            newline_style=source.newline_style,
            size_bytes=source.size_bytes,
            sha256=source.sha256,
            sections=source.section_names,
            artifact_status=artifact_status,
            info_count=sum(issue.severity is LasIssueSeverity.INFO for issue in report.issues),
            warning_count=sum(
                issue.severity is LasIssueSeverity.WARNING for issue in report.issues
            ),
            error_count=sum(issue.severity is LasIssueSeverity.ERROR for issue in report.issues),
        )

    def set_active_index(self, index_id: str) -> None:
        dataset = self._dataset()
        if dataset.active_index_id == index_id:
            return
        dataset.set_active_index(index_id)
        self.session.dirty = True

    def _dataset(self) -> Dataset:
        dataset = self.session.current_dataset
        if dataset is None:
            raise RuntimeError("Сначала выберите dataset")
        return dataset

    @staticmethod
    def _inspect_index(index: DatasetIndex, active: bool) -> IndexInspection:
        values = np.asarray(index.values)
        warnings: list[str] = []
        if values.size == 0:
            start = stop = None
            warnings.append("индекс пуст")
        else:
            start, stop = _format_index_value(values[0]), _format_index_value(values[-1])
            if np.issubdtype(values.dtype, np.datetime64):
                missing_mask = np.isnat(values)
                comparable = values.astype("datetime64[ns]").astype(np.int64)
                finite = comparable[~missing_mask]
            else:
                comparable = values.astype(np.float64)
                finite = comparable[np.isfinite(comparable)]
            if finite.size != comparable.size:
                warnings.append("есть пропущенные значения")
            if finite.size > 1:
                differences = np.diff(finite)
                if not (np.all(differences >= 0) or np.all(differences <= 0)):
                    warnings.append("смешанное направление")
                if np.unique(finite).size != finite.size:
                    warnings.append("повторяющиеся значения")
        return IndexInspection(
            index_id=index.index_id,
            mnemonic=index.mnemonic,
            index_type=index.index_type,
            role=index.role,
            unit=index.unit,
            sample_count=len(values),
            start=start,
            stop=stop,
            confidence=index.confidence,
            evidence=index.evidence,
            warnings=tuple(warnings),
            active=active,
        )


def _format_index_value(value) -> str:
    if np.issubdtype(np.asarray(value).dtype, np.datetime64):
        return str(np.datetime64(value, "ns"))
    try:
        return f"{float(value):.10g}"
    except (TypeError, ValueError):
        return str(value)
