from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from enum import StrEnum
from hashlib import sha256
import json
import os
from pathlib import Path
import stat
from typing import Any

from geoworkbench.project.document_bundle_orchestrator import DocumentBundleRun


DOCUMENT_BUNDLE_MANIFEST_SCHEMA_VERSION = 1


class DocumentBundleManifestError(RuntimeError):
    """Raised when a bundle run cannot be represented by a trustworthy manifest."""


class DocumentBundleManifestStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"


@dataclass(frozen=True, slots=True)
class DocumentBundleManifestArtifact:
    relative_path: str
    size_bytes: int
    sha256: str


@dataclass(frozen=True, slots=True)
class DocumentBundleManifestOutput:
    output_id: str
    succeeded: bool
    artifacts: tuple[DocumentBundleManifestArtifact, ...]
    error_message: str | None


@dataclass(frozen=True, slots=True)
class DocumentBundleManifestOutputSpec:
    output_id: str
    exporter_kind: str
    source_id: str
    dataset_id: str | None
    file_format: str
    target_name: str


@dataclass(frozen=True, slots=True)
class DocumentBundleManifest:
    schema_version: int
    status: DocumentBundleManifestStatus
    snapshot_id: str
    project_id: str
    save_revision: int
    well_id: str
    well_content_revision: int
    project_bundle_sha256: str
    output_ids: tuple[str, ...]
    languages: tuple[str, ...]
    orientations: tuple[str, ...]
    scope_kind: str
    scope_top_depth: float | None
    scope_bottom_depth: float | None
    output_specs: tuple[DocumentBundleManifestOutputSpec, ...]
    outputs: tuple[DocumentBundleManifestOutput, ...]
    manifest_sha256: str = ""

    def payload(self, *, include_digest: bool = True) -> dict[str, Any]:
        payload = _json_ready(asdict(self))
        if not include_digest:
            payload.pop("manifest_sha256", None)
        return payload

    def verify(self) -> bool:
        return bool(self.manifest_sha256) and self.manifest_sha256 == _manifest_digest(self)


def build_document_bundle_manifest(
    run: DocumentBundleRun,
    output_root: Path,
) -> DocumentBundleManifest:
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    resolved_root = root.resolve()

    outputs: list[DocumentBundleManifestOutput] = []
    seen_paths: set[Path] = set()
    for result in run.results:
        artifacts: tuple[DocumentBundleManifestArtifact, ...]
        if result.succeeded:
            artifact_items: list[DocumentBundleManifestArtifact] = []
            for path in result.paths:
                artifact_items.append(
                    _artifact_fingerprint(
                        Path(path),
                        resolved_root=resolved_root,
                        seen_paths=seen_paths,
                    )
                )
            artifacts = tuple(artifact_items)
        else:
            artifacts = ()
        outputs.append(
            DocumentBundleManifestOutput(
                output_id=result.output_id,
                succeeded=result.succeeded,
                artifacts=artifacts,
                error_message=result.error_message,
            )
        )

    request = run.snapshot.request
    output_specs = tuple(
        DocumentBundleManifestOutputSpec(
            output_id=spec.output_id,
            exporter_kind=spec.exporter_kind,
            source_id=spec.source_id,
            dataset_id=spec.dataset_id,
            file_format=spec.file_format.value,
            target_name=spec.target_name,
        )
        for spec in request.output_specs
    )
    unsigned = DocumentBundleManifest(
        schema_version=DOCUMENT_BUNDLE_MANIFEST_SCHEMA_VERSION,
        status=(
            DocumentBundleManifestStatus.COMPLETE
            if run.is_complete
            else DocumentBundleManifestStatus.PARTIAL
        ),
        snapshot_id=run.snapshot.snapshot_id,
        project_id=run.snapshot.project_id,
        save_revision=run.snapshot.save_revision,
        well_id=request.well_id,
        well_content_revision=run.snapshot.well_content_revision,
        project_bundle_sha256=run.snapshot.bundle_sha256,
        output_ids=request.output_ids,
        languages=request.languages,
        orientations=request.orientations,
        scope_kind=request.scope.kind.value,
        scope_top_depth=request.scope.top_depth,
        scope_bottom_depth=request.scope.bottom_depth,
        output_specs=output_specs,
        outputs=tuple(outputs),
    )
    return replace(unsigned, manifest_sha256=_manifest_digest(unsigned))


def write_document_bundle_manifest(
    manifest: DocumentBundleManifest,
    output_root: Path,
) -> Path:
    if not manifest.verify():
        raise DocumentBundleManifestError("Document bundle manifest digest is invalid")

    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    target = root / f"bundle-{manifest.snapshot_id}.manifest.json"
    temporary = target.with_name(f".{target.name}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            json.dump(
                manifest.payload(),
                stream,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return target


def _artifact_fingerprint(
    path: Path,
    *,
    resolved_root: Path,
    seen_paths: set[Path],
) -> DocumentBundleManifestArtifact:
    try:
        raw_stat = path.lstat()
    except OSError as exc:
        raise DocumentBundleManifestError(
            f"Bundle artifact is missing: {path}"
        ) from exc
    if stat.S_ISLNK(raw_stat.st_mode) or not stat.S_ISREG(raw_stat.st_mode):
        raise DocumentBundleManifestError(
            f"Bundle artifact must be a regular non-symlink file: {path}"
        )

    resolved = path.resolve()
    try:
        relative = resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise DocumentBundleManifestError(
            f"Bundle artifact is outside output root: {path}"
        ) from exc
    if resolved in seen_paths:
        raise DocumentBundleManifestError(
            f"Bundle artifact path is duplicated: {relative.as_posix()}"
        )
    seen_paths.add(resolved)

    payload = path.read_bytes()
    if not payload:
        raise DocumentBundleManifestError(
            f"Bundle artifact is empty: {relative.as_posix()}"
        )
    return DocumentBundleManifestArtifact(
        relative_path=relative.as_posix(),
        size_bytes=len(payload),
        sha256=sha256(payload).hexdigest(),
    )


def _manifest_digest(manifest: DocumentBundleManifest) -> str:
    canonical = json.dumps(
        manifest.payload(include_digest=False),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(canonical.encode("utf-8")).hexdigest()


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, StrEnum):
        return value.value
    return value
