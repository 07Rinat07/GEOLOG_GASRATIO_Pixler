from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from geoworkbench.calculations.opus_gasomer import (
    OPUS_GASOMER_INDICATORS,
    OPUS_GASOMER_PROFILE_ID,
    OPUS_GASOMER_PROFILE_VERSION,
    calculate_opus_gasomer_row,
    classify_opus_gasomer_value,
    load_opus_gasomer_profile,
    unique_opus_gasomer_mode,
)


ROOT = Path(__file__).resolve().parents[1]
CONTROL_PATH = ROOT / "tests" / "fixtures" / "opus_gasomer" / "workbook_control_v1.json"
PROFILE_PATH = ROOT / "src" / "geoworkbench" / "resources" / "opus_gasomer_profile_v1.json"
SOURCE_SHA256 = "bd70ce36ac9f99f56267c7fc24b51bf4ba0a26e2ffb86e768b282e1bd5201818"
PROFILE_SHA256 = "891c801f844c5bcd12a7bf87ceb3d5b026540dce6063dda60b085e068fdb6f02"
CONTROL_SHA256 = "400966ac853ac62793773a3c9d020534ff0a86b4e77a3f463792dc9b5f342306"


def _control() -> dict[str, object]:
    return json.loads(CONTROL_PATH.read_text(encoding="utf-8"))


def test_gasomer_fixture_pins_primary_workbook_identity_and_profile_contract() -> None:
    fixture = _control()
    profile = load_opus_gasomer_profile()

    assert fixture["source"]["sha256"] == SOURCE_SHA256
    assert profile["source"]["sha256"] == SOURCE_SHA256
    assert profile["profile_id"] == OPUS_GASOMER_PROFILE_ID
    assert profile["profile_version"] == OPUS_GASOMER_PROFILE_VERSION
    assert tuple(profile["formulas"]) == OPUS_GASOMER_INDICATORS
    assert PROFILE_PATH.is_file()


def test_gasomer_reproduces_primary_workbook_control_row() -> None:
    fixture = _control()
    raw = fixture["legacy_max_inputs"]

    result = calculate_opus_gasomer_row(
        raw["C1"],
        raw["C2"],
        raw["C3"],
        raw["C4"],
        raw["C5"],
        raw["TotalGas"],
    )

    np.testing.assert_allclose(
        result.normalized_percent,
        tuple(fixture["normalized_percent"].values()),
        rtol=0.0,
        atol=1e-13,
    )
    np.testing.assert_allclose(
        result.indicator_values,
        tuple(fixture["indicator_values"].values()),
        rtol=2e-15,
        atol=0.0,
    )
    assert result.indicator_votes == tuple(fixture["indicator_votes"].values())
    assert result.class_code == fixture["workbook_consensus"]["class_code"] == 2


@pytest.mark.parametrize("indicator", OPUS_GASOMER_INDICATORS)
def test_every_gasomer_boundary_is_inclusive_and_ordered(indicator: str) -> None:
    band = load_opus_gasomer_profile()["bands"][indicator]
    rules = band["rules"]
    direction = band["direction"]

    boundaries = [float(rule["boundary"]) for rule in rules]
    assert boundaries == sorted(boundaries, reverse=direction == "lower")
    for index, rule in enumerate(rules):
        boundary = float(rule["boundary"])
        expected = int(rule["class_code"])
        delta = max(abs(boundary) * 1e-9, 1e-12)
        assert classify_opus_gasomer_value(indicator, boundary) == expected
        if direction == "upper":
            assert classify_opus_gasomer_value(indicator, boundary - delta) == expected
            above = classify_opus_gasomer_value(indicator, boundary + delta)
            expected_above = (
                int(rules[index + 1]["class_code"])
                if index + 1 < len(rules)
                else int(band["fallback_class_code"])
            )
            assert above == expected_above
        else:
            assert classify_opus_gasomer_value(indicator, boundary + delta) == expected
            below = classify_opus_gasomer_value(indicator, boundary - delta)
            expected_below = (
                int(rules[index + 1]["class_code"])
                if index + 1 < len(rules)
                else int(band["fallback_class_code"])
            )
            assert below == expected_below


def test_ab4_erratum_makes_class_one_boundary_reachable() -> None:
    fixture = _control()["errata_control"]
    profile = load_opus_gasomer_profile()
    erratum = profile["errata"][0]

    assert fixture["source_expression"] == erratum["source_expression"]
    assert fixture["source_branch_reachable"] is False
    assert erratum["corrected_expression"] == "AB2>=250000"
    assert classify_opus_gasomer_value("OPUS_GM_4", 249999.999) == 2
    assert classify_opus_gasomer_value("OPUS_GM_4", 250000.0) == 1
    assert classify_opus_gasomer_value("OPUS_GM_4", 250000.001) == 1


def test_unique_mode_never_resolves_a_tie_arbitrarily() -> None:
    assert unique_opus_gasomer_mode([2, 2, 5, 5, 1]) == 7
    assert unique_opus_gasomer_mode([2, 2, 7, 7, 7]) == 7
    assert unique_opus_gasomer_mode([2, 2, 5, 5, 5]) == 5


def test_gasomer_fixture_files_are_stable_utf8_json() -> None:
    expected_hashes = {
        CONTROL_PATH: CONTROL_SHA256,
        PROFILE_PATH: PROFILE_SHA256,
    }
    for path, expected_hash in expected_hashes.items():
        raw = path.read_bytes()
        assert not raw.startswith(b"\xef\xbb\xbf")
        assert json.loads(raw.decode("utf-8"))
        assert hashlib.sha256(raw).hexdigest() == expected_hash
