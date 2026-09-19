from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from geoworkbench.domain.document_bundle import DocumentBundleRequest
from geoworkbench.project.document_bundle_orchestrator import DocumentBundleRun
from geoworkbench.services.document_bundle_manifest import (
    DocumentBundleManifest,
    build_document_bundle_manifest,
    write_document_bundle_manifest,
)


class DocumentBundleRunner(Protocol):
    """Application port implemented by the verified bundle service."""

    def execute(self, request: DocumentBundleRequest) -> DocumentBundleRun:
        """Execute one new bundle request."""

    def retry_failed(self, previous: DocumentBundleRun) -> DocumentBundleRun:
        """Retry failed outputs from the same immutable snapshot."""


@dataclass(frozen=True, slots=True)
class RecordedDocumentBundleExecution:
    run: DocumentBundleRun
    manifest: DocumentBundleManifest
    manifest_path: Path

    def __post_init__(self) -> None:
        if self.manifest.snapshot_id != self.run.snapshot.snapshot_id:
            raise ValueError("Recorded manifest must match the bundle run snapshot")
        if self.manifest_path.name != (
            f"bundle-{self.run.snapshot.snapshot_id}.manifest.json"
        ):
            raise ValueError("Recorded manifest path does not match the snapshot ID")


@dataclass(slots=True)
class RecordingDocumentBundleApplicationService:
    """Decorator that records every bundle run as an atomic signed manifest."""

    delegate: DocumentBundleRunner
    output_root: Path

    def execute(
        self,
        request: DocumentBundleRequest,
    ) -> RecordedDocumentBundleExecution:
        return self._record(self.delegate.execute(request))

    def retry_failed(
        self,
        previous: RecordedDocumentBundleExecution,
    ) -> RecordedDocumentBundleExecution:
        retried = self.delegate.retry_failed(previous.run)
        if retried.snapshot is not previous.run.snapshot:
            raise RuntimeError(
                "Bundle retry must preserve the exact captured snapshot"
            )
        return self._record(retried)

    def _record(
        self,
        run: DocumentBundleRun,
    ) -> RecordedDocumentBundleExecution:
        manifest = build_document_bundle_manifest(run, self.output_root)
        manifest_path = write_document_bundle_manifest(manifest, self.output_root)
        return RecordedDocumentBundleExecution(
            run=run,
            manifest=manifest,
            manifest_path=manifest_path,
        )
