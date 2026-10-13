"""Explicit LAS 3.0 scalar pilot -> project Dataset adapter.

This is not registered as a general LAS import route. Only the constrained
Log_Data/Log_Definition pilot is materialized. All unhandled LAS 3.0 sections
are retained in the original source snapshot, not reinterpreted as curves.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from geoworkbench.data.las3_scalar_log_preview import (
    Las3ScalarField,
    Las3ScalarLogPreview,
    read_las3_scalar_log_preview,
)
from geoworkbench.data.las3_section_inventory import inspect_las3_sections
from geoworkbench.data.lossless_las import LosslessLasDocument, read_lossless_las
from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetIndex,
    DatasetKind,
    DatasetSourceRevision,
    DepthDomain,
    IndexRole,
    IndexType,
    new_id,
)


@dataclass(frozen=True, slots=True)
class Las3DatasetPilotResult:
    dataset: Dataset
    preview: Las3ScalarLogPreview
    source_document: LosslessLasDocument
    excluded_fields: tuple[Las3ScalarField, ...]

    @property
    def source_sha256(self) -> str:
        return self.source_document.sha256


def import_las3_scalar_dataset_pilot(
    path: str | Path,
    *,
    max_bytes: int = 16 * 1024**2,
    max_rows: int = 100_000,
) -> Las3DatasetPilotResult:
    """Materialize only verified float scalar channels into a standalone GIS Dataset.

    No implicit format dispatch or source writing. The source is held in an
    immutable byte snapshot for future explicit project/package persistence.
    """
    preview = read_las3_scalar_log_preview(path, max_bytes=max_bytes, max_rows=max_rows)
    inventory = inspect_las3_sections(path, max_bytes=max_bytes)
    source_document = read_lossless_las(path, max_bytes=max_bytes)
    if not (
        source_document.sha256 == preview.source_sha256 == inventory.source_sha256
    ):
        raise ValueError("LAS 3 source changed during dataset pilot import")

    index_field = preview.fields[0]
    if index_field.mnemonic != "DEPT" or index_field.unit.upper() != "M":
        raise ValueError("LAS 3 pilot supports only DEPT measured in metres")
    depth = np.asarray(preview.samples_for("DEPT"), dtype=np.float64)
    if depth.shape != (preview.sample_count,) or not np.isfinite(depth).all():
        raise ValueError("LAS 3 index is not a finite one-dimensional MD grid")
    scalar = dict(preview.scalar_samples)
    dataset_id = new_id()
    index_id = f"{dataset_id}:primary-index"
    primary = DatasetIndex(
        index_id=index_id,
        mnemonic=index_field.mnemonic,
        index_type=IndexType.MD,
        role=IndexRole.DEPTH,
        unit=index_field.unit,
        values=depth,
        evidence=("LAS 3.0 Log_Definition explicit numeric DEPT",),
    )
    dataset = Dataset(
        dataset_id=dataset_id,
        name=Path(path).stem,
        kind=DatasetKind.GIS,
        depth_domain=DepthDomain.MD,
        depth=depth.copy(),
        source_path=Path(path),
        indexes={index_id: primary},
        active_index_id=index_id,
        version_headers={
            "VERS": inventory.reported_version,
            "WRAP": "NO",
            "DLM": "COMMA",
        },
    )

    for field in preview.fields[1:]:
        values = scalar.get(field.mnemonic)
        if values is None:
            continue
        array = np.asarray(values, dtype=np.float64)
        if array.shape != depth.shape:
            raise ValueError(f"LAS 3 channel/grid mismatch: {field.mnemonic}")
        curve_id = new_id()
        dataset.curves[curve_id] = CurveData(
            metadata=CurveMetadata(
                curve_id=curve_id,
                original_mnemonic=field.mnemonic,
                canonical_mnemonic=None,
                unit=field.unit or None,
                description=None,
                source_dataset_id=dataset_id,
                provenance="source:las3-log_data-pilot",
            ),
            values=array.copy(),
        )
    if not dataset.curves:
        raise ValueError("LAS 3 scalar pilot contains no materializable channels")

    dataset.source_revisions.append(
        DatasetSourceRevision(
            source_revision_id=f"primary:{dataset_id}:las3",
            artifact_id=dataset_id,
            source_name=Path(path).name,
            source_sha256=source_document.sha256,
            size_bytes=source_document.size_bytes,
            imported_at=datetime.now(timezone.utc).isoformat(),
            provider_kind="las3_scalar_pilot",
            provider_location=str(Path(path)),
            start_value=str(float(depth[0])),
            stop_value=str(float(depth[-1])),
            rows_added=int(depth.size),
            rows_skipped=0,
        )
    )
    return Las3DatasetPilotResult(
        dataset=dataset,
        preview=preview,
        source_document=source_document,
        excluded_fields=preview.excluded_fields,
    )
