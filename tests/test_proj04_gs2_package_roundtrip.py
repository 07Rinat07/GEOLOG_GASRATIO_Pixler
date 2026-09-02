from __future__ import annotations

from pathlib import Path

import numpy as np

from geoworkbench.data.lossless_las import parse_lossless_las
from geoworkbench.domain.models import (
    Dataset,
    DatasetKind,
    DatasetSourceRevision,
    DepthDomain,
    Project,
    Well,
)
from geoworkbench.storage.package_project_repository import PackageProjectRepository
from geoworkbench.storage.project_codec import ProjectDocument


def test_gs2_source_registry_survives_project_package_round_trip(tmp_path: Path) -> None:
    dataset = Dataset(
        dataset_id="dataset-gs2",
        name="GS2 dataset",
        kind=DatasetKind.GTI,
        depth_domain=DepthDomain.MD,
        depth=np.asarray([100.0, 101.0], dtype=np.float64),
    )
    raw = b"\x00GS2\x01\xffbinary\r\npayload\x00"
    source_document = parse_lossless_las(raw)
    dataset.source_revisions.append(
        DatasetSourceRevision(
            source_revision_id="primary:dataset-gs2:test",
            artifact_id=dataset.dataset_id,
            source_name="source.gs2",
            source_sha256=source_document.sha256,
            size_bytes=source_document.size_bytes,
            imported_at="2026-09-02T00:00:00Z",
            provider_kind="gs2_file",
            provider_location="C:/data/source.gs2",
            start_value="100.0",
            stop_value="101.0",
            rows_added=2,
            rows_skipped=0,
        )
    )
    well = Well(
        well_id="well-1",
        name="Well",
        datasets={dataset.dataset_id: dataset},
    )
    document = ProjectDocument(
        project=Project(
            project_id="project-1",
            name="Project",
            wells={well.well_id: well},
        ),
        source_documents={dataset.dataset_id: source_document},
    )
    package = tmp_path / "project.geologpkg"
    repository = PackageProjectRepository()

    repository.save(document, package)
    restored = repository.load(package)

    restored_dataset = restored.project.wells[well.well_id].datasets[dataset.dataset_id]
    assert len(restored_dataset.source_revisions) == 1
    revision = restored_dataset.source_revisions[0]
    assert revision.source_name == "source.gs2"
    assert revision.artifact_id == dataset.dataset_id
    assert revision.source_sha256 == source_document.sha256
    assert revision.provider_kind == "gs2_file"

    restored_document = restored.source_documents[revision.artifact_id]
    assert restored_document.to_bytes() == raw
    assert restored_document.sha256 == revision.source_sha256
