from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pytest

from geoworkbench.data.csv_adapter import (
    CsvImportError,
    CsvImportPlan,
    CsvImportResult,
)
from geoworkbench.data.excel_adapter import ExcelImportError, ExcelImportPlan
from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.services.import_jobs import (
    DatasetImportJobExecutor,
    ImportSourceKind,
)


@dataclass
class FakeTabularImportPort:
    datasets: list[Dataset] = field(default_factory=list)

    def add_imported_dataset(
        self,
        dataset: Dataset,
        **_kwargs: object,
    ) -> str:
        self.datasets.append(dataset)
        return "Well"


def make_result() -> CsvImportResult:
    dataset = Dataset(
        "dataset-1",
        "Dataset",
        DatasetKind.USER,
        DepthDomain.MD,
        np.array([100.0, 100.2]),
    )
    return CsvImportResult(dataset, ",", "utf-8", 2)


def test_csv_job_builds_plan_loads_and_registers_dataset(tmp_path: Path) -> None:
    port = FakeTabularImportPort()
    result = make_result()
    plan = CsvImportPlan(index_column="DEPTH")
    received: list[tuple[Path, CsvImportPlan]] = []

    def load(source: str | Path, selected: CsvImportPlan) -> CsvImportResult:
        received.append((Path(source), selected))
        return result

    executor = DatasetImportJobExecutor(port, csv_loader=load)
    source = tmp_path / "source.csv"

    outcome = executor.execute_csv(source, lambda: plan)

    assert outcome.succeeded is True
    assert outcome.kind is ImportSourceKind.CSV
    assert received == [(source, plan)]
    assert port.datasets == [result.dataset]


def test_excel_job_builds_plan_loads_and_registers_dataset(tmp_path: Path) -> None:
    port = FakeTabularImportPort()
    result = make_result()
    plan = ExcelImportPlan("Data", index_column="DEPTH")

    executor = DatasetImportJobExecutor(
        port,
        excel_loader=lambda _source, _plan: result,
    )
    outcome = executor.execute_excel(tmp_path / "source.xlsx", lambda: plan)

    assert outcome.succeeded is True
    assert outcome.kind is ImportSourceKind.EXCEL
    assert port.datasets == [result.dataset]


@pytest.mark.parametrize(
    ("kind", "error_type", "message"),
    [
        (ImportSourceKind.CSV, CsvImportError, "bad csv"),
        (ImportSourceKind.EXCEL, ExcelImportError, "bad excel"),
    ],
)
def test_failed_tabular_job_returns_error_without_registering_dataset(
    tmp_path: Path,
    kind: ImportSourceKind,
    error_type: type[Exception],
    message: str,
) -> None:
    port = FakeTabularImportPort()

    def fail(*_args):
        raise error_type(message)

    executor = DatasetImportJobExecutor(
        port,
        csv_loader=fail,
        excel_loader=fail,
    )
    outcome = (
        executor.execute_csv(
            tmp_path / "source.csv",
            lambda: CsvImportPlan(index_column="DEPTH"),
        )
        if kind is ImportSourceKind.CSV
        else executor.execute_excel(
            tmp_path / "source.xlsx",
            lambda: ExcelImportPlan("Data", index_column="DEPTH"),
        )
    )

    assert outcome.succeeded is False
    assert outcome.error == message
    assert port.datasets == []


def test_invalid_plan_and_registration_failure_are_reported(tmp_path: Path) -> None:
    class RejectingPort(FakeTabularImportPort):
        def add_imported_dataset(
            self,
            dataset: Dataset,
            **_kwargs: object,
        ) -> str:
            del dataset
            raise ValueError("registration failed")

    executor = DatasetImportJobExecutor(
        RejectingPort(),
        csv_loader=lambda _source, _plan: make_result(),
    )

    def invalid_plan() -> CsvImportPlan:
        raise ValueError("invalid plan")

    invalid = executor.execute_csv(
        tmp_path / "source.csv",
        invalid_plan,
    )
    rejected = executor.execute_csv(
        tmp_path / "source.csv",
        lambda: CsvImportPlan(index_column="DEPTH"),
    )

    assert invalid.error == "invalid plan"
    assert rejected.error == "registration failed"


def test_main_window_delegates_tabular_execution_to_job_executor() -> None:
    source = (
        Path(__file__).resolve().parents[1]
        / "src/geoworkbench/ui/main_window.py"
    ).read_text(encoding="utf-8")

    assert "self._dataset_import_jobs.execute_csv(" in source
    assert "self._dataset_import_jobs.execute_excel(" in source
    assert "result = import_csv(" not in source
    assert "result = import_excel(" not in source
