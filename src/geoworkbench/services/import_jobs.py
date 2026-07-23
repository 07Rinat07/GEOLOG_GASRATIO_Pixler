from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from geoworkbench.data.csv_adapter import (
    CsvImportError,
    CsvImportPlan,
    CsvImportResult,
    import_csv,
)
from geoworkbench.data.excel_adapter import (
    ExcelImportError,
    ExcelImportPlan,
    import_excel,
)
from geoworkbench.data.las_import_policy import (
    LasImportMode,
    evaluate_las_import,
)
from geoworkbench.data.las_import_report import (
    LasImportIssue,
    LasImportReport,
    LasIssueSeverity,
)
from geoworkbench.data.lossless_las import LosslessLasDocument
from geoworkbench.domain.models import Dataset
from geoworkbench.importers.paradox.models import ParadoxImportResult
from geoworkbench.services.depth_axis import DepthDirection, analyze_depth_axis


if TYPE_CHECKING:
    from geoworkbench.data.las_adapter import LasImportResult
else:
    LasImportResult = Any


def _load_las_with_report(path: str | Path) -> LasImportResult:
    from geoworkbench.data.las_adapter import import_las_with_report

    return import_las_with_report(path)


class ImportSourceKind(StrEnum):
    LAS = "las"
    CSV = "csv"
    EXCEL = "excel"
    PARADOX = "paradox"


@dataclass(frozen=True, slots=True)
class ImportSourceChoice:
    kind: ImportSourceKind
    label: str


class ImportJobPort(Protocol):
    def execute_import(self, kind: ImportSourceKind) -> None: ...

    def report_unknown_source(self, selected_label: str) -> None: ...


_SOURCE_LABEL_KEYS = (
    (ImportSourceKind.LAS, "import.source_las"),
    (ImportSourceKind.CSV, "import.source_csv"),
    (ImportSourceKind.EXCEL, "import.source_excel"),
    (ImportSourceKind.PARADOX, "import.source_paradox"),
)


class ImportJobController:
    """Resolve one universal-import choice into a stable import job kind."""

    def __init__(self, port: ImportJobPort) -> None:
        self._port = port

    @staticmethod
    def choices(localize: Callable[[str], str]) -> tuple[ImportSourceChoice, ...]:
        return tuple(
            ImportSourceChoice(kind, localize(label_key))
            for kind, label_key in _SOURCE_LABEL_KEYS
        )

    def dispatch(
        self,
        selected_label: str,
        accepted: bool,
        localize: Callable[[str], str],
    ) -> bool:
        if not accepted:
            return False
        kind_by_label = {choice.label: choice.kind for choice in self.choices(localize)}
        kind = kind_by_label.get(selected_label)
        if kind is None:
            self._port.report_unknown_source(selected_label)
            return False
        self._port.execute_import(kind)
        return True


class DatasetImportPort(Protocol):
    """Application boundary for attaching imported data to the active project."""

    def add_imported_dataset(
        self,
        dataset: Dataset,
        *,
        source_document: LosslessLasDocument | None = None,
        import_report: LasImportReport | None = None,
        create_new_well: bool = False,
    ) -> str: ...


@dataclass(frozen=True, slots=True)
class TabularImportOutcome:
    kind: ImportSourceKind
    source: Path
    result: CsvImportResult | None = None
    error: str = ""
    review_skipped: bool = False

    @property
    def succeeded(self) -> bool:
        return self.result is not None


@dataclass(frozen=True, slots=True)
class LasImportOutcome:
    source: Path
    result: LasImportResult | None = None
    well_name: str | None = None
    error: str = ""
    review_skipped: bool = False
    warning_messages: tuple[str, ...] = ()
    descending_depth: bool = False

    @property
    def succeeded(self) -> bool:
        return self.result is not None and self.well_name is not None


@dataclass(frozen=True, slots=True)
class LasImportBatchOutcome:
    files: tuple[LasImportOutcome, ...]

    @property
    def successful(self) -> tuple[LasImportOutcome, ...]:
        return tuple(item for item in self.files if item.succeeded)

    @property
    def failed(self) -> tuple[LasImportOutcome, ...]:
        return tuple(item for item in self.files if item.error)

    @property
    def skipped(self) -> tuple[LasImportOutcome, ...]:
        return tuple(item for item in self.files if item.review_skipped)

    @property
    def last_successful(self) -> LasImportOutcome | None:
        return self.successful[-1] if self.successful else None


@dataclass(frozen=True, slots=True)
class ParadoxImportOutcome:
    source: Path
    result: ParadoxImportResult | None = None
    well_name: str | None = None
    error: str = ""
    review_skipped: bool = False

    @property
    def succeeded(self) -> bool:
        return self.result is not None and self.well_name is not None


CsvLoader = Callable[[str | Path, CsvImportPlan], CsvImportResult]
ExcelLoader = Callable[[str | Path, ExcelImportPlan], CsvImportResult]
LasLoader = Callable[[str | Path], LasImportResult]
LasReviewConfirmation = Callable[[Path, tuple[LasImportIssue, ...]], bool]
ImportDatasetReview = Callable[[Dataset, ImportSourceKind, Path], Dataset | None]


class DatasetImportJobExecutor:
    """Execute import plans and commit accepted datasets through one project port.

    Qt dialogs remain responsible for collecting filenames and user choices. This
    executor owns the application-level work: loading, policy evaluation, dataset
    registration, and stable outcomes that the UI can present without mutating the
    project model directly.
    """

    def __init__(
        self,
        port: DatasetImportPort,
        *,
        csv_loader: CsvLoader = import_csv,
        excel_loader: ExcelLoader = import_excel,
        las_loader: LasLoader = _load_las_with_report,
    ) -> None:
        self._port = port
        self._csv_loader = csv_loader
        self._excel_loader = excel_loader
        self._las_loader = las_loader

    def execute_csv(
        self,
        source: Path,
        plan_factory: Callable[[], CsvImportPlan],
        *,
        review_dataset: ImportDatasetReview | None = None,
    ) -> TabularImportOutcome:
        try:
            result = self._csv_loader(source, plan_factory())
            dataset = self._review_or_original(
                result.dataset, ImportSourceKind.CSV, source, review_dataset
            )
            if dataset is None:
                return TabularImportOutcome(
                    ImportSourceKind.CSV, source, review_skipped=True
                )
            result = replace(result, dataset=dataset)
            self._port.add_imported_dataset(result.dataset)
        except (CsvImportError, FileNotFoundError, OSError, ValueError) as exc:
            return TabularImportOutcome(ImportSourceKind.CSV, source, error=str(exc))
        return TabularImportOutcome(ImportSourceKind.CSV, source, result=result)

    def execute_excel(
        self,
        source: Path,
        plan_factory: Callable[[], ExcelImportPlan],
        *,
        review_dataset: ImportDatasetReview | None = None,
    ) -> TabularImportOutcome:
        try:
            result = self._excel_loader(source, plan_factory())
            dataset = self._review_or_original(
                result.dataset, ImportSourceKind.EXCEL, source, review_dataset
            )
            if dataset is None:
                return TabularImportOutcome(
                    ImportSourceKind.EXCEL, source, review_skipped=True
                )
            result = replace(result, dataset=dataset)
            self._port.add_imported_dataset(result.dataset)
        except (ExcelImportError, FileNotFoundError, OSError, ValueError) as exc:
            return TabularImportOutcome(ImportSourceKind.EXCEL, source, error=str(exc))
        return TabularImportOutcome(ImportSourceKind.EXCEL, source, result=result)

    def execute_las(
        self,
        sources: tuple[Path, ...],
        mode: LasImportMode,
        *,
        confirm_review: LasReviewConfirmation | None = None,
        review_dataset: ImportDatasetReview | None = None,
    ) -> LasImportBatchOutcome:
        outcomes: list[LasImportOutcome] = []
        for source in sources:
            try:
                result = self._las_loader(source)
                decision = evaluate_las_import(result.report, mode)
                if not decision.accepted:
                    messages = "\n  ".join(
                        issue.message for issue in decision.blocking_issues
                    )
                    raise RuntimeError(
                        f"режим {mode.value} отклонил файл:\n  {messages}"
                    )
                if decision.requires_confirmation:
                    if confirm_review is None:
                        raise RuntimeError(
                            "режим manual требует подтверждения "
                            "диагностических сообщений"
                        )
                    if not confirm_review(source, decision.review_issues):
                        outcomes.append(
                            LasImportOutcome(source=source, review_skipped=True)
                        )
                        continue

                dataset = self._review_or_original(
                    result.dataset, ImportSourceKind.LAS, source, review_dataset
                )
                if dataset is None:
                    outcomes.append(
                        LasImportOutcome(source=source, review_skipped=True)
                    )
                    continue
                result = replace(result, dataset=dataset)
                well_name = self._port.add_imported_dataset(
                    result.dataset,
                    source_document=result.source_document,
                    import_report=result.report,
                    create_new_well=True,
                )
                warning_messages = (
                    tuple(
                        issue.message
                        for issue in result.report.issues
                        if issue.code != "index-descending"
                        and issue.severity is not LasIssueSeverity.INFO
                    )
                    if mode is LasImportMode.COMPATIBLE
                    else ()
                )
                descending = (
                    mode is LasImportMode.COMPATIBLE
                    and analyze_depth_axis(result.dataset.depth).direction
                    is DepthDirection.DESCENDING
                )
                outcomes.append(
                    LasImportOutcome(
                        source=source,
                        result=result,
                        well_name=well_name,
                        warning_messages=warning_messages,
                        descending_depth=descending,
                    )
                )
            except (OSError, RuntimeError, ValueError) as exc:
                outcomes.append(LasImportOutcome(source=source, error=str(exc)))
        return LasImportBatchOutcome(tuple(outcomes))

    @staticmethod
    def _review_or_original(
        dataset: Dataset,
        kind: ImportSourceKind,
        source: Path,
        review_dataset: ImportDatasetReview | None,
    ) -> Dataset | None:
        return dataset if review_dataset is None else review_dataset(dataset, kind, source)

    def register_paradox(
        self,
        source: Path,
        result: ParadoxImportResult,
        *,
        review_dataset: ImportDatasetReview | None = None,
    ) -> ParadoxImportOutcome:
        try:
            dataset = self._review_or_original(
                result.dataset, ImportSourceKind.PARADOX, source, review_dataset
            )
            if dataset is None:
                return ParadoxImportOutcome(source, review_skipped=True)
            if dataset is not result.dataset:
                removed = max(0, len(result.dataset.curves) - len(dataset.curves))
                result = replace(
                    result,
                    dataset=dataset,
                    imported_channels=len(dataset.curves),
                    skipped_channels=result.skipped_channels + removed,
                )
            well_name = self._port.add_imported_dataset(
                result.dataset,
                create_new_well=True,
            )
        except (OSError, ValueError) as exc:
            return ParadoxImportOutcome(source, error=str(exc))
        return ParadoxImportOutcome(source, result=result, well_name=well_name)
