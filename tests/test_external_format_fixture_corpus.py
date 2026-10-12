"""Byte-exact, offline contracts for the pinned third-party format corpus."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tools.fetch_external_format_fixtures import (
    ALLOWED_REPOSITORIES,
    CORPUS,
    MAX_FILE_SIZE,
    _validate,
    blob_sha1,
)

MANIFEST = CORPUS / "manifest.json"


def _fixtures() -> list[dict[str, object]]:
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    return payload["fixtures"]


def test_complete_open_format_corpus_has_pinned_sources() -> None:
    items = _fixtures()
    assert len(items) == 16
    names = [str(item["destination"]) for item in items]
    assert len(set(names)) == len(names)
    assert {name.split("/")[0] for name in names} == {
        "las", "dlis", "lis79", "segy", "su",
    }
    assert {item["scenario"] for item in items} >= {"reference", "exploratory", "negative"}
    assert all(item["repository"] in ALLOWED_REPOSITORIES for item in items)


@pytest.mark.parametrize("entry", _fixtures(), ids=lambda entry: str(entry["destination"]))
def test_every_fixture_matches_original_upstream_blob(entry: dict[str, object]) -> None:
    path, url, size, expected_sha = _validate(entry)
    assert path.is_file(), f"Missing source bytes for {path.name}"
    payload = path.read_bytes()
    assert len(payload) == size <= MAX_FILE_SIZE
    assert blob_sha1(payload) == expected_sha
    assert len(hashlib.sha256(payload).hexdigest()) == 64
    assert url.startswith("https://raw.githubusercontent.com/")
    assert str(entry["revision"]) in url
    assert path.parent.is_relative_to(CORPUS)


def test_actual_las_versions_are_not_inferred_from_file_names() -> None:
    samples = {
        "las/1.2/sample.las": b"VERS.                  1.2",
        "las/2.0/sample_2.0.las": b"VERS.                          2.0",
        "las/3.0/sample_3.0.las": b"VERS.                          3.0",
    }
    for relative, marker in samples.items():
        raw = (CORPUS / relative).read_bytes()
        assert marker in raw


def test_non_las_fixtures_remain_binary_structures() -> None:
    sample = (CORPUS / "segy/1x1.sgy").read_bytes()
    assert len(sample) >= 3600 + 240
    assert b"VERS." not in sample[:3600]
    dlis = (CORPUS / "dlis/7k_file.dlis").read_bytes()
    lis = (CORPUS / "lis79/inforec_01.lis").read_bytes()
    assert b"VERS." not in dlis[:120]
    assert b"VERS." not in lis[:120]


@pytest.mark.parametrize("bad_path", ["../escape.las", "/root/absolute.las", "las/../escape.las",
                         "C:/outside.las", "las\\\\..\\\\escape.las"])
def test_manifest_rejects_unsafe_destination_paths(bad_path: str) -> None:
    entry = dict(_fixtures()[0], destination=bad_path)
    with pytest.raises(ValueError, match="Unsafe relative fixture path"):
        _validate(entry)


def test_manifest_rejects_unapproved_upstream_repository() -> None:
    entry = dict(_fixtures()[0], repository="not-trusted/other")
    with pytest.raises(ValueError, match="Unapproved source"):
        _validate(entry)


def test_blob_sha1_includes_real_nul_separator() -> None:
    assert blob_sha1(b"hello world") == "95d09f2b10159347eece71399a7e2e907ea3df4f"
