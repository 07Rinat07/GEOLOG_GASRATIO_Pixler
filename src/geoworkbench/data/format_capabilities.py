"""Conservative, source-version-aware import capability declarations.

These describe the verified adapters, not a promise that arbitrary vendor files
can be parsed. Editing always targets a project dataset, never a raw source.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class CapabilityLevel(StrEnum):
    VERIFIED = "verified"
    LIMITED = "limited"
    UNVERIFIED = "unverified"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class ImportFormatCapabilities:
    source_format: str
    source_version: str | None
    metadata_preview: CapabilityLevel
    sample_read: CapabilityLevel
    project_edit: CapabilityLevel
    source_write: CapabilityLevel
    derived_export: CapabilityLevel
    limitations: tuple[str, ...]


def import_format_capabilities(
    source_format: str, *, las_version: str | None = None
) -> ImportFormatCapabilities:
    """Describe verified importer behavior without probing or changing source data.

    ``las_version`` must come from source header metadata, not a filename guess.
    An unknown LAS version is intentionally not promoted to verified support.
    """
    if not isinstance(source_format, str):
        raise ValueError("Source format must be a string")
    selected = source_format.strip().casefold()
    if selected not in {"las", "csv", "excel"}:
        raise ValueError(f"Unknown import source format: {source_format!r}")
    if selected != "las":
        if las_version is not None:
            raise ValueError("LAS version is only valid for LAS sources")
        return ImportFormatCapabilities(
            source_format=selected,
            source_version=None,
            metadata_preview=CapabilityLevel.VERIFIED,
            sample_read=CapabilityLevel.VERIFIED,
            project_edit=CapabilityLevel.VERIFIED,
            source_write=CapabilityLevel.UNAVAILABLE,
            derived_export=CapabilityLevel.LIMITED,
            limitations=(
                "Import requires operator selection of an index column.",
                "Export of a derived dataset does not round-trip the original file layout.",
                *(("Legacy XLS requires an external LibreOffice converter.",)
                  if selected == "excel" else ()),
            ),
        )
    if las_version is not None and not isinstance(las_version, str):
        raise ValueError("LAS version must be a string or None")
    version = las_version.strip() if las_version is not None else None
    version = version or None
    verified = version in {"1.2", "2.0"}
    limited = bool(version and (version.startswith("1.2") or version.startswith("2.")))
    read_level = (
        CapabilityLevel.VERIFIED if verified else
        CapabilityLevel.LIMITED if limited else CapabilityLevel.UNVERIFIED
    )
    return ImportFormatCapabilities(
        source_format="las",
        source_version=version,
        metadata_preview=read_level,
        sample_read=read_level,
        project_edit=read_level,
        source_write=CapabilityLevel.UNAVAILABLE,
        derived_export=CapabilityLevel.VERIFIED if verified else CapabilityLevel.LIMITED,
        limitations=(
            "LAS raw input is immutable; edits belong to the project dataset.",
            "New LAS output supports only LAS 1.2/2.0, with export-loss analysis.",
            *(() if verified else (
                "This LAS version/dialect has no verified lossless round-trip contract.",
            )),
        ),
    )
