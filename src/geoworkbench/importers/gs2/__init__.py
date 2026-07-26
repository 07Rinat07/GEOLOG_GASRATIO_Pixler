"""GeoScape II ``.gs2`` container support."""

from .container import (
    Gs2ContainerError,
    Gs2ContainerLimits,
    Gs2ContainerManifest,
    Gs2Member,
    Gs2MultipartSummary,
    Gs2TableSummary,
    extract_gs2,
    extract_gs2_metadata,
    extract_gs2_table,
    extract_gs2_tables,
    inspect_gs2,
)

__all__ = [
    "Gs2ContainerError",
    "Gs2ContainerLimits",
    "Gs2ContainerManifest",
    "Gs2Member",
    "Gs2MultipartSummary",
    "Gs2TableSummary",
    "extract_gs2",
    "extract_gs2_metadata",
    "extract_gs2_table",
    "extract_gs2_tables",
    "inspect_gs2",
]
