from __future__ import annotations

from pathlib import Path

import numpy as np

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetIndex,
    DatasetKind,
    new_id,
)


def create_dataset_copy(
    source: Dataset,
    *,
    name: str,
    kind: DatasetKind = DatasetKind.DERIVED,
    provenance: str = "copy",
) -> Dataset:
    """Create a fully independent dataset with new IDs and copied arrays.

    The copy intentionally has no ``source_path``. Export code therefore cannot
    overwrite either original LAS by accident, and every curve/index belongs to
    the new dataset identity.
    """

    dataset_id = new_id()
    index_ids = {
        old_id: f"{dataset_id}:index:{position}"
        for position, old_id in enumerate(source.indexes, start=1)
    }
    indexes: dict[str, DatasetIndex] = {}
    for old_id, index in source.indexes.items():
        new_index_id = index_ids[old_id]
        indexes[new_index_id] = DatasetIndex(
            index_id=new_index_id,
            mnemonic=index.mnemonic,
            index_type=index.index_type,
            role=index.role,
            unit=index.unit,
            values=np.asarray(index.values).copy(),
            confidence=index.confidence,
            evidence=index.evidence + (f"{provenance}:{source.dataset_id}",),
            datetime_format=index.datetime_format,
            timezone=index.timezone,
        )

    result = Dataset(
        dataset_id=dataset_id,
        name=name.strip() or f"{source.name} — копия",
        kind=kind,
        depth_domain=source.depth_domain,
        depth=np.asarray(source.depth, dtype=np.float64).copy(),
        source_path=None,
        headers=dict(source.headers),
        parameters={
            **source.parameters,
            "COPY_SOURCE_DATASET": source.dataset_id,
            "COPY_SOURCE_PATH": str(Path(source.source_path) if source.source_path else ""),
            "COPY_PROVENANCE": provenance,
        },
        indexes=indexes,
        active_index_id=index_ids[source.active_index_id],  # type: ignore[index]
        version_headers=dict(source.version_headers),
    )

    for curve in source.curves.values():
        metadata = curve.metadata
        curve_id = new_id()
        result.curves[curve_id] = CurveData(
            metadata=CurveMetadata(
                curve_id=curve_id,
                original_mnemonic=metadata.original_mnemonic,
                canonical_mnemonic=metadata.canonical_mnemonic,
                unit=metadata.unit,
                description=metadata.description,
                source_dataset_id=dataset_id,
                provenance=f"{provenance}:{source.dataset_id}:{metadata.curve_id}",
            ),
            values=np.asarray(curve.values, dtype=np.float64).copy(),
            version=curve.version,
            state=curve.state,
        )
    return result
