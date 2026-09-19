from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Protocol

from geoworkbench.project.document_bundle_snapshot import (
    DocumentBundleSnapshotBinding,
)


class DocumentBundleOrchestrationError(RuntimeError):
    """Raised when the bundle cannot be orchestrated safely."""


class DocumentBundleExporter(Protocol):
    """Strategy port implemented by one existing output workflow."""

    output_id: str

    def export(self, snapshot: DocumentBundleSnapshotBinding) -> tuple[Path, ...]:
        """Produce all files for one logical output from the bound snapshot."""


class DocumentBundleSnapshotGuard(Protocol):
    """Safety port that revalidates the persisted snapshot before each output."""

    def assert_source_current(self, snapshot: DocumentBundleSnapshotBinding) -> None:
        """Raise when the persisted source no longer matches the snapshot binding."""


@dataclass(frozen=True, slots=True)
class DocumentBundleOutputResult:
    output_id: str
    paths: tuple[Path, ...] = ()
    error_message: str | None = None

    def __post_init__(self) -> None:
        if not self.output_id.strip():
            raise DocumentBundleOrchestrationError("output_id must not be blank")
        if self.error_message is None:
            if not self.paths:
                raise DocumentBundleOrchestrationError(
                    "successful bundle output must contain at least one file"
                )
        elif self.paths:
            raise DocumentBundleOrchestrationError(
                "failed bundle output must not expose output paths"
            )

    @property
    def succeeded(self) -> bool:
        return self.error_message is None


@dataclass(frozen=True, slots=True)
class DocumentBundleRun:
    snapshot: DocumentBundleSnapshotBinding
    results: tuple[DocumentBundleOutputResult, ...]

    def __post_init__(self) -> None:
        output_ids = tuple(result.output_id for result in self.results)
        if len(set(output_ids)) != len(output_ids):
            raise DocumentBundleOrchestrationError(
                "bundle run contains duplicate output results"
            )
        if output_ids != self.snapshot.request.output_ids:
            raise DocumentBundleOrchestrationError(
                "bundle run results must match the request output order"
            )

    @property
    def is_complete(self) -> bool:
        return all(result.succeeded for result in self.results)

    @property
    def failed_output_ids(self) -> tuple[str, ...]:
        return tuple(
            result.output_id for result in self.results if not result.succeeded
        )


@dataclass(slots=True)
class DocumentBundleOrchestrator:
    """Coordinate independent exporters without duplicating their format logic."""

    exporters: Mapping[str, DocumentBundleExporter]
    snapshot_guard: DocumentBundleSnapshotGuard

    def execute(self, snapshot: DocumentBundleSnapshotBinding) -> DocumentBundleRun:
        self._validate_registry(snapshot)
        results = tuple(
            self._execute_output(snapshot, output_id)
            for output_id in snapshot.request.output_ids
        )
        return DocumentBundleRun(snapshot=snapshot, results=results)

    def retry_failed(self, previous: DocumentBundleRun) -> DocumentBundleRun:
        self._validate_registry(previous.snapshot)
        failed = set(previous.failed_output_ids)
        if not failed:
            return previous

        results = tuple(
            self._execute_output(previous.snapshot, result.output_id)
            if result.output_id in failed
            else result
            for result in previous.results
        )
        return DocumentBundleRun(snapshot=previous.snapshot, results=results)

    def _execute_output(
        self,
        snapshot: DocumentBundleSnapshotBinding,
        output_id: str,
    ) -> DocumentBundleOutputResult:
        self.snapshot_guard.assert_source_current(snapshot)
        exporter = self.exporters[output_id]
        try:
            paths = tuple(Path(path) for path in exporter.export(snapshot))
            self._validate_paths(paths)
        except Exception as exc:
            message = str(exc).strip() or exc.__class__.__name__
            return DocumentBundleOutputResult(
                output_id=output_id,
                error_message=f"{exc.__class__.__name__}: {message}",
            )
        return DocumentBundleOutputResult(output_id=output_id, paths=paths)

    def _validate_registry(self, snapshot: DocumentBundleSnapshotBinding) -> None:
        missing = [
            output_id
            for output_id in snapshot.request.output_ids
            if output_id not in self.exporters
        ]
        if missing:
            raise DocumentBundleOrchestrationError(
                "No exporter registered for: " + ", ".join(missing)
            )

        mismatched = [
            output_id
            for output_id in snapshot.request.output_ids
            if self.exporters[output_id].output_id != output_id
        ]
        if mismatched:
            raise DocumentBundleOrchestrationError(
                "Exporter registration key does not match exporter output_id: "
                + ", ".join(mismatched)
            )

    @staticmethod
    def _validate_paths(paths: tuple[Path, ...]) -> None:
        if not paths:
            raise DocumentBundleOrchestrationError(
                "exporter did not produce any output files"
            )
        resolved = tuple(path.resolve() for path in paths)
        if len(set(resolved)) != len(resolved):
            raise DocumentBundleOrchestrationError(
                "exporter returned duplicate output files"
            )
        for path in paths:
            if not path.is_file() or path.stat().st_size <= 0:
                raise DocumentBundleOrchestrationError(
                    f"exporter did not create a non-empty file: {path}"
                )
