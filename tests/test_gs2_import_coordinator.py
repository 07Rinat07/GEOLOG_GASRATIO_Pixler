from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import numpy as np

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.importers.gs2.metadata import (
    Gs2Metadata,
    Gs2MetadataState,
    Gs2WellMetadata,
)
from geoworkbench.importers.paradox.models import ParadoxImportResult
from geoworkbench.project.gs2_import_coordinator import Gs2ImportCoordinator
from geoworkbench.services.import_jobs import ParadoxImportOutcome


class _Registration:
    def __init__(self) -> None:
        self.source: Path | None = None
        self.result: ParadoxImportResult | None = None

    def register_gs2(
        self,
        source: Path,
        result: ParadoxImportResult,
        *,
        review_dataset=None,
    ) -> ParadoxImportOutcome:
        self.source = source
        self.result = result
        return ParadoxImportOutcome(source, result=result, well_name="Well A")


def _result() -> ParadoxImportResult:
    dataset = Dataset(
        dataset_id="dataset-1",
        name="raw",
        kind=DatasetKind.USER,
        depth_domain=DepthDomain.MD,
        depth=np.asarray([1000.0, 1001.0], dtype=np.float64),
    )
    return ParadoxImportResult(
        dataset=dataset,
        table=cast(Any, object()),
        quality=cast(Any, object()),
        imported_channels=0,
        skipped_channels=0,
        skipped_records=0,
    )


def test_gs2_coordinator_owns_dataset_enrichment_and_registration(tmp_path: Path) -> None:
    source = tmp_path / "field_bundle.gs2"
    result = _result()
    metadata = Gs2Metadata(
        source=source,
        database_member="GS2.mdb",
        state=Gs2MetadataState.LOADED,
        adapter="test",
        database_tables=("WELL",),
        wells=(
            Gs2WellMetadata(
                identifier="well-42",
                name="Well 42",
                country="KZ",
                field="Field A",
                area="Block 7",
                company="Operator",
            ),
        ),
    )
    registration = _Registration()
    coordinator = Gs2ImportCoordinator(registration)

    outcome = coordinator.enrich_and_register(
        source,
        result,
        member_names=("GS2#12.DB", "GS2#13.DB"),
        table_label="GS2#12 (2 parts)",
        metadata=metadata,
        matched_metadata_channels=4,
        matched_sensor_channels=3,
    )

    dataset = result.dataset
    assert outcome.succeeded
    assert registration.source == source
    assert registration.result is result
    assert dataset.name == "field_bundle — GS2#12 (2 parts)"
    assert dataset.source_path == source.resolve()
    assert dataset.headers["WELL"] == "Well 42"
    assert dataset.headers["FLD"] == "Field A"
    assert dataset.parameters["SOURCE_FORMAT"] == "GeoScape II GS2"
    assert dataset.parameters["GS2_TABLE"] == "GS2#12.DB"
    assert dataset.parameters["GS2_TABLES"] == "GS2#12.DB; GS2#13.DB"
    assert dataset.parameters["GS2_MULTIPART"] == "true"
    assert dataset.parameters["GS2_METADATA_MATCHED_CHANNELS"] == "4"
    assert dataset.parameters["GS2_METADATA_ANNOTATED_CURVES"] == "0"
    assert dataset.parameters["GS2_SENSORS_MATCHED_CHANNELS"] == "3"
    assert dataset.parameters["GS2_METADATA_STATUS"] == "loaded"
    assert dataset.parameters["GS2_WELL_ID"] == "well-42"


def test_gs2_main_window_has_no_direct_dataset_writes() -> None:
    source = Path("src/geoworkbench/ui/main_window_drilling.py").read_text(encoding="utf-8")

    forbidden = (
        ".dataset.name =",
        ".dataset.source_path =",
        ".dataset.parameters.update(",
        ".dataset.headers.update(",
    )
    assert all(token not in source for token in forbidden)
