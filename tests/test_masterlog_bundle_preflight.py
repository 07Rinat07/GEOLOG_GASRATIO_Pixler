from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from geoworkbench.domain.document_bundle import (
    DocumentBundleOutputFormat,
    DocumentBundleOutputSpec,
    DocumentBundleRequest,
    DocumentBundleScope,
    DocumentBundleScopeKind,
)
from geoworkbench.domain.models import (
    CalculationState,
    Dataset,
    DatasetKind,
    DepthDomain,
    MasterlogColumnTemplate,
    MasterlogTemplate,
    Project,
    Well,
)
from geoworkbench.project.document_bundle_preflight import (
    DocumentBundlePreflightCategory,
)
from geoworkbench.project.document_bundle_snapshot import (
    DocumentBundleSnapshotBinding,
)
from geoworkbench.project.document_bundle_snapshot_reader import (
    LoadedDocumentBundleSnapshot,
)
from geoworkbench.project.masterlog_bundle_preflight import (
    MasterlogBundlePreflightValidator,
)
from geoworkbench.storage.project_codec import ProjectDocument


@dataclass
class StaticLoader:
    loaded: LoadedDocumentBundleSnapshot

    def load(self, _snapshot):
        return self.loaded


def _fixture(
    tmp_path: Path,
    *,
    include_curve: bool = True,
    curve_state: CalculationState = CalculationState.CURRENT,
    scope: DocumentBundleScope | None = None,
) -> tuple[
    DocumentBundleSnapshotBinding,
    DocumentBundleOutputSpec,
    LoadedDocumentBundleSnapshot,
]:
    dataset = Dataset(
        "dataset-1",
        "Dataset",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.array([1000.0, 1050.0, 1100.0]),
    )
    if include_curve:
        curve = dataset.upsert_curve(
            "C1",
            np.array([1.0, 2.0, 3.0]),
            unit="ppm",
        )
        curve.state = curve_state

    well = Well(
        "well-1",
        "Well",
        datasets={dataset.dataset_id: dataset},
        content_revision=9,
    )
    template = MasterlogTemplate(
        "template-1",
        "Masterlog",
        page_format="A4",
        columns=[
            MasterlogColumnTemplate(
                "gas",
                "Gas",
                "curves",
                50.0,
                curve_mnemonics=["C1"],
            )
        ],
    )
    project = Project(
        "project-1",
        "Project",
        wells={well.well_id: well},
        masterlog_templates={template.template_id: template},
        save_revision=4,
    )
    output = DocumentBundleOutputSpec(
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
        languages=("ru",),
        orientations=("portrait",),
        scope=scope or DocumentBundleScope(DocumentBundleScopeKind.WHOLE_WELL),
        output_specs=(output,),
    )
    snapshot = DocumentBundleSnapshotBinding(
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
    loaded = LoadedDocumentBundleSnapshot(
        binding=snapshot,
        document=ProjectDocument(project),
    )
    return snapshot, output, loaded


def test_masterlog_preflight_accepts_current_resolved_dependencies(tmp_path: Path) -> None:
    snapshot, output, loaded = _fixture(tmp_path)

    issues = MasterlogBundlePreflightValidator(StaticLoader(loaded)).validate(
        snapshot,
        output,
    )

    assert issues == ()


def test_masterlog_preflight_blocks_unresolved_curve_dependency(tmp_path: Path) -> None:
    snapshot, output, loaded = _fixture(tmp_path, include_curve=False)

    issues = MasterlogBundlePreflightValidator(StaticLoader(loaded)).validate(
        snapshot,
        output,
    )

    assert any(
        issue.code == "masterlog.dependencies_missing"
        and issue.category is DocumentBundlePreflightCategory.DEPENDENCY
        for issue in issues
    )


def test_masterlog_preflight_blocks_stale_calculation_dependency(tmp_path: Path) -> None:
    snapshot, output, loaded = _fixture(
        tmp_path,
        curve_state=CalculationState.STALE,
    )

    issues = MasterlogBundlePreflightValidator(StaticLoader(loaded)).validate(
        snapshot,
        output,
    )

    assert any(issue.code == "masterlog.dependencies_not_current" for issue in issues)


def test_masterlog_preflight_blocks_scope_outside_saved_dataset(tmp_path: Path) -> None:
    snapshot, output, loaded = _fixture(
        tmp_path,
        scope=DocumentBundleScope(
            DocumentBundleScopeKind.INTERVAL,
            top_depth=900.0,
            bottom_depth=1050.0,
        ),
    )

    issues = MasterlogBundlePreflightValidator(StaticLoader(loaded)).validate(
        snapshot,
        output,
    )

    assert any(issue.code == "masterlog.scope_outside_dataset" for issue in issues)
