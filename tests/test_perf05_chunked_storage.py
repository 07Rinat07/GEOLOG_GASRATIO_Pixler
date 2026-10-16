from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import numpy as np

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain, Project, Well
from geoworkbench.storage.atomic_json import save_project
from geoworkbench.storage.chunked_project_document import (
    ChunkedProjectDocumentCodec,
    STORAGE_MARKER,
)
from geoworkbench.storage.package_project_repository import (
    PACKAGE_FORMAT,
    PACKAGE_MANIFEST,
    PACKAGE_PROJECT,
    PACKAGE_VERSION,
    PackageProjectRepository,
)
from geoworkbench.storage.project_codec import ProjectDocument


def test_chunked_codec_externalizes_large_scalar_lists_and_round_trips(tmp_path: Path) -> None:
    project_path = tmp_path / PACKAGE_PROJECT
    original = {
        "project": {
            "datasets": [
                {
                    "depth": [1000.0, 1000.5, 1001.0, 1001.5, 1002.0],
                    "curves": {
                        "C1": [1.0, 2.0, None, 4.0, 5.0],
                        "metadata": [{"name": "C1"}, {"name": "C2"}],
                    },
                }
            ]
        }
    }
    project_path.write_text(json.dumps(original), encoding="utf-8")
    codec = ChunkedProjectDocumentCodec(chunk_threshold=4, chunk_size=2)

    encoded = codec.encode(project_path, tmp_path)
    stored = json.loads(project_path.read_text(encoding="utf-8"))

    assert encoded.chunked_list_count == 2
    assert encoded.chunk_count == 6
    assert encoded.value_count == 10
    assert STORAGE_MARKER in stored["project"]["datasets"][0]["depth"]
    assert STORAGE_MARKER in stored["project"]["datasets"][0]["curves"]["C1"]
    assert stored["project"]["datasets"][0]["curves"]["metadata"] == original["project"][
        "datasets"
    ][0]["curves"]["metadata"]

    decoded = codec.decode(project_path, tmp_path)

    assert decoded == encoded
    assert json.loads(project_path.read_text(encoding="utf-8")) == original


def test_package_v2_chunks_dataset_columns_and_recovers_pending_commit(tmp_path: Path, monkeypatch) -> None:
    package = tmp_path / "project.geologpkg"
    repository = PackageProjectRepository(
        chunk_codec=ChunkedProjectDocumentCodec(chunk_threshold=2, chunk_size=2)
    )
    dataset = Dataset(
        dataset_id="dataset-perf05",
        name="Dataset",
        kind=DatasetKind.GTI,
        depth_domain=DepthDomain.MD,
        depth=np.asarray([1000.0, 1000.5, 1001.0, 1001.5], dtype=float),
    )
    well = Well("well-perf05", "Well", datasets={dataset.dataset_id: dataset})
    document = ProjectDocument(
        project=Project("project-perf05", "PERF-05", wells={well.well_id: well})
    )

    def reject_monolithic_roundtrip(*args, **kwargs):
        raise AssertionError("Package save must chunk arrays directly")

    monkeypatch.setattr(repository.chunk_codec, "encode", reject_monolithic_roundtrip)
    repository.save(document, package)

    with ZipFile(package, "r") as archive:
        manifest = json.loads(archive.read(PACKAGE_MANIFEST).decode("utf-8"))
        archive_names = set(archive.namelist())
    assert manifest["format"] == PACKAGE_FORMAT
    assert manifest["package_version"] == PACKAGE_VERSION == 2
    assert manifest["storage"]["format"] == "geolog-chunked-json"
    assert manifest["storage"]["version"] == 1
    assert manifest["storage"]["chunk_count"] >= 2
    assert any(name.startswith("chunks/") for name in archive_names)

    pending = repository.pending_path(package)
    package.replace(pending)
    assert not package.exists()
    assert pending.exists()

    recovered = repository.load(package)

    assert recovered.project.project_id == "project-perf05"
    recovered_dataset = recovered.project.wells[well.well_id].datasets[dataset.dataset_id]
    assert np.array_equal(recovered_dataset.depth, dataset.depth)
    assert package.exists()
    assert not pending.exists()


def test_package_repository_reads_legacy_v1_monolithic_package(tmp_path: Path) -> None:
    project_path = tmp_path / PACKAGE_PROJECT
    save_project(Project("legacy-project", "Legacy v1"), project_path)
    payload = project_path.read_bytes()
    manifest = {
        "format": PACKAGE_FORMAT,
        "package_version": 1,
        "project_path": PACKAGE_PROJECT,
        "entries": [
            {
                "path": PACKAGE_PROJECT,
                "size_bytes": len(payload),
                "sha256": sha256(payload).hexdigest(),
            }
        ],
    }
    package = tmp_path / "legacy.geologpkg"
    with ZipFile(package, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(PACKAGE_MANIFEST, json.dumps(manifest).encode("utf-8"))
        archive.writestr(PACKAGE_PROJECT, payload)

    loaded = PackageProjectRepository().load(package)

    assert loaded.project.project_id == "legacy-project"
    assert loaded.project.name == "Legacy v1"


def test_direct_numpy_chunks_match_legacy_json_chunks(tmp_path):
    direct = tmp_path / "direct"
    legacy = tmp_path / "legacy"
    direct.mkdir()
    legacy.mkdir()
    values = np.asarray([1.0, float("nan"), 0.0, -3.5, 7.0])
    codec = ChunkedProjectDocumentCodec(chunk_threshold=2, chunk_size=2)
    legacy_file = legacy / PACKAGE_PROJECT
    legacy_file.write_text(json.dumps({"values": values.tolist()}), encoding="utf-8")
    expected = codec.encode(legacy_file, legacy)
    encoded, actual = codec.encode_document({"values": values}, direct)
    assert actual == expected
    assert encoded == json.loads(legacy_file.read_text(encoding="utf-8"))
    for chunk in (legacy / "chunks").rglob("*.json"):
        assert chunk.read_bytes() == (direct / chunk.relative_to(legacy)).read_bytes()
    assert np.isnan(values[1])
    assert values[-1] == 7.0
