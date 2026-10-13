"""Fixture-backed LAS 3.0 Dataset and JSON/package persistence acceptance."""

from __future__ import annotations

from hashlib import sha256

import numpy as np
import pytest

from geoworkbench.data.las3_dataset_pilot import import_las3_scalar_dataset_pilot
from geoworkbench.data.las3_scalar_log_preview import Las3ScalarPreviewError
from geoworkbench.domain.models import (
    DatasetKind,
    DepthDomain,
    IndexRole,
    IndexType,
    Project,
    Well,
)
from geoworkbench.storage.json_project_repository import JsonProjectRepository
from geoworkbench.storage.package_project_repository import PackageProjectRepository
from geoworkbench.storage.project_codec import ProjectDocument
from tools.fetch_external_format_fixtures import CORPUS


SOURCE = CORPUS / "las/3.0/sample_3.0.las"


def _source_result():
    return import_las3_scalar_dataset_pilot(SOURCE)


def test_real_las3_scalar_channels_materialize_as_gis_dataset_without_loss() -> None:
    original = SOURCE.read_bytes()
    result = _source_result()
    dataset = result.dataset

    assert result.source_document.to_bytes() == original
    assert result.source_sha256 == sha256(original).hexdigest()
    assert dataset.source_path == SOURCE
    assert dataset.kind is DatasetKind.GIS
    assert dataset.depth_domain is DepthDomain.MD
    assert dataset.version_headers == {"VERS": "3.0", "WRAP": "NO", "DLM": "COMMA"}
    assert dataset.active_index.mnemonic == "DEPT"
    assert dataset.active_index.role is IndexRole.DEPTH
    assert dataset.active_index.index_type is IndexType.MD
    assert dataset.active_index.unit == "M"
    assert len(dataset.curves) == 8
    np.testing.assert_array_equal(dataset.depth, [1670.0, 1669.875, 1669.75])
    np.testing.assert_array_equal(dataset.active_index.values, dataset.depth)
    assert {item.metadata.original_mnemonic for item in dataset.curves.values()} == {
        "DT", "RHOB", "NPHI", "SFLU", "SFLA", "ILM", "ILD", "YME",
    }
    assert {item.mnemonic for item in result.excluded_fields} == {
        "CDES", "NMR[1]", "NMR[2]", "NMR[3]", "NMR[4]", "NMR[5]",
    }

    dt = dataset.curve_by_mnemonic("DT")
    assert dt is not None
    assert dt.metadata.unit == "US/M"
    assert dt.metadata.canonical_mnemonic is None
    assert dt.metadata.provenance == "source:las3-log_data-pilot"
    assert dt.metadata.source_dataset_id == dataset.dataset_id
    np.testing.assert_array_equal(dt.values, [123.45, 123.45, 123.45])
    modulus = dataset.curve_by_mnemonic("YME")
    assert modulus is not None
    assert modulus.metadata.unit == "PA"
    np.testing.assert_array_equal(modulus.values, [1.45e12, 1.47e12, 2.85e12])

    assert dataset.curve_by_mnemonic("CDES") is None
    assert dataset.curve_by_mnemonic("NMR[1]") is None
    assert len(dataset.source_revisions) == 1
    revision = dataset.source_revisions[0]
    assert revision.source_sha256 == sha256(original).hexdigest()
    assert revision.artifact_id == dataset.dataset_id
    assert revision.provider_kind == "las3_scalar_pilot"
    assert revision.rows_added == 3
    assert SOURCE.read_bytes() == original


@pytest.mark.parametrize(
    ("suffix", "repository"),
    [
        (".geolog.json", JsonProjectRepository),
        (".geologpkg", PackageProjectRepository),
    ],
)
def test_las3_scalar_dataset_survives_real_project_save_reopen(
    tmp_path, suffix, repository
) -> None:
    original = SOURCE.read_bytes()
    result = _source_result()
    dataset = result.dataset
    well = Well(
        well_id="test-las3-well",
        name="LAS 3 pilot well",
        datasets={dataset.dataset_id: dataset},
    )
    document = ProjectDocument(
        project=Project(
            project_id="test-las3-project",
            name="LAS 3 scalar pilot",
            wells={well.well_id: well},
        ),
        source_documents={dataset.dataset_id: result.source_document},
    )
    destination = tmp_path / ("pilot" + suffix)
    storage = repository()
    storage.save(document, destination)
    reloaded = storage.load(destination)
    restored = reloaded.project.wells[well.well_id].datasets[dataset.dataset_id]

    assert restored.kind is DatasetKind.GIS
    assert restored.depth_domain is DepthDomain.MD
    assert restored.active_index.index_type is IndexType.MD
    assert restored.active_index.unit == "M"
    np.testing.assert_array_equal(restored.depth, dataset.depth)
    assert restored.version_headers == dataset.version_headers
    assert len(restored.curves) == 8
    for name in ("DT", "RHOB", "NPHI", "SFLU", "SFLA", "ILM", "ILD", "YME"):
        before = dataset.curve_by_mnemonic(name)
        after = restored.curve_by_mnemonic(name)
        assert before is not None and after is not None
        assert before.metadata.unit == after.metadata.unit
        assert before.metadata.original_mnemonic == after.metadata.original_mnemonic
        np.testing.assert_array_equal(before.values, after.values)
    assert restored.curve_by_mnemonic("NMR[1]") is None
    assert restored.source_revisions[0].source_sha256 == result.source_sha256
    assert restored.source_revisions[0].artifact_id == dataset.dataset_id
    persisted_source = reloaded.source_documents[dataset.dataset_id]
    assert persisted_source.to_bytes() == original
    assert persisted_source.sha256 == result.source_sha256
    assert SOURCE.read_bytes() == original


@pytest.mark.parametrize(
    "relative",
    [
        "las/3.0/good_file_ss.las",
        "las/3.0/multisection_curve_param_error.las",
    ],
)
def test_las3_dataset_pilot_fails_closed_on_other_vendor_sets(relative: str) -> None:
    source = CORPUS / relative
    raw = source.read_bytes()
    with pytest.raises(Las3ScalarPreviewError):
        import_las3_scalar_dataset_pilot(source)
    assert source.read_bytes() == raw


def test_las3_dataset_pilot_rejects_wrong_index_uom_before_project_insertion(
    tmp_path,
) -> None:
    original = SOURCE.read_bytes()
    corrupted = original.replace(b"DEPT .M", b"DEPT .FT", 1)
    assert corrupted != original
    source = tmp_path / "wrong-unit.las"
    source.write_bytes(corrupted)
    with pytest.raises(ValueError, match="measured in metres"):
        import_las3_scalar_dataset_pilot(source)
    assert source.read_bytes() == corrupted
    assert SOURCE.read_bytes() == original
