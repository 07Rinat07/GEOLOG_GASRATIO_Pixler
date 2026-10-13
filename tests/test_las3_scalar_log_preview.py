"""Contract tests for an explicitly limited LAS 3.0 scalar sample reader."""

from __future__ import annotations

from hashlib import sha256
import re

import pytest

from geoworkbench.data.las3_scalar_log_preview import (
    Las3ScalarPreviewError,
    read_las3_scalar_log_preview,
)
from geoworkbench.services.bounded_input import InputLimitError
from tools.fetch_external_format_fixtures import CORPUS


SOURCE = CORPUS / "las/3.0/sample_3.0.las"


def test_real_las3_log_scalar_values_units_and_excluded_fields_are_explicit() -> None:
    original = SOURCE.read_bytes()
    preview = read_las3_scalar_log_preview(SOURCE)

    assert preview.source_sha256 == sha256(original).hexdigest()
    assert preview.source_path == SOURCE
    assert preview.index_mnemonic == "DEPT"
    assert preview.sample_count == 3
    assert len(preview.fields) == 15
    assert len(preview.scalar_samples) == 9
    assert {field.mnemonic for field in preview.excluded_fields} == {
        "CDES", "NMR[1]", "NMR[2]", "NMR[3]", "NMR[4]", "NMR[5]",
    }
    assert {field.mnemonic: field.unit for field in preview.fields}["DT"] == "US/M"
    assert preview.null_value == -999.25
    assert preview.samples_for("DEPT") == (1670.0, 1669.875, 1669.75)
    assert preview.samples_for("DT") == (123.45, 123.45, 123.45)
    assert preview.samples_for("YME") == (1.45e12, 1.47e12, 2.85e12)
    with pytest.raises(KeyError):
        preview.samples_for("NMR[1]")
    with pytest.raises(KeyError):
        preview.samples_for("CDES")
    assert SOURCE.read_bytes() == original


def test_different_las3_fixture_is_not_promoted_to_explicit_log_set() -> None:
    for relative in (
        "las/3.0/good_file_ss.las",
        "las/3.0/multisection_curve_param_error.las",
    ):
        source = CORPUS / relative
        original = source.read_bytes()
        with pytest.raises(Las3ScalarPreviewError, match="Expected one"):
            read_las3_scalar_log_preview(source)
        assert source.read_bytes() == original


@pytest.mark.parametrize(
    ("transform", "pattern"),
    [
        (
            lambda raw: raw.replace(
                b"1670.000,123.450", b"1670.000,NOT_A_NUMBER", 1
            ),
            "Non-numeric scalar value",
        ),
        (
            lambda raw: raw.replace(
                b"DOLOMITE WI/VUGS,10,12", b"DOLOMITE WI/VUGS,10,12,EXTRA", 1
            ),
            "column mismatch",
        ),
        (
            lambda raw: re.sub(
                rb"(WRAP\.\s*)NO", rb"\g<1>YES", raw, count=1
            ),
            "WRAP=NO",
        ),
        (
            lambda raw: re.sub(
                rb"(DLM\s*\.\s*)COMMA", rb"\g<1>SPACE", raw, count=1
            ),
            "DLM=COMMA",
        ),
        (
            lambda raw: raw + b"\n~Log_Data | Log_Definition\n",
            "Expected one",
        ),
    ],
)
def test_malformed_or_unsupported_log_data_fails_closed_without_source_changes(
    tmp_path, transform, pattern: str
) -> None:
    original = SOURCE.read_bytes()
    changed = transform(original)
    assert changed != original, "the regression must actually corrupt the fixture"
    copied = tmp_path / "changed.las"
    copied.write_bytes(changed)
    with pytest.raises(Las3ScalarPreviewError, match=pattern):
        read_las3_scalar_log_preview(copied)
    assert copied.read_bytes() == changed
    assert SOURCE.read_bytes() == original


def test_las3_scalar_preview_rejects_row_budget_and_oversized_source() -> None:
    original = SOURCE.read_bytes()
    with pytest.raises(Las3ScalarPreviewError, match="row cap"):
        read_las3_scalar_log_preview(SOURCE, max_rows=2)
    with pytest.raises(InputLimitError):
        read_las3_scalar_log_preview(SOURCE, max_bytes=512)
    for invalid in (0, -1, True):
        with pytest.raises(ValueError, match="max_rows"):
            read_las3_scalar_log_preview(SOURCE, max_rows=invalid)
    assert SOURCE.read_bytes() == original
