from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from geoworkbench.domain.models import Dataset
from geoworkbench.importers.gs2.metadata import (
    Gs2Metadata,
    annotate_gs2_dataset,
    metadata_dataset_parameters,
    metadata_well_headers,
)
from geoworkbench.importers.paradox.models import ParadoxImportResult
from geoworkbench.services.import_jobs import (
    ImportDatasetReview,
    ParadoxImportOutcome,
)


class Gs2RegistrationPort(Protocol):
    def register_gs2(
        self,
        source: Path,
        result: ParadoxImportResult,
        *,
        review_dataset: ImportDatasetReview | None = None,
    ) -> ParadoxImportOutcome: ...


@dataclass(slots=True)
class Gs2ImportCoordinator:
    """Own GS2 Dataset enrichment and project registration outside Qt.

    The UI may select files/tables and collect review choices, but it must not write
    Dataset fields, metadata dictionaries or project collections directly.
    """

    registration: Gs2RegistrationPort

    def enrich_and_register(
        self,
        source: str | Path,
        result: ParadoxImportResult,
        *,
        member_names: tuple[str, ...],
        table_label: str,
        metadata: Gs2Metadata | None = None,
        matched_metadata_channels: int = 0,
        matched_sensor_channels: int = 0,
        review_dataset: ImportDatasetReview | None = None,
    ) -> ParadoxImportOutcome:
        if not member_names:
            raise ValueError("GS2 import requires at least one selected table")
        selected = Path(source)
        dataset = result.dataset
        if not isinstance(dataset, Dataset):
            raise TypeError("GS2 import result must contain Dataset")

        resolved = selected.resolve()
        dataset.name = f"{selected.stem} — {table_label}"
        dataset.source_path = resolved

        annotated_metadata_curves = 0
        if metadata is not None:
            annotated_metadata_curves = annotate_gs2_dataset(
                dataset,
                metadata,
                member_names[0],
            )
            dataset.parameters.update(metadata_dataset_parameters(metadata))
            dataset.headers.update(metadata_well_headers(metadata))

        dataset.parameters.update(
            {
                "SOURCE_FORMAT": "GeoScape II GS2",
                "SOURCE_FILE": str(resolved),
                "SOURCE_BUNDLE": selected.name,
                "GS2_TABLE": member_names[0],
                "GS2_TABLES": "; ".join(member_names),
                "GS2_MULTIPART": str(len(member_names) > 1).lower(),
                "GS2_METADATA_MATCHED_CHANNELS": str(matched_metadata_channels),
                "GS2_METADATA_ANNOTATED_CURVES": str(annotated_metadata_curves),
                "GS2_SENSORS_MATCHED_CHANNELS": str(matched_sensor_channels),
            }
        )
        return self.registration.register_gs2(
            selected,
            result,
            review_dataset=review_dataset,
        )


__all__ = ["Gs2ImportCoordinator", "Gs2RegistrationPort"]
