"""Explicit opt-in Dataset adapter for the bounded LAS 3.0 scalar pilot."""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import numpy as np

from geoworkbench.data.las_adapter import LasImportResult
from geoworkbench.data.las3_scalar_log_preview import read_las3_scalar_log_preview
from geoworkbench.data.las_import_report import (
    LasImportIssue, LasImportReport, LasIssueSeverity, LasSourceSnapshot,
)
from geoworkbench.data.lossless_las import read_lossless_las
from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.services.depth_axis import analyze_depth_axis


def import_las3_scalar_dataset(
    path: str | Path, *, max_bytes: int = 16 * 1024**2, max_rows: int = 100_000,
) -> LasImportResult:
    """Materialize only the explicit scalar preview contract, never a raw rewrite.

    General LAS import dispatch is unchanged. Excluded text/array columns remain
    in mandatory report warnings and the exact immutable source document.
    """
    preview = read_las3_scalar_log_preview(path, max_bytes=max_bytes, max_rows=max_rows)
    document = read_lossless_las(path, max_bytes=max_bytes)
    if preview.source_sha256 != document.sha256:
        raise ValueError("Source changed between scalar preview and materialization")
    depth = np.asarray(preview.samples_for(preview.index_mnemonic), dtype=np.float64)
    if not np.isfinite(depth).all():
        raise ValueError("Scalar LAS3 pilot requires finite depth samples")
    index_field = next(field for field in preview.fields
                       if field.mnemonic == preview.index_mnemonic)
    if (index_field.mnemonic.upper() not in {"DEPT", "DEPTH"}
            or index_field.unit.casefold() != "m"):
        raise ValueError("Scalar LAS3 pilot requires an explicit depth index in metres")
    dataset = Dataset(str(uuid4()), Path(path).stem, DatasetKind.GTI, DepthDomain.MD,
                      depth.copy(), source_path=Path(path))
    dataset.version_headers = {"VERS": "3.0", "WRAP": "NO", "DLM": "COMMA"}
    dataset.headers = {"NULL": str(preview.null_value)} if preview.null_value is not None else {}
    dataset.upsert_curve(index_field.mnemonic, depth.copy(), unit=index_field.unit or None)
    scalar_names = {name for name, _ in preview.scalar_samples}
    for field in preview.fields:
        if field.mnemonic not in scalar_names or field.mnemonic == preview.index_mnemonic:
            continue
        values = np.asarray(preview.samples_for(field.mnemonic), dtype=np.float64)
        dataset.upsert_curve(field.mnemonic, values.copy(), unit=field.unit or None)
    source = LasSourceSnapshot(
        Path(path), document.size_bytes, document.sha256, document.encoding,
        document.newline_style.value, tuple(section.name for section in document.sections),
        "3.0", "NO", preview.null_value,
    )
    issues = [LasImportIssue("las3-scalar-pilot", LasIssueSeverity.WARNING,
                            "Limited LAS3 scalar pilot; general read/write support is unverified.")]
    issues.extend(LasImportIssue("las3-excluded-field", LasIssueSeverity.WARNING,
                                f"Excluded non-scalar field: {field.mnemonic} ({field.format_code})")
                  for field in preview.excluded_fields)
    report = LasImportReport(source, analyze_depth_axis(depth), tuple(issues))
    return LasImportResult(dataset, report, document)
