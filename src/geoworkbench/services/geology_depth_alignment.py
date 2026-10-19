"""Eligibility for aligning saved well MD observations without conversion."""

from __future__ import annotations

from geoworkbench.domain.models import Dataset, IndexRole, IndexType


def supports_saved_md_geology(dataset: Dataset) -> bool:
    """Stored geology has metre MD bounds, but no TVD/time/lag mapping.

    Lag output metadata is written by the existing correction service. Only
    its explicitly preserved source axis may retain the original alignment.
    """
    axis = dataset.active_index
    if "LAG_FORMULA_ID" in dataset.parameters or "LAG_PROFILE_ID" in dataset.headers:
        source_marker = (
            f"lag profile {dataset.headers.get('LAG_PROFILE_ID', '')} "
            f"revision {dataset.headers.get('LAG_REVISION', '')}: source"
        )
        if source_marker not in axis.evidence:
            return False
    return (
        axis.role is IndexRole.DEPTH
        and axis.index_type is IndexType.MD
        and (axis.unit or "").strip().casefold() in {"m", "meter", "metre", "meters", "metres"}
    )
