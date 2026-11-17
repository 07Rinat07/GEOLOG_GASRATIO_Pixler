"""Fail-closed Archie handoff source stamp; synthetic GIS only."""
from dataclasses import replace

import numpy as np
import pytest

from geoworkbench.services.gis_archie_handoff import seal_archie_tablet_source
from test_gis_archie_source_profile import _dataset, _evaluate


@pytest.mark.parametrize("descending", (False, True))
@pytest.mark.parametrize("row", (0, 1, 2, 3))
def test_seal_records_exact_row_and_original_profile_without_mutation(descending, row):
    dataset = _dataset(descending)
    before = (dataset.active_index.values.copy(), dataset.curves["phi"].values.copy(),
              dataset.curves["rt"].values.copy())
    profile = _evaluate(dataset)
    seal = seal_archie_tablet_source(
        dataset, profile, porosity_curve_key="phi",
        resistivity_curve_key="rt", row_index=row,
    )
    assert seal.profile is profile and seal.dataset is dataset
    assert seal.row_index == row
    assert seal.is_current(dataset)
    np.testing.assert_array_equal(dataset.active_index.values, before[0])
    np.testing.assert_array_equal(dataset.curves["phi"].values, before[1])
    np.testing.assert_array_equal(dataset.curves["rt"].values, before[2])


@pytest.mark.parametrize("change", (
    "phi", "rt", "outside_interval", "depth", "new_depth_array", "new_curve_array",
    "metadata", "version", "state", "active_index", "dataset", "removed_curve",
))
def test_seal_invalidated_by_live_source_or_identity_change(change):
    dataset = _dataset()
    profile = _evaluate(dataset, md_top_m=100., md_base_m=100.)
    seal = seal_archie_tablet_source(
        dataset, profile, porosity_curve_key="phi", resistivity_curve_key="rt",
        row_index=0,
    )
    if change == "phi":
        dataset.curves["phi"].values[0] = 0.3
    elif change == "rt":
        dataset.curves["rt"].values[0] = 20.
    elif change == "outside_interval":
        dataset.curves["rt"].values[3] = 12.
    elif change == "depth":
        dataset.active_index.values[0] = 99.
    elif change == "new_depth_array":
        dataset.active_index.values = dataset.active_index.values.copy()
    elif change == "new_curve_array":
        dataset.curves["phi"].values = dataset.curves["phi"].values.copy()
    elif change == "metadata":
        curve = dataset.curves["rt"]
        curve.metadata = replace(curve.metadata, provenance="new lineage")
    elif change == "version":
        dataset.curves["rt"].version += 1
    elif change == "state":
        from geoworkbench.domain.models import CalculationState
        dataset.curves["phi"].state = CalculationState.STALE
    elif change == "active_index":
        dataset.active_index_id = "missing"
    elif change == "dataset":
        assert not seal.is_current(_dataset())
        return
    else:
        dataset.curves.pop("rt")
    assert not seal.is_current(dataset)


@pytest.mark.parametrize("change", (
    "row", "method", "reviewer", "wrong_phi", "wrong_rt", "mismatched_md",
    "mismatched_input", "bad_phi_unit",
))
def test_seal_rejects_untrusted_row_model_or_source(change):
    dataset = _dataset()
    profile = _evaluate(dataset)
    chosen_row = 0
    phi_key, rt_key = "phi", "rt"
    if change == "row":
        chosen_row = 100
    elif change == "method":
        profile = replace(profile, method_id="igr-linear-1")
    elif change == "reviewer":
        profile = replace(profile, reviewer="")
    elif change == "wrong_phi":
        phi_key = "rt"
    elif change == "wrong_rt":
        rt_key = "phi"
    elif change == "mismatched_md":
        first = replace(profile.rows[0], md_m=99.)
        profile = replace(profile, rows=(first, *profile.rows[1:]))
    elif change == "mismatched_input":
        first = profile.rows[0]
        assert first.estimate is not None
        altered = replace(
            first.estimate,
            parameters=tuple(
                (k, 0.9 if k == "porosity_fraction" else v)
                for k, v in first.estimate.parameters
            ),
        )
        profile = replace(profile, rows=(replace(first, estimate=altered), *profile.rows[1:]))
    else:
        curve = dataset.curves["phi"]
        curve.metadata = replace(curve.metadata, unit="%")
    with pytest.raises(ValueError):
        seal_archie_tablet_source(
            dataset, profile, porosity_curve_key=phi_key,
            resistivity_curve_key=rt_key, row_index=chosen_row,
        )


def test_sealed_source_never_creates_or_fills_missing_measured_rows():
    dataset = _dataset()
    profile = _evaluate(dataset)
    seal = seal_archie_tablet_source(
        dataset, profile, porosity_curve_key="phi",
        resistivity_curve_key="rt", row_index=1,
    )
    assert profile.rows[1].estimate is None
    assert np.isnan(dataset.curves["phi"].values[1])
    assert seal.is_current(dataset)


@pytest.mark.parametrize("change", (
    "missing_now_valid", "invalid_now_valid", "missing_marked_invalid",
    "forged_saturation", "forged_quality", "changed_coefficients",
    "skipped_row", "expanded_bounds",
))
def test_seal_rejects_stale_qc_or_forged_snapshot(change):
    """A seal must verify all row statuses and numerical Sw, not only selected MD."""
    dataset = _dataset()
    profile = _evaluate(dataset)
    if change == "missing_now_valid":
        dataset.curves["phi"].values[1] = 0.2
    elif change == "invalid_now_valid":
        dataset.curves["rt"].values[3] = 10.
    elif change == "missing_marked_invalid":
        profile = replace(
            profile,
            rows=(
                profile.rows[0],
                replace(profile.rows[1], status=profile.rows[3].status,
                        issue=profile.rows[3].issue),
                *profile.rows[2:],
            ),
        )
    elif change == "forged_saturation":
        first = profile.rows[0]
        assert first.estimate is not None
        profile = replace(
            profile,
            rows=(replace(first, estimate=replace(
                first.estimate, value=first.estimate.value * 1.1,
            )), *profile.rows[1:]),
        )
    elif change == "forged_quality":
        from geoworkbench.services.petrophysical_reference_models import PetrophysicalQuality
        first = profile.rows[0]
        assert first.estimate is not None
        profile = replace(
            profile,
            rows=(replace(first, estimate=replace(
                first.estimate, quality=PetrophysicalQuality.OUTSIDE_PHYSICAL_RANGE,
            )), *profile.rows[1:]),
        )
    elif change == "changed_coefficients":
        profile = replace(
            profile,
            coefficients=replace(profile.coefficients, saturation_exponent=2.5),
        )
    elif change == "skipped_row":
        profile = replace(profile, rows=(profile.rows[0], *profile.rows[2:]))
    else:
        profile = replace(profile, md_bounds=(99., 104.))
    with pytest.raises(ValueError):
        seal_archie_tablet_source(
            dataset, profile, porosity_curve_key="phi",
            resistivity_curve_key="rt", row_index=0,
        )



@pytest.mark.parametrize(("phi_unit", "rt_unit"), (
    ("v/v", "ohm.m"),
    ("vol/vol", "ohm-m"),
    ("cm3/cm3", "ом.м"),
))
def test_seal_matches_archie_calculation_unit_aliases_without_conversion(phi_unit, rt_unit):
    """Exact equivalent unit spellings must pass the same strict source gate."""
    from geoworkbench.services.semantic_channels import SemanticChannelDictionary

    dataset = _dataset()
    semantic = SemanticChannelDictionary()
    for key, unit in (("phi", phi_unit), ("rt", rt_unit)):
        curve = dataset.curves[key]
        curve.metadata = replace(
            curve.metadata, unit=unit,
            semantic=semantic.resolve(curve.metadata.original_mnemonic, unit=unit),
        )
    before = (
        dataset.active_index.values.copy(),
        dataset.curves["phi"].values.copy(),
        dataset.curves["rt"].values.copy(),
    )
    profile = _evaluate(dataset)
    seal = seal_archie_tablet_source(
        dataset, profile, porosity_curve_key="phi", resistivity_curve_key="rt",
        row_index=0,
    )
    assert seal.is_current(dataset)
    assert profile.rows[0].estimate is not None
    assert profile.rows[0].estimate.value == pytest.approx(0.5)
    np.testing.assert_array_equal(dataset.active_index.values, before[0])
    np.testing.assert_array_equal(dataset.curves["phi"].values, before[1])
    np.testing.assert_array_equal(dataset.curves["rt"].values, before[2])


@pytest.mark.parametrize(("phi_unit", "rt_unit"), (
    ("%", "ohm.m"),
    ("v/v", "kohm.m"),
    ("unitless", "ohm.m"),
))
def test_source_and_seal_do_not_treat_scaled_units_as_equivalent(phi_unit, rt_unit):
    """No automatic percent, kOhm-m or unrelated dimensionless reinterpretation."""
    from geoworkbench.services.semantic_channels import SemanticChannelDictionary

    dataset = _dataset()
    previously_calculated = _evaluate(dataset)
    semantic = SemanticChannelDictionary()
    for key, unit in (("phi", phi_unit), ("rt", rt_unit)):
        curve = dataset.curves[key]
        curve.metadata = replace(
            curve.metadata, unit=unit,
            semantic=semantic.resolve(curve.metadata.original_mnemonic, unit=unit),
        )
    with pytest.raises(ValueError):
        _evaluate(dataset)
    # Also reject a previously computed profile after the unit contract
    # changes; no post-hoc reinterpretation or unit scale adjustment.
    with pytest.raises(ValueError):
        seal_archie_tablet_source(
            dataset, previously_calculated, porosity_curve_key="phi",
            resistivity_curve_key="rt", row_index=0,
        )
