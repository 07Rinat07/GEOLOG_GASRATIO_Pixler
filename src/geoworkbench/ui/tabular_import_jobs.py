from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

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
from geoworkbench.domain.models import Dataset
from geoworkbench.ui.import_job_controller import ImportSourceKind


class TabularImportPort(Protocol):
    def add_imported_dataset(self, dataset: Dataset) -> None: ...


@dataclass(frozen=True, slots=True)
class TabularImportOutcome:
    kind: ImportSourceKind
    source: Path
    result: CsvImportResult | None = None
    error: str = ""

    @property
    def succeeded(self) -> bool:
        return self.result is not None


CsvLoader = Callable[[str | Path, CsvImportPlan], CsvImportResult]
ExcelLoader = Callable[[str | Path, ExcelImportPlan], CsvImportResult]


class TabularImportJobExecutor:
    """Execute confirmed CSV/Excel plans and register their datasets."""

    def __init__(
        self,
        port: TabularImportPort,
        *,
        csv_loader: CsvLoader = import_csv,
        excel_loader: ExcelLoader = import_excel,
    ) -> None:
        self._port = port
        self._csv_loader = csv_loader
        self._excel_loader = excel_loader

    def execute_csv(
        self,
        source: Path,
        plan_factory: Callable[[], CsvImportPlan],
    ) -> TabularImportOutcome:
        try:
            result = self._csv_loader(source, plan_factory())
            self._port.add_imported_dataset(result.dataset)
        except (CsvImportError, FileNotFoundError, OSError, ValueError) as exc:
            return TabularImportOutcome(ImportSourceKind.CSV, source, error=str(exc))
        return TabularImportOutcome(ImportSourceKind.CSV, source, result=result)

    def execute_excel(
        self,
        source: Path,
        plan_factory: Callable[[], ExcelImportPlan],
    ) -> TabularImportOutcome:
        try:
            result = self._excel_loader(source, plan_factory())
            self._port.add_imported_dataset(result.dataset)
        except (ExcelImportError, FileNotFoundError, OSError, ValueError) as exc:
            return TabularImportOutcome(ImportSourceKind.EXCEL, source, error=str(exc))
        return TabularImportOutcome(ImportSourceKind.EXCEL, source, result=result)
