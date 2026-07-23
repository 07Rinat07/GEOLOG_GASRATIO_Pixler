from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import numpy as np

from geoworkbench.data.las_import_policy import LasImportMode
from geoworkbench.data.las_import_report import (
    LasImportIssue,
    LasImportReport,
    LasIssueSeverity,
    LasSourceSnapshot,
)
from geoworkbench.data.lossless_las import LosslessLasDocument, parse_lossless_las
from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.importers.paradox.models import ParadoxImportResult
from geoworkbench.services.depth_axis import analyze_depth_axis
from geoworkbench.services.import_jobs import DatasetImportJobExecutor


@dataclass(frozen=True, slots=True)
class FakeLasImportResult:
    dataset: Dataset
    report: LasImportReport
    source_document: LosslessLasDocument


@dataclass(frozen=True, slots=True)
class Registration:
    dataset: Dataset
    source_document: LosslessLasDocument | None
    import_report: LasImportReport | None
    create_new_well: bool


@dataclass
class FakeDatasetImportPort:
    registrations: list[Registration] = field(default_factory=list)

    def add_imported_dataset(
        self,
        dataset: Dataset,
        *,
        source_document: LosslessLasDocument | None = None,
        import_report: LasImportReport | None = None,
        create_new_well: bool = False,
    ) -> str:
        self.registrations.append(
            Registration(
                dataset,
                source_document,
                import_report,
                create_new_well,
            )
        )
        return f"Well {len(self.registrations)}"


def make_dataset(depth: np.ndarray | None = None) -> Dataset:
    values = np.asarray(
        depth if depth is not None else np.array([100.0, 100.2]),
        dtype=np.float64,
    )
    return Dataset(
        "dataset-1",
        "Dataset",
        DatasetKind.USER,
        DepthDomain.MD,
        values,
    )


def make_las_result(
    source: Path,
    *,
    depth: np.ndarray | None = None,
    issues: tuple[LasImportIssue, ...] = (),
) -> FakeLasImportResult:
    dataset = make_dataset(depth)
    document = parse_lossless_las(b"~Version\nVERS. 2.0\n~Well\n~Curve\n~Ascii\n")
    report = LasImportReport(
        source=LasSourceSnapshot(
            path=source,
            size_bytes=document.size_bytes,
            sha256=document.sha256,
            encoding=document.encoding,
            newline_style=document.newline_style.value,
            section_names=tuple(section.name for section in document.sections),
            las_version="2.0",
            wrap="NO",
            null_value=-999.25,
        ),
        depth_axis=analyze_depth_axis(dataset.depth),
        issues=issues,
    )
    return FakeLasImportResult(dataset, report, document)


def test_las_job_applies_policy_registers_provenance_and_reports_batch_state(
    tmp_path: Path,
) -> None:
    accepted = tmp_path / "accepted.las"
    rejected = tmp_path / "rejected.las"
    result = make_las_result(
        accepted,
        depth=np.array([101.0, 100.5, 100.0]),
        issues=(
            LasImportIssue(
                "index-descending",
                LasIssueSeverity.WARNING,
                "Depth is descending",
            ),
            LasImportIssue(
                "header-warning",
                LasIssueSeverity.WARNING,
                "Header requires review",
            ),
        ),
    )
    port = FakeDatasetImportPort()

    def load(source: str | Path) -> FakeLasImportResult:
        if Path(source) == rejected:
            raise RuntimeError("broken source")
        return result

    executor = DatasetImportJobExecutor(port, las_loader=load)
    outcome = executor.execute_las(
        (accepted, rejected),
        LasImportMode.COMPATIBLE,
    )

    assert len(outcome.successful) == 1
    assert len(outcome.failed) == 1
    assert outcome.last_successful is outcome.successful[0]
    assert outcome.successful[0].well_name == "Well 1"
    assert outcome.successful[0].warning_messages == ("Header requires review",)
    assert outcome.successful[0].descending_depth is True
    assert outcome.failed[0].error == "broken source"
    assert port.registrations == [
        Registration(result.dataset, result.source_document, result.report, True)
    ]


def test_manual_las_review_can_skip_without_mutating_project(tmp_path: Path) -> None:
    source = tmp_path / "manual.las"
    warning = LasImportIssue(
        "header-warning",
        LasIssueSeverity.WARNING,
        "Header requires review",
    )
    port = FakeDatasetImportPort()
    executor = DatasetImportJobExecutor(
        port,
        las_loader=lambda _source: make_las_result(source, issues=(warning,)),
    )
    confirmations: list[tuple[Path, tuple[LasImportIssue, ...]]] = []

    outcome = executor.execute_las(
        (source,),
        LasImportMode.MANUAL,
        confirm_review=lambda path, issues: confirmations.append((path, issues)) or False,
    )

    assert outcome.successful == ()
    assert len(outcome.skipped) == 1
    assert outcome.failed == ()
    assert confirmations == [(source, (warning,))]
    assert port.registrations == []


def test_strict_las_policy_blocks_warning_before_registration(tmp_path: Path) -> None:
    source = tmp_path / "strict.las"
    warning = LasImportIssue(
        "header-warning",
        LasIssueSeverity.WARNING,
        "Header requires review",
    )
    port = FakeDatasetImportPort()
    executor = DatasetImportJobExecutor(
        port,
        las_loader=lambda _source: make_las_result(source, issues=(warning,)),
    )

    outcome = executor.execute_las((source,), LasImportMode.STRICT)

    assert outcome.successful == ()
    assert "strict" in outcome.failed[0].error
    assert "Header requires review" in outcome.failed[0].error
    assert port.registrations == []


def test_paradox_job_registers_dataset_in_a_new_well(tmp_path: Path) -> None:
    source = tmp_path / "source.db"
    dataset = make_dataset()
    result = cast(ParadoxImportResult, SimpleNamespace(dataset=dataset))
    port = FakeDatasetImportPort()
    executor = DatasetImportJobExecutor(port)

    outcome = executor.register_paradox(source, result)

    assert outcome.succeeded is True
    assert outcome.result is result
    assert outcome.well_name == "Well 1"
    assert port.registrations == [Registration(dataset, None, None, True)]


def test_main_window_delegates_las_and_paradox_project_mutation() -> None:
    project_root = Path(__file__).resolve().parents[1]
    source = (project_root / "src/geoworkbench/ui/main_window.py").read_text(
        encoding="utf-8"
    )

    assert "self._dataset_import_jobs.execute_las(" in source
    assert "self._dataset_import_jobs.register_paradox(" in source
    assert "import_las_with_report(" not in source
    assert "evaluate_las_import(" not in source
    assert "self.session.add_dataset(result.dataset, create_new_well=True)" not in source
    assert not (project_root / "src/geoworkbench/ui/import_job_controller.py").exists()
    assert not (project_root / "src/geoworkbench/ui/tabular_import_jobs.py").exists()
