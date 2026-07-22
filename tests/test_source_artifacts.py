import json

import pytest

from geoworkbench.data.lossless_las import parse_lossless_las
from geoworkbench.storage.source_artifacts import (
    SourceArtifactError,
    load_source_documents,
    save_source_documents,
)


def test_source_artifact_round_trip_is_content_addressed(tmp_path) -> None:
    project_path = tmp_path / "well.geolog.json"
    raw = b"~V\nVERS. 2.0\n~A\n100 1\n"
    document = parse_lossless_las(raw)

    manifest = save_source_documents(project_path, {"dataset-1": document})
    restored = load_source_documents(project_path, manifest)

    reference = manifest["dataset-1"]
    assert reference["sha256"] == document.sha256
    assert reference["path"].startswith("well.geolog.json.assets/")
    assert restored["dataset-1"].to_bytes() == raw
    assert len(list((tmp_path / "well.geolog.json.assets").glob("*.las"))) == 1


def test_source_artifact_save_reuses_verified_content(tmp_path) -> None:
    project_path = tmp_path / "well.geolog.json"
    document = parse_lossless_las(b"~A\n1\n")

    first = save_source_documents(project_path, {"one": document})
    second = save_source_documents(project_path, {"two": document})

    assert first["one"]["path"] == second["two"]["path"]
    assert len(list((tmp_path / "well.geolog.json.assets").iterdir())) == 1


def test_source_artifact_load_rejects_tampered_content(tmp_path) -> None:
    project_path = tmp_path / "well.geolog.json"
    manifest = save_source_documents(
        project_path,
        {"dataset-1": parse_lossless_las(b"~A\n1\n")},
    )
    artifact = tmp_path / manifest["dataset-1"]["path"]
    artifact.write_bytes(b"tampered")

    with pytest.raises(SourceArtifactError, match="Размер|SHA-256"):
        load_source_documents(project_path, manifest)


def test_source_artifact_load_rejects_path_traversal(tmp_path) -> None:
    project_path = tmp_path / "well.geolog.json"
    manifest = {
        "dataset-1": {
            "path": "../outside.las",
            "sha256": "0" * 64,
            "size_bytes": 0,
        }
    }

    with pytest.raises(SourceArtifactError, match="Недопустимый путь"):
        load_source_documents(project_path, manifest)


def test_source_artifact_manifest_is_json_serializable(tmp_path) -> None:
    manifest = save_source_documents(
        tmp_path / "well.geolog.json",
        {"dataset-1": parse_lossless_las(b"~A\n1\n")},
    )

    assert json.loads(json.dumps(manifest)) == manifest


def test_source_artifact_store_rejects_symlinked_assets_directory(
    tmp_path, symlink_or_skip
) -> None:
    project_path = tmp_path / "well.geolog.json"
    outside = tmp_path / "outside"
    outside.mkdir()
    symlink_or_skip(
        tmp_path / "well.geolog.json.assets",
        outside,
        target_is_directory=True,
    )

    with pytest.raises(SourceArtifactError, match="символической ссылкой"):
        save_source_documents(
            project_path,
            {"dataset-1": parse_lossless_las(b"~A\n1\n")},
        )
