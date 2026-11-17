"""Exact-row Archie from two explicit, read-only native GIS channels."""
from dataclasses import replace

import numpy as np
import pytest

from geoworkbench.domain.models import (
    CalculationState, CurveData, CurveMetadata, Dataset, DatasetKind, DepthDomain, IndexType,
)
from geoworkbench.services import gis_archie_source_profile as module
from geoworkbench.services.gis_archie_profile import ArchieRowStatus
from geoworkbench.services.gis_archie_source_profile import evaluate_gis_archie_sources
from geoworkbench.services.petrophysical_reference_models import PetrophysicalQuality
from geoworkbench.services.semantic_channels import SemanticChannelDictionary


def _dataset(descending=False):
    semantic = SemanticChannelDictionary()
    curves = {}
    for key, mnemonic, unit, values in (
        ("phi", "NPHI", "v/v", [0.2, np.nan, 0.1, 0.2]),
        ("rt", "RT", "ohm.m", [10.0, 10.0, 0.2, -1.0]),
    ):
        binding = semantic.resolve(mnemonic, unit=unit)
        curves[key] = CurveData(
            CurveMetadata(key, mnemonic, binding.canonical_mnemonic, unit,
                          "Synthetic test input", "synthetic-run", "source:las", binding),
            np.array(values, dtype=float),
        )
    depths = np.array([100., 101., 102., 103.])
    if descending:
        depths[:] = depths[::-1].copy()
    return Dataset("gis", "Synthetic GIS", DatasetKind.GIS, DepthDomain.MD, depths, curves=curves)


def _evaluate(dataset, **changes):
    args = dict(
        porosity_curve_key="phi", resistivity_curve_key="rt", reviewer="Interpreter",
        applicability_reference="Synthetic clean Archie reservoir assumption",
        effective_porosity_reference="Independent effective-porosity calibration evidence",
        true_resistivity_reference="Independent Rt tool-depth evidence",
        alignment_reference="Synthetic exact same MD-row review",
        water_resistivity_reference="Synthetic Rw reference at reservoir temperature",
        md_top_m=100., md_base_m=103.,
        formation_water_resistivity_ohm_m=0.1, tortuosity_factor=1.,
        cementation_exponent=2., saturation_exponent=2.,
    )
    args.update(changes)
    return evaluate_gis_archie_sources(dataset, **args)


@pytest.mark.parametrize("descending", (False, True))
def test_live_sources_exact_rows_qc_missing_and_unclipped_sw(descending):
    dataset = _dataset(descending)
    depths = dataset.active_index.values
    phi, rt = dataset.curves["phi"].values, dataset.curves["rt"].values
    original = (depths.copy(), phi.copy(), rt.copy())
    result = _evaluate(dataset)
    assert [r.sample_index for r in result.rows] == [0, 1, 2, 3]
    assert [r.md_m for r in result.rows] == list(depths)
    assert result.md_bounds == (100., 103.)
    assert [r.status for r in result.rows] == [
        ArchieRowStatus.ESTIMATED, ArchieRowStatus.MISSING_INPUT,
        ArchieRowStatus.ESTIMATED, ArchieRowStatus.INVALID_INPUT,
    ]
    assert result.rows[0].estimate.value == pytest.approx(0.5)
    assert result.rows[1].estimate is None
    assert result.rows[2].estimate.value > 1
    assert result.rows[2].estimate.quality is PetrophysicalQuality.OUTSIDE_PHYSICAL_RANGE
    assert result.rows[3].estimate is None
    assert "Independent effective-porosity" in result.porosity_source
    assert "Independent Rt" in result.resistivity_source
    assert result.alignment_reference == "Synthetic exact same MD-row review"
    assert dataset.active_index.values is depths
    np.testing.assert_array_equal(depths, original[0])
    np.testing.assert_array_equal(phi, original[1])
    np.testing.assert_array_equal(rt, original[2])


def test_interval_and_missing_only_are_not_resampled_or_zero_filled():
    dataset = _dataset()
    result = _evaluate(dataset, md_top_m=100.5, md_base_m=102.5)
    assert [(r.sample_index, r.md_m) for r in result.rows] == [(1, 101.), (2, 102.)]
    assert result.rows[0].status is ArchieRowStatus.MISSING_INPUT
    assert result.rows[0].estimate is None
    with pytest.raises(ValueError, match="No actual"):
        _evaluate(dataset, md_top_m=100.1, md_base_m=100.9)


@pytest.mark.parametrize("changes", [
    {"porosity_curve_key": "rt"}, {"porosity_curve_key": "missing"},
    {"resistivity_curve_key": "missing"}, {"md_top_m": 104.},
    {"md_base_m": 99.}, {"md_top_m": np.nan}, {"md_top_m": None},
    {"md_base_m": "not a depth"}, {"md_top_m": True}, {"max_rows": 2},
    {"max_rows": True}, {"reviewer": ""}, {"alignment_reference": ""},
    {"effective_porosity_reference": ""}, {"true_resistivity_reference": ""},
    {"water_resistivity_reference": ""}, {"formation_water_resistivity_ohm_m": 0.},
])
def test_fail_closed_on_invalid_selection_scope_evidence_or_parameters(changes):
    with pytest.raises(ValueError):
        _evaluate(_dataset(), **changes)


@pytest.mark.parametrize("change", [
    "percent", "resistivity_unit", "metadata_semantic", "state", "axis",
    "different_run", "other_dataset_kind", "broken_axis", "all_missing",
])
def test_ineligible_gis_source_is_never_made_eligible_by_text_evidence(change):
    dataset = _dataset()
    phi = dataset.curves["phi"]
    rt = dataset.curves["rt"]
    if change == "percent":
        phi.metadata = replace(phi.metadata, unit="%")
    elif change == "resistivity_unit":
        rt.metadata = replace(rt.metadata, unit="kohm.m")
    elif change == "metadata_semantic":
        phi.metadata = replace(phi.metadata, semantic=None)
    elif change == "state":
        rt.state = CalculationState.STALE
    elif change == "axis":
        dataset.active_index.index_type = IndexType.TVD
    elif change == "different_run":
        rt.metadata = replace(rt.metadata, source_dataset_id="another-logging-run")
    elif change == "other_dataset_kind":
        dataset.kind = DatasetKind.GTI
    elif change == "broken_axis":
        dataset.active_index.values[2] = dataset.active_index.values[1]
    else:
        phi.values[:] = np.nan
    with pytest.raises(ValueError):
        _evaluate(dataset)


@pytest.mark.parametrize("change", ["phi", "rt", "axis", "meta", "replace_array", "outside_scope"])
def test_live_source_changes_during_evaluation_are_rejected(monkeypatch, change):
    dataset = _dataset()
    evaluate = module.evaluate_archie_rows

    def changed(*args, **kwargs):
        output = evaluate(*args, **kwargs)
        if change == "phi":
            dataset.curves["phi"].values[0] = 0.3
        elif change == "rt":
            dataset.curves["rt"].values[1] = 99.
        elif change == "axis":
            dataset.active_index.values[0] = 99.
        elif change == "meta":
            curve = dataset.curves["rt"]
            curve.metadata = replace(curve.metadata, provenance="another-source")
        elif change == "replace_array":
            dataset.curves["phi"].values = dataset.curves["phi"].values.copy()
        else:
            dataset.curves["rt"].values[3] = 20.
        return output

    monkeypatch.setattr(module, "evaluate_archie_rows", changed)
    with pytest.raises(ValueError, match="changed"):
        _evaluate(dataset, md_top_m=100., md_base_m=100.)
