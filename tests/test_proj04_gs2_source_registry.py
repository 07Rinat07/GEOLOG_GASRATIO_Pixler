from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import numpy as np

from geoworkbench.data.las_import_report import LasImportReport
from geoworkbench.data.lossless_las import LosslessLasDocument
from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.importers.paradox.models import ParadoxImportResult
from geoworkbench.services.import_jobs import DatasetImportJobExecutor
from geoworkbench.storage.source_artifacts import (
    load_source_documents,
    save_source_documents,
)


@dataclass(frozen=True, slots=True)
class Registration:
    dataset: Dataset
    source_document: LosslessLasDocument | None
    import_report: LasImportReport | None
    create_new_well: bool


@dataclass
class RecordingImportPort:
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
                dataset=dataset,
                source_document=source_document,
                import_report=import_report,
                create_new_well=create_new_well,
            )
        )
        return "GS2 Well"


def test_gs2_uses_dataset_source_registry_and_binary_sidecar_round_trip(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.gs2"
    raw = b"\x00GS2\x01\xffbinary\r\npayload\x00"
    source.write_bytes(raw)
    dataset = Dataset(
        dataset_id="dataset-gs2",
        name="GS2 dataset",
        kind=DatasetKind.GTI,
        depth_domain=DepthDomain.MD,
        depth=np.asarray([100.0, 101.0], dtype=np.float64),
    )
    result = cast(ParadoxImportResult, SimpleNamespace(dataset=dataset))
    port = RecordingImportPort()

    outcome = DatasetImportJobExecutor(port).register_gs2(source, result)

    assert outcome.succeeded is True
    assert outcome.well_name == "GS2 Well"
    assert len(port.registrations) == 1
    registration = port.registrations[0]
    assert registration.dataset is dataset
    assert registration.create_new_well is True
    assert registration.import_report is None
    assert registration.source_document is not None
    assert registration.source_document.to_bytes() == raw

    assert len(dataset.source_revisions) == 1
    revision = dataset.source_revisions[0]
    assert revision.artifact_id == dataset.dataset_id
    assert revision.source_name == source.name
    assert revision.source_sha256 == registration.source_document.sha256
    assert revision.size_bytes == len(raw)
    assert revision.provider_kind == "gs2_file"
    assert revision.provider_location == str(source.resolve())
    assert revision.rows_added == len(dataset.active_index.values)
    assert revision.rows_skipped == 0

    project_path = tmp_path / "project.geolog.json"
    manifest = save_source_documents(
        project_path,
        {revision.artifact_id: registration.source_document},
    )
    restored = load_source_documents(project_path, manifest)

    assert restored[revision.artifact_id].to_bytes() == raw
    assert restored[revision.artifact_id].sha256 == revision.source_sha256
