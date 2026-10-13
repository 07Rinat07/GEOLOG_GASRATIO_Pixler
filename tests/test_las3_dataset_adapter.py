from pathlib import Path

import numpy as np
import pytest

from geoworkbench.data.format_capabilities import CapabilityLevel
from geoworkbench.data.las3_dataset_adapter import import_las3_scalar_dataset
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
    np.testing.assert_array_equal(result.dataset.depth, [1670.0, 1669.875, 1669.75])
    by_name = {curve.metadata.original_mnemonic: curve for curve in result.dataset.curves.values()}
    assert set(by_name).isdisjoint({"CDES", "NMR[1]", "NMR[2]", "NMR[3]", "NMR[4]", "NMR[5]"})
    np.testing.assert_array_equal(by_name["DT"].values, [123.45, 123.45, 123.45])
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
    np.testing.assert_array_equal(dataset.depth, result.dataset.depth)
    for key, curve in result.dataset.curves.items():
        np.testing.assert_array_equal(dataset.curves[key].values, curve.values)
        assert dataset.curves[key].metadata.unit == curve.metadata.unit
    assert reopened.source_documents[dataset.dataset_id].to_bytes() == original
    assert reopened.import_reports[dataset.dataset_id].issues == result.report.issues
    assert reopened.import_reports[dataset.dataset_id].source.sha256 == result.report.source.sha256
    assert source.read_bytes() == original
