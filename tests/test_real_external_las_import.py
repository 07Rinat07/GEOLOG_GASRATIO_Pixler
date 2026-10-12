"""End-to-end LAS importer acceptance using byte-exact upstream reference files.

Unlike corpus integrity checks, these tests exercise the actual lasio-based
production adapter, import report, curves and source immutability. LAS 3.x
samples deliberately remain audit-only until importer support is established.
"""

from __future__ import annotations

from hashlib import sha256

import numpy as np
import pytest

from geoworkbench.data.format_capabilities import (
    CapabilityLevel,
    import_format_capabilities,
)
from geoworkbench.data.las_adapter import import_las_with_report
from geoworkbench.data.lossless_las import read_lossless_las
from tools.fetch_external_format_fixtures import CORPUS


@pytest.mark.parametrize(
    ("relative_path", "version", "expected_read", "wrap"),
    [
        ("las/1.2/sample.las", "1.2", CapabilityLevel.VERIFIED, "NO"),
        ("las/1.2/sample_wrapped.las", "1.2", CapabilityLevel.VERIFIED, "YES"),
        ("las/2.0/sample_2.0.las", "2.0", CapabilityLevel.VERIFIED, "NO"),
        ("las/2.0/sample_2.0_wrapped.las", "2.0", CapabilityLevel.VERIFIED, "YES"),
        ("las/2.0/sample_2.0_tab_dlm.las", "2.0", CapabilityLevel.VERIFIED, "NO"),
    ],
)
def test_real_reference_las_import_preserves_source_and_sample_grid(
    relative_path: str,
    version: str,
    expected_read: CapabilityLevel,
    wrap: str,
) -> None:
    source = CORPUS / relative_path
    original = source.read_bytes()
    result = import_las_with_report(source)
    dataset, report = result.dataset, result.report

    # The imported project dataset is not a rewrite of the original source.
    assert source.read_bytes() == original
    assert result.source_document.to_bytes() == original
    assert dataset.source_path == source
    assert report.source.path == source
    assert report.source.sha256 == sha256(original).hexdigest()
    assert report.source.size_bytes == len(original)
    assert report.source.las_version in ({version, "1.20"} if version == "1.2" else {version})
    assert report.source.wrap == wrap
    assert dataset.version_headers["VERS"] == report.source.las_version
    assert dataset.version_headers["WRAP"].upper() == wrap

    assert report.capabilities.sample_read in ({expected_read, CapabilityLevel.LIMITED} if version == "1.2" else {expected_read})
    assert report.capabilities.source_write is CapabilityLevel.UNAVAILABLE
    assert not report.has_errors
    assert dataset.depth.ndim == 1
    assert dataset.depth.size >= 3
    assert np.isfinite(dataset.depth).all()
    assert dataset.curves
    for curve in dataset.curves.values():
        assert curve.values.shape == dataset.depth.shape


@pytest.mark.parametrize(
    "relative_path",
    [
        "las/1.2/sample.las",
        "las/2.0/sample_2.0.las",
        "las/2.0/sample_2.0_tab_dlm.las",
    ],
)
def test_real_unwrapped_las_preserves_depth_and_curve_values(
    relative_path: str,
) -> None:
    dataset = import_las_with_report(CORPUS / relative_path).dataset
    np.testing.assert_allclose(
        dataset.depth,
        [1670.0, 1669.875, 1669.75],
        rtol=0,
        atol=1e-6,
    )
    dt = dataset.curve_by_mnemonic("DT")
    assert dt is not None
    np.testing.assert_allclose(
        dt.values,
        [123.450, 123.450, 123.450],
        rtol=0,
        atol=1e-6,
    )
    assert dt.metadata.unit


@pytest.mark.parametrize(
    "relative_path",
    [
        "las/3.0/sample_3.0.las",
        "las/3.0/good_file_ss.las",
        "las/3.0/multisection_curve_param_error.las",
    ],
)
def test_las3_real_fixture_metadata_is_preserved_without_claiming_import_support(
    relative_path: str,
) -> None:
    source = CORPUS / relative_path
    raw = source.read_bytes()
    doc = read_lossless_las(source)

    assert doc.to_bytes() == raw
    assert source.read_bytes() == raw
    assert len(doc.sections) >= 2
    capabilities = import_format_capabilities("las", las_version="3.0")
    assert capabilities.sample_read is CapabilityLevel.UNVERIFIED
    assert capabilities.source_write is CapabilityLevel.UNAVAILABLE


@pytest.mark.parametrize(
    "relative_path",
    [
        "dlis/7k_file.dlis",
        "lis79/inforec_01.lis",
        "segy/1x1.sgy",
        "segy/broken.sgy",
        "su/small.su",
    ],
)
def test_binary_format_fixtures_are_not_silently_reinterpreted_as_las(
    relative_path: str,
) -> None:
    from geoworkbench.data.las_adapter import LasImportError

    source = CORPUS / relative_path
    original = source.read_bytes()
    with pytest.raises(LasImportError, match="Ожидался LAS-файл"):
        import_las_with_report(source)
    assert source.read_bytes() == original
