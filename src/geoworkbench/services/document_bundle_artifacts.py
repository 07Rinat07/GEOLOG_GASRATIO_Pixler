from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from geoworkbench.domain.document_bundle import (
    DocumentBundleOutputFormat,
    DocumentBundleRequest,
)


class DocumentBundleArtifactExpansionError(ValueError):
    """Raised when logical bundle outputs cannot expand into unique artifacts."""


@dataclass(frozen=True, slots=True)
class DocumentBundleArtifactSpec:
    artifact_id: str
    output_id: str
    exporter_kind: str
    source_id: str
    dataset_id: str | None
    file_format: DocumentBundleOutputFormat
    language: str
    orientation: str
    target_name: str


def expand_document_bundle_artifacts(
    request: DocumentBundleRequest,
) -> tuple[DocumentBundleArtifactSpec, ...]:
    """Expand logical outputs into a deterministic language/orientation artifact matrix."""

    if not request.output_specs:
        raise DocumentBundleArtifactExpansionError(
            "bundle artifact expansion requires bound output_specs"
        )

    variant_count = len(request.languages) * len(request.orientations)
    artifacts: list[DocumentBundleArtifactSpec] = []
    seen_ids: set[str] = set()
    seen_targets: set[str] = set()

    for output in request.output_specs:
        for language in request.languages:
            for orientation in request.orientations:
                artifact_id = f"{output.output_id}:{language}:{orientation}"
                target_name = _variant_target_name(
                    output.target_name,
                    language=language,
                    orientation=orientation,
                    include_variant=variant_count > 1,
                )

                if artifact_id in seen_ids:
                    raise DocumentBundleArtifactExpansionError(
                        f"duplicate artifact ID: {artifact_id}"
                    )
                target_key = target_name.casefold()
                if target_key in seen_targets:
                    raise DocumentBundleArtifactExpansionError(
                        f"duplicate artifact target: {target_name}"
                    )

                seen_ids.add(artifact_id)
                seen_targets.add(target_key)
                artifacts.append(
                    DocumentBundleArtifactSpec(
                        artifact_id=artifact_id,
                        output_id=output.output_id,
                        exporter_kind=output.exporter_kind,
                        source_id=output.source_id,
                        dataset_id=output.dataset_id,
                        file_format=output.file_format,
                        language=language,
                        orientation=orientation,
                        target_name=target_name,
                    )
                )

    return tuple(artifacts)


def _variant_target_name(
    target_name: str,
    *,
    language: str,
    orientation: str,
    include_variant: bool,
) -> str:
    if not include_variant:
        return target_name

    target = Path(target_name)
    return f"{target.stem}__{language}_{orientation}{target.suffix}"
