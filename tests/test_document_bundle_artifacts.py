from __future__ import annotations

import pytest

from geoworkbench.domain.document_bundle import (
    DocumentBundleOutputFormat,
    DocumentBundleOutputSpec,
    DocumentBundleRequest,
    DocumentBundleScope,
    DocumentBundleScopeKind,
)
from geoworkbench.services.document_bundle_artifacts import (
    DocumentBundleArtifactExpansionError,
    expand_document_bundle_artifacts,
)


def _request(
    *,
    languages: tuple[str, ...] = ("ru",),
    orientations: tuple[str, ...] = ("portrait",),
    output_specs: tuple[DocumentBundleOutputSpec, ...] | None = None,
) -> DocumentBundleRequest:
    specs = output_specs or (
        DocumentBundleOutputSpec(
            output_id="masterlog",
            exporter_kind="masterlog",
            source_id="template-1",
            dataset_id="dataset-1",
            file_format=DocumentBundleOutputFormat.PDF,
            target_name="masterlog.pdf",
        ),
    )
    return DocumentBundleRequest(
        well_id="well-1",
        output_ids=tuple(spec.output_id for spec in specs),
        languages=languages,
        orientations=orientations,
        scope=DocumentBundleScope(DocumentBundleScopeKind.WHOLE_WELL),
        output_specs=specs,
    )


def test_single_variant_preserves_explicit_target_name() -> None:
    artifacts = expand_document_bundle_artifacts(_request())

    assert len(artifacts) == 1
    artifact = artifacts[0]
    assert artifact.artifact_id == "masterlog:ru:portrait"
    assert artifact.target_name == "masterlog.pdf"
    assert artifact.language == "ru"
    assert artifact.orientation == "portrait"


def test_artifact_expansion_is_output_language_orientation_ordered() -> None:
    artifacts = expand_document_bundle_artifacts(
        _request(
            languages=("ru", "en"),
            orientations=("portrait", "landscape"),
        )
    )

    assert [
        (item.artifact_id, item.target_name)
        for item in artifacts
    ] == [
        ("masterlog:ru:portrait", "masterlog__ru_portrait.pdf"),
        ("masterlog:ru:landscape", "masterlog__ru_landscape.pdf"),
        ("masterlog:en:portrait", "masterlog__en_portrait.pdf"),
        ("masterlog:en:landscape", "masterlog__en_landscape.pdf"),
    ]


def test_artifact_expansion_preserves_bound_output_parameters() -> None:
    artifacts = expand_document_bundle_artifacts(_request())
    artifact = artifacts[0]

    assert artifact.exporter_kind == "masterlog"
    assert artifact.source_id == "template-1"
    assert artifact.dataset_id == "dataset-1"
    assert artifact.file_format is DocumentBundleOutputFormat.PDF


def test_artifact_expansion_rejects_target_collisions_case_insensitively() -> None:
    specs = (
        DocumentBundleOutputSpec(
            output_id="first",
            exporter_kind="report",
            source_id="report-1",
            file_format=DocumentBundleOutputFormat.PDF,
            target_name="Report.pdf",
        ),
        DocumentBundleOutputSpec(
            output_id="second",
            exporter_kind="report",
            source_id="report-2",
            file_format=DocumentBundleOutputFormat.PDF,
            target_name="report.pdf",
        ),
    )

    with pytest.raises(DocumentBundleArtifactExpansionError, match="duplicate artifact target"):
        expand_document_bundle_artifacts(_request(output_specs=specs))


def test_artifact_expansion_requires_bound_output_specs() -> None:
    request = DocumentBundleRequest(
        well_id="well-1",
        output_ids=("masterlog",),
        languages=("ru",),
        orientations=("portrait",),
        scope=DocumentBundleScope(DocumentBundleScopeKind.WHOLE_WELL),
    )

    with pytest.raises(DocumentBundleArtifactExpansionError, match="output_specs"):
        expand_document_bundle_artifacts(request)
