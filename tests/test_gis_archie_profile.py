"""Archie exact-row data-only contract, independent of GUI and real LAS."""
from dataclasses import replace
from math import nan
import pytest

from geoworkbench.services.gis_archie_profile import (
    ArchieInputRow, ArchieRowStatus, evaluate_archie_rows,
)
from geoworkbench.services.petrophysical_reference_models import PetrophysicalQuality


def _evaluate(rows, **changes):
    params = dict(
        reviewer="Independent interpreter", applicability_reference="Synthetic clean formation only",
        porosity_source="Synthetic phi v/v", resistivity_source="Synthetic Rt ohm.m",
        water_resistivity_reference="Synthetic Rw at temperature",
        formation_water_resistivity_ohm_m=0.1, tortuosity_factor=1.0,
        cementation_exponent=2.0, saturation_exponent=2.0,
    )
    params.update(changes)
    return evaluate_archie_rows(rows, **params)


def test_exact_md_rows_missing_and_unclipped_qc():
    rows = (
        ArchieInputRow(2, 102.0, 0.2, 10.0),
        ArchieInputRow(3, 103.0, None, 10.0),
        ArchieInputRow(4, 104.0, 0.1, 0.2),
        ArchieInputRow(5, 105.0, nan, 10.0),
    )
    profile = _evaluate(rows)
    assert profile.method_id == "archie-water-saturation-1"
    assert profile.md_bounds == (102.0, 105.0)
    assert [r.sample_index for r in profile.rows] == [2, 3, 4, 5]
    assert [r.status for r in profile.rows] == [
        ArchieRowStatus.ESTIMATED, ArchieRowStatus.MISSING_INPUT,
        ArchieRowStatus.ESTIMATED, ArchieRowStatus.INVALID_INPUT,
    ]
    assert profile.rows[0].estimate.value == pytest.approx(0.5)
    assert profile.rows[1].estimate is None
    assert profile.rows[2].estimate.value > 1
    assert profile.rows[2].estimate.quality is PetrophysicalQuality.OUTSIDE_PHYSICAL_RANGE
    assert profile.rows[3].issue
    assert rows[0].porosity_fraction == 0.2


def test_descending_md_preserves_order_without_resampling():
    profile = _evaluate((ArchieInputRow(1, 105.0, 0.2, 10),
                         ArchieInputRow(2, 103.0, 0.2, 10)))
    assert profile.md_bounds == (103.0, 105.0)
    assert [r.md_m for r in profile.rows] == [105.0, 103.0]


@pytest.mark.parametrize("rows", [
    (), (ArchieInputRow(1, 100.0, 0.2, 10), ArchieInputRow(1, 101.0, 0.2, 10)),
    (ArchieInputRow(1, 100.0, 0.2, 10), ArchieInputRow(2, 100.0, 0.2, 10)),
    (ArchieInputRow(1, 100.0, 0.2, 10), ArchieInputRow(2, 102.0, 0.2, 10),
     ArchieInputRow(3, 101.0, 0.2, 10)),
    (ArchieInputRow(1, nan, 0.2, 10),),
])
def test_invalid_axis_and_rows_fail_closed(rows):
    with pytest.raises(ValueError):
        _evaluate(rows)


@pytest.mark.parametrize("change", [
    {"reviewer": " "}, {"applicability_reference": ""},
    {"porosity_source": ""}, {"resistivity_source": ""},
    {"water_resistivity_reference": ""}, {"formation_water_resistivity_ohm_m": 0},
    {"tortuosity_factor": 0}, {"cementation_exponent": 0},
    {"saturation_exponent": 0}, {"max_rows": 0},
])
def test_evidence_coefficients_and_budget_required(change):
    with pytest.raises(ValueError):
        _evaluate((ArchieInputRow(0, 100.0, None, None),), **change)


def test_row_budget_does_not_truncate():
    with pytest.raises(ValueError):
        _evaluate((ArchieInputRow(0, 100.0, 0.2, 10),
                   ArchieInputRow(1, 101.0, 0.2, 10)), max_rows=1)
