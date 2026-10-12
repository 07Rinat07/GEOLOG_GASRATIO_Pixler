from __future__ import annotations

import pytest

from geoworkbench.data.format_capabilities import (
    CapabilityLevel,
    import_format_capabilities,
)


@pytest.mark.parametrize("version", ["1.2", "2.0", " 2.0 "])
def test_verified_las_versions_keep_raw_sources_immutable(version: str) -> None:
    capabilities = import_format_capabilities("las", las_version=version)
    assert capabilities.sample_read is CapabilityLevel.VERIFIED
    assert capabilities.project_edit is CapabilityLevel.VERIFIED
    assert capabilities.derived_export is CapabilityLevel.VERIFIED
    assert capabilities.source_write is CapabilityLevel.UNAVAILABLE


@pytest.mark.parametrize("version", [None, "", "3.0", "4.0", "2.0-vendor", "bogus"])
def test_unverified_las_versions_never_claim_full_support(version: str | None) -> None:
    capabilities = import_format_capabilities("LAS", las_version=version)
    assert capabilities.sample_read is not CapabilityLevel.VERIFIED
    assert capabilities.derived_export is not CapabilityLevel.VERIFIED
    assert capabilities.source_write is CapabilityLevel.UNAVAILABLE
    assert "round-trip" in capabilities.limitations[-1]


@pytest.mark.parametrize("version", ["2.1", "2.00", "1.2-vendor"])
def test_declared_other_las_2x_versions_are_limited(version: str) -> None:
    capabilities = import_format_capabilities("las", las_version=version)
    assert capabilities.sample_read is CapabilityLevel.LIMITED


@pytest.mark.parametrize("source_format", ["csv", "excel", " CSV "])
def test_tabular_adapters_have_project_edit_but_no_raw_writer(source_format: str) -> None:
    capabilities = import_format_capabilities(source_format)
    assert capabilities.metadata_preview is CapabilityLevel.VERIFIED
    assert capabilities.sample_read is CapabilityLevel.VERIFIED
    assert capabilities.project_edit is CapabilityLevel.VERIFIED
    assert capabilities.source_write is CapabilityLevel.UNAVAILABLE
    assert capabilities.derived_export is CapabilityLevel.LIMITED


@pytest.mark.parametrize("source_format", ["dlis", "", "hdf5", "las3"])
def test_unknown_format_rejected_instead_of_assuming_support(source_format: str) -> None:
    with pytest.raises(ValueError, match="Unknown import source format"):
        import_format_capabilities(source_format)


def test_las_version_cannot_be_passed_to_tabular_importer() -> None:
    with pytest.raises(ValueError, match="only valid for LAS"):
        import_format_capabilities("excel", las_version="2.0")


def test_invalid_las_version_type_rejected() -> None:
    with pytest.raises(ValueError, match="must be a string"):
        import_format_capabilities("las", las_version=2.0)  # type: ignore[arg-type]
