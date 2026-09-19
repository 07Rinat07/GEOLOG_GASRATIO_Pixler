from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Protocol

from geoworkbench.domain.document_bundle import (
    DocumentBundleOutputFormat,
    DocumentBundleRequest,
)
from geoworkbench.project.document_bundle_orchestrator import (
    DocumentBundleExporter,
    DocumentBundleOrchestrator,
    DocumentBundleRun,
)
from geoworkbench.project.document_bundle_preflight import (
    DocumentBundlePreflightReport,
)
from geoworkbench.project.document_bundle_snapshot import (
    DocumentBundleSnapshotBinding,
)
from geoworkbench.project.document_bundle_snapshot_reader import (
    DocumentBundleSnapshotReader,
)
from geoworkbench.project.masterlog_bundle_exporter import (
    MasterlogPdfBundleExporter,
)


class DocumentBundleServiceError(RuntimeError):
    """Raised when a bundle request cannot be wired to supported exporters."""


class DocumentBundlePreflightFailed(DocumentBundleServiceError):
    """Raised before output execution when persisted preflight is not ready."""

    def __init__(self, report: DocumentBundlePreflightReport) -> None:
        self.report = report
        codes = ", ".join(issue.code for issue in report.blocking_issues)
        super().__init__(f"Document bundle preflight failed: {codes}")


class DocumentBundlePreflightGate(Protocol):
    def evaluate(
        self,
        snapshot: DocumentBundleSnapshotBinding,
    ) -> DocumentBundlePreflightReport:
        """Validate the persisted snapshot before any exporter is invoked."""


class DocumentBundleSnapshotGateway(Protocol):
    def capture(
        self,
        request: DocumentBundleRequest,
    ) -> DocumentBundleSnapshotBinding:
        """Capture one verified persisted project revision."""

    def assert_source_current(
        self,
        snapshot: DocumentBundleSnapshotBinding,
    ) -> None:
        """Raise when the persisted snapshot source no longer matches."""


class DocumentBundleExporterFactory(Protocol):
    def build(
        self,
        snapshot: DocumentBundleSnapshotBinding,
    ) -> Mapping[str, DocumentBundleExporter]:
        """Build logical output exporters for one immutable request."""


@dataclass(slots=True)
class DefaultDocumentBundleExporterFactory:
    """Production exporter registry for currently supported WELL-06 outputs."""

    output_directory: Path
    snapshot_reader: DocumentBundleSnapshotReader

    def build(
        self,
        snapshot: DocumentBundleSnapshotBinding,
    ) -> Mapping[str, DocumentBundleExporter]:
        if not snapshot.request.output_specs:
            raise DocumentBundleServiceError(
                "Document bundle execution requires bound output_specs"
            )

        exporters: dict[str, DocumentBundleExporter] = {}
        for spec in snapshot.request.output_specs:
            if spec.exporter_kind == "masterlog":
                if spec.file_format is not DocumentBundleOutputFormat.PDF:
                    raise DocumentBundleServiceError(
                        f"Masterlog output {spec.output_id!r} supports PDF only"
                    )
                exporters[spec.output_id] = MasterlogPdfBundleExporter(
                    output_id=spec.output_id,
                    output_directory=self.output_directory,
                    snapshot_loader=self.snapshot_reader,
                )
                continue
            raise DocumentBundleServiceError(
                f"Unsupported document bundle exporter kind: {spec.exporter_kind}"
            )
        return exporters


@dataclass(slots=True)
class DocumentBundleApplicationService:
    """Single application entry point for verified WELL-06 bundle execution."""

    snapshot_gateway: DocumentBundleSnapshotGateway
    exporter_factory: DocumentBundleExporterFactory
    preflight: DocumentBundlePreflightGate

    def execute(
        self,
        request: DocumentBundleRequest,
    ) -> DocumentBundleRun:
        snapshot = self.snapshot_gateway.capture(request)
        report = self.preflight.evaluate(snapshot)
        if not report.is_ready:
            raise DocumentBundlePreflightFailed(report)
        exporters = self.exporter_factory.build(snapshot)
        orchestrator = DocumentBundleOrchestrator(
            exporters=exporters,
            snapshot_guard=self.snapshot_gateway,
        )
        return orchestrator.execute(snapshot)

    def retry_failed(
        self,
        previous: DocumentBundleRun,
    ) -> DocumentBundleRun:
        report = self.preflight.evaluate(previous.snapshot)
        if not report.is_ready:
            raise DocumentBundlePreflightFailed(report)
        exporters = self.exporter_factory.build(previous.snapshot)
        orchestrator = DocumentBundleOrchestrator(
            exporters=exporters,
            snapshot_guard=self.snapshot_gateway,
        )
        return orchestrator.retry_failed(previous)
