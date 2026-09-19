from __future__ import annotations

import json
from pathlib import Path

import pytest

from geoworkbench.domain.document_bundle import (
    DocumentBundleOutputFormat,
    DocumentBundleOutputSpec,
    DocumentBundleRequest,
    DocumentBundleScope,
    DocumentBundleScopeKind,
)
from geoworkbench.project.document_bundle_orchestrator import (
    DocumentBundleOutputResult,
    DocumentBundleRun,
)
from geoworkbench.project.document_bundle_snapshot import (
    DocumentBundleSnapshotBinding,
)
from geoworkbench.services.document_bundle_manifest import (
    DocumentBundleManifestError,
    DocumentBundleManifestStatus,
    build_document_bundle_manifest,
    write_document_bundle_manifest,
)


def _snapshot(tmp_path: Path) -> DocumentBundleSnapshotBinding:
    spec = DocumentBundleOutputSpec(
        output_id="masterlog",
        exporter_kind="masterlog",
        source_id="template-1",
        dataset_id="dataset-1",
        file_format=DocumentBundleOutputFormat.PDF,
        target_name="masterlog.pdf",
    )
    request = DocumentBundleRequest(
        well_id="well-1",
        output_ids=("masterlog",),
        languages=("ru", "en"),
        orientations=("portrait",),
        scope=DocumentBundleScope(
            DocumentBundleScopeKind.INTERVAL,
            top_depth=1000.0,
            bottom_depth=1100.0,
        ),
        output_specs=(spec,),
    )
    return DocumentBundleSnapshotBinding(
        snapshot_id="1" * 32,
        request=request,
        project_path=tmp_path / "project.geologpkg",
        project_id="project-1",
        save_revision=4,
        well_content_revision=9,
        storage_kind="package",
        path_id="a" * 64,
        bundle_sha256="b" * 64,
    )


def test_complete_bundle_manifest_fingerprints_all_artifacts(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path)
    pdf = tmp_path / "masterlog.pdf"
    sidecar = tmp_path / "masterlog.pdf.report.json"
    pdf.write_bytes(b"%PDF-bundle")
    sidecar.write_text('{"ok":true}', encoding="utf-8")
    run = DocumentBundleRun(
        snapshot=snapshot,
        results=(
            DocumentBundleOutputResult(
                output_id="masterlog",
                paths=(pdf, sidecar),
            ),
        ),
    )

    manifest = build_document_bundle_manifest(run, tmp_path)

    assert manifest.status is DocumentBundleManifestStatus.COMPLETE
    assert manifest.verify() is True
    assert manifest.snapshot_id == snapshot.snapshot_id
    assert manifest.save_revision == 4
    assert manifest.well_content_revision == 9
    assert manifest.scope_kind == "interval"
    assert manifest.scope_top_depth == 1000.0
    assert manifest.scope_bottom_depth == 1100.0
    assert manifest.output_specs[0].source_id == "template-1"
    assert [item.relative_path for item in manifest.outputs[0].artifacts] == [
        "masterlog.pdf",
        "masterlog.pdf.report.json",
    ]


def test_partial_bundle_manifest_never_reports_complete(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path)
    run = DocumentBundleRun(
        snapshot=snapshot,
        results=(
            DocumentBundleOutputResult(
                output_id="masterlog",
                error_message="RuntimeError: render failed",
            ),
        ),
    )

    manifest = build_document_bundle_manifest(run, tmp_path)

    assert manifest.status is DocumentBundleManifestStatus.PARTIAL
    assert manifest.outputs[0].succeeded is False
    assert manifest.outputs[0].artifacts == ()
    assert manifest.outputs[0].error_message == "RuntimeError: render failed"
    assert manifest.verify() is True


def test_bundle_manifest_rejects_artifact_outside_output_root(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path)
    outside = tmp_path.parent / "outside.pdf"
    outside.write_bytes(b"outside")
    run = DocumentBundleRun(
        snapshot=snapshot,
        results=(
            DocumentBundleOutputResult(
                output_id="masterlog",
                paths=(outside,),
            ),
        ),
    )

    with pytest.raises(DocumentBundleManifestError, match="outside output root"):
        build_document_bundle_manifest(run, tmp_path)


def test_bundle_manifest_rejects_duplicate_artifact_paths(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path)
    pdf = tmp_path / "masterlog.pdf"
    pdf.write_bytes(b"%PDF")
    run = DocumentBundleRun(
        snapshot=snapshot,
        results=(
            DocumentBundleOutputResult(
                output_id="masterlog",
                paths=(pdf, pdf),
            ),
        ),
    )

    with pytest.raises(DocumentBundleManifestError, match="duplicated"):
        build_document_bundle_manifest(run, tmp_path)


def test_bundle_manifest_writer_is_stable_and_self_verifying(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path)
    pdf = tmp_path / "masterlog.pdf"
    pdf.write_bytes(b"%PDF")
    run = DocumentBundleRun(
        snapshot=snapshot,
        results=(
            DocumentBundleOutputResult(
                output_id="masterlog",
                paths=(pdf,),
            ),
        ),
    )
    manifest = build_document_bundle_manifest(run, tmp_path)

    path = write_document_bundle_manifest(manifest, tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert path.name == f"bundle-{snapshot.snapshot_id}.manifest.json"
    assert payload["status"] == "complete"
    assert payload["manifest_sha256"] == manifest.manifest_sha256
    assert not path.with_name(f".{path.name}.tmp").exists()
