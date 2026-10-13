"""Real LAS 3.0 section inventory tests without manufacturing parser support."""

from __future__ import annotations

from hashlib import sha256

import pytest

from geoworkbench.data.las3_section_inventory import (
    Las3InventoryError,
    Las3SectionKind,
    inspect_las3_sections,
)
from geoworkbench.services.bounded_input import InputLimitError
from tools.fetch_external_format_fixtures import CORPUS


@pytest.mark.parametrize(
    ("relative", "version", "minimum_sections", "multi_set"),
    [
        ("las/3.0/sample_3.0.las", "3.0", 15, True),
        ("las/3.0/good_file_ss.las", "3", 5, False),
        ("las/3.0/multisection_curve_param_error.las", "3.0", 10, True),
    ],
)
def test_original_las3_multi_set_inventory_reports_real_sections_without_write(
    relative: str, version: str, minimum_sections: int, multi_set: bool
) -> None:
    source = CORPUS / relative
    original = source.read_bytes()
    result = inspect_las3_sections(source)

    assert result.reported_version == version
    assert result.source_path == source
    assert result.source_size_bytes == len(original)
    assert result.source_sha256 == sha256(original).hexdigest()
    assert len(result.sections) >= minimum_sections
    assert result.is_multi_set is multi_set
    assert not result.unresolved_definitions
    assert result.sections[0].kind is Las3SectionKind.VERSION
    assert source.read_bytes() == original
    assert sum(item.size_bytes for item in result.sections) <= len(original)
    assert all(item.offset >= 0 and item.size_bytes > 0 for item in result.sections)
    assert [s.offset for s in result.sections] == sorted(s.offset for s in result.sections)


def test_las3_log_and_core_data_sets_preserve_indexed_names_and_definition_links() -> None:
    inventory = inspect_las3_sections(CORPUS / "las/3.0/sample_3.0.las")
    names = {section.name for section in inventory.sections}
    assert {"log_definition", "log_data", "core_definition", "core_data[1]",
            "core_data[2]"}.issubset(names)
    source_links = {
        (item.name, item.linked_definition) for item in inventory.data_sections
    }
    assert ("log_data", "log_definition") in source_links
    assert ("core_data[1]", "core_definition") in source_links
    assert ("core_data[2]", "core_definition") in source_links


def test_las3_multi_phase_sets_are_not_silently_mapped_to_log_channels() -> None:
    inventory = inspect_las3_sections(
        CORPUS / "las/3.0/multisection_curve_param_error.las"
    )
    names = {section.name for section in inventory.data_sections}
    assert {"phase_a_data", "phase_b_data"}.issubset(names)
    assert "log_data" not in names
    assert not inventory.unresolved_definitions


@pytest.mark.parametrize(
    "relative",
    ["las/1.2/sample.las", "las/2.0/sample_2.0.las"],
)
def test_earlier_las_versions_are_not_misreported_as_las3(relative: str) -> None:
    source = CORPUS / relative
    original = source.read_bytes()
    with pytest.raises(Las3InventoryError, match="LAS version is not 3.0"):
        inspect_las3_sections(source)
    assert source.read_bytes() == original


@pytest.mark.parametrize(
    "raw",
    [
        b"~V\nWRAP. NO\n~A\n1 2\n",
        b"~V\nVERS. 3.0\nVERS. 3.0\n~A\n1 2\n",
        b"~V\nVERS. 3.1\n~A\n1 2\n",
    ],
)
def test_unsupported_or_ambiguous_las3_headers_are_rejected(
    tmp_path, raw: bytes
) -> None:
    source = tmp_path / "invalid.las"
    source.write_bytes(raw)
    with pytest.raises(Las3InventoryError):
        inspect_las3_sections(source)
    assert source.read_bytes() == raw


def test_las3_metadata_preview_respects_file_byte_limit() -> None:
    source = CORPUS / "las/3.0/sample_3.0.las"
    with pytest.raises(InputLimitError):
        inspect_las3_sections(source, max_bytes=100)


def test_las3_metadata_preview_does_not_guess_missing_source_file(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        inspect_las3_sections(tmp_path / "does-not-exist.las")
