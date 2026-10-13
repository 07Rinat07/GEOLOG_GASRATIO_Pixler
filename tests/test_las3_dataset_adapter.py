from pathlib import Path

import numpy as np
import pytest

from geoworkbench.data.format_capabilities import CapabilityLevel
from geoworkbench.data.las3_dataset_adapter import import_las3_scalar_dataset
from geoworkbench.domain.models import DatasetKind, DepthDomain, IndexRole, IndexType
from geoworkbench.project.controller import ProjectController
from geoworkbench.project.session import ProjectSession
from tools.fetch_external_format_fixtures import CORPUS


@pytest.mark.parametrize("extension", [".geolog.json", ".geologpkg"])
def test_scalar_las3_dataset_reopens_with_source_and_exclusion_evidence(tmp_path: Path, extension: str) -> None:
    source = CORPUS / "las/3.0/sample_3.0.las"
    original = source.read_bytes()
    result = import_las3_scalar_dataset(source)
    assert result.source_document.to_bytes() == original
    assert result.report.capabilities.sample_read is CapabilityLevel.UNVERIFIED
    excluded = [issue for issue in result.report.issues if issue.code == "las3-excluded-field"]
    assert len(excluded) == 6
    assert result.dataset.version_headers["VERS"] == "3.0"
    assert result.dataset.kind is DatasetKind.GIS
    assert result.dataset.depth_domain is DepthDomain.MD
    assert result.dataset.active_index.role is IndexRole.DEPTH
    assert result.dataset.active_index.index_type is IndexType.MD
    assert result.dataset.active_index.unit == "M"
    assert result.dataset.curve_by_mnemonic("DEPT") is None
    assert len(result.dataset.curves) == 8
    assert len(result.dataset.source_revisions) == 1
    revision = result.dataset.source_revisions[0]
    assert revision.artifact_id == result.dataset.dataset_id
    assert revision.source_sha256 == result.source_document.sha256
    assert revision.size_bytes == len(original)
    assert revision.source_name == source.name
    assert revision.provider_kind == "las3_scalar_pilot"
    assert revision.rows_added == 3
    assert revision.rows_skipped == 0
    np.testing.assert_array_equal(result.dataset.depth, [1670.0, 1669.875, 1669.75])
    by_name = {curve.metadata.original_mnemonic: curve for curve in result.dataset.curves.values()}
    assert set(by_name).isdisjoint({"CDES", "NMR[1]", "NMR[2]", "NMR[3]", "NMR[4]", "NMR[5]"})
    np.testing.assert_array_equal(by_name["DT"].values, [123.45, 123.45, 123.45])
    assert all(
        curve.metadata.provenance == "source:las3-log_data-pilot"
        for curve in result.dataset.curves.values()
    )
    assert all(
        curve.metadata.source_dataset_id == result.dataset.dataset_id
        for curve in result.dataset.curves.values()
    )
    np.testing.assert_array_equal(by_name["YME"].values, [1.45e12, 1.47e12, 2.85e12])
    assert all(curve.values.shape == (3,) for curve in result.dataset.curves.values())
    session = ProjectSession()
    session.add_dataset(result.dataset, source_document=result.source_document, import_report=result.report)
    destination = tmp_path / ("scalar" + extension)
    ProjectController(session=session).save_project(destination)
    reopened = ProjectController().open_project(destination)
    dataset = reopened.current_dataset
    assert dataset is not None
    assert dataset.version_headers == result.dataset.version_headers
    assert dataset.kind is DatasetKind.GIS
    assert dataset.curve_by_mnemonic("DEPT") is None
    assert len(dataset.curves) == 8
    assert len(dataset.source_revisions) == 1
    restored_revision = dataset.source_revisions[0]
    assert restored_revision.source_sha256 == result.source_document.sha256
    assert restored_revision.artifact_id == dataset.dataset_id
    assert restored_revision.source_name == source.name
    assert restored_revision.provider_kind == "las3_scalar_pilot"
    assert restored_revision.rows_added == 3
    np.testing.assert_array_equal(dataset.depth, result.dataset.depth)
    for key, curve in result.dataset.curves.items():
        np.testing.assert_array_equal(dataset.curves[key].values, curve.values)
        assert dataset.curves[key].metadata.unit == curve.metadata.unit
        assert dataset.curves[key].metadata.provenance == curve.metadata.provenance
    assert reopened.source_documents[dataset.dataset_id].to_bytes() == original
    assert reopened.import_reports[dataset.dataset_id].issues == result.report.issues
    assert reopened.import_reports[dataset.dataset_id].source.sha256 == result.report.source.sha256
    assert source.read_bytes() == original



def test_las3_adapter_rejects_nonmetric_md_without_modifying_source(tmp_path: Path) -> None:
    source = CORPUS / "las/3.0/sample_3.0.las"
    original = source.read_bytes()
    changed = original.replace(b"DEPT .M", b"DEPT .FT", 1)
    assert changed != original
    copy = tmp_path / "wrong-depth-unit.las"
    copy.write_bytes(changed)

    with pytest.raises(ValueError, match="depth index in metres"):
        import_las3_scalar_dataset(copy)

    assert copy.read_bytes() == changed
    assert source.read_bytes() == original


def test_las3_adapter_rejects_index_only_dataset_without_false_channels(
    tmp_path: Path,
) -> None:
    raw = (
        b"~VERSION INFORMATION\n"
        b"VERS. 3.0\n"
        b"WRAP. NO\n"
        b"DLM. COMMA\n"
        b"~Well Information\n"
        b"NULL. -999.25\n"
        b"~Log_Definition\n"
        b"DEPT.M : DEPTH {F}\n"
        b"~Log_Data | Log_Definition\n"
        b"1670.0\n1669.875\n"
    )
    source = tmp_path / "index-only.las"
    source.write_bytes(raw)

    with pytest.raises(ValueError, match="no materializable channels"):
        import_las3_scalar_dataset(source)

    assert source.read_bytes() == raw
