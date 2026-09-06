from dataclasses import FrozenInstanceError, replace

import numpy as np
import pytest

from test_daily_las_growth import _add_curve, _dataset
from geoworkbench.domain.models import DepthDomain
from geoworkbench.services.daily_las_growth import (
    DailyLasGrowthError, dataset_append_state_sha256,
)
from geoworkbench.services.well_update_plan import (
    NumericalUpdateKind, analyze_well_numerical_update,
)


def review(target, source, **kwargs):
    return analyze_well_numerical_update(
        target, source, source_name="daily.las", source_sha256="a" * 64, **kwargs,
    )


@pytest.mark.parametrize("descending", [False, True])
def test_review_classifies_three_operations_without_mutation(descending):
    axis = [4, 3, 2, 1] if descending else [1, 2, 3, 4]
    target = _dataset("target", axis[:3], [np.nan, 2, 0])
    source = _dataset("source", axis, [0, 3, np.nan, 4])
    _add_curve(target, "LOCAL", [99, 98, 97], provenance="calculation:test")
    before = [dataset_append_state_sha256(ds) for ds in (target, source)]
    plan = review(target, source)
    assert (plan.rows_added, plan.cells_added, plan.gaps_filled, plan.corrections) == (1, 1, 1, 1)
    assert plan.source_missing == 1
    assert [c.kind for c in plan.changes] == [
        NumericalUpdateKind.FILL, NumericalUpdateKind.CORRECT, NumericalUpdateKind.APPEND,
    ]
    assert plan.changes[0].after == 0
    assert (plan.changes[1].before, plan.changes[1].after) == (2, 3)
    assert plan.changes[-1].target_row is None
    assert before == [dataset_append_state_sha256(ds) for ds in (target, source)]
    assert plan == review(target, source)
    with pytest.raises(FrozenInstanceError):
        plan.rows_added = 5


def test_full_counts_survive_truncated_preview_and_equal_input_is_noop():
    target = _dataset("target", [1, 2, 3], [1, 2, 3])
    source = _dataset("source", [1, 2, 3], [4, 5, 6])
    plan = review(target, source, preview_limit=1)
    assert plan.corrections == 3 and len(plan.changes) == 1 and plan.preview_truncated
    assert review(target, source, preview_limit=0).corrections == 3
    source.curve_by_mnemonic("ROP").values[:] = [1, 2, 3]
    plan = review(target, source)
    assert plan.cells_unchanged == 3 and not plan.changes and not plan.preview_truncated


@pytest.mark.parametrize("failure", ["unit", "domain", "well", "duplicate", "inside", "inf"])
def test_incompatible_inputs_fail_without_mutation(failure):
    target = _dataset("target", [1, 2, 3], [1, 2, 3])
    source = _dataset("source", [1, 2, 3], [1, 2, 3])
    if failure == "unit":
        curve = source.curve_by_mnemonic("ROP")
        curve.metadata = replace(curve.metadata, unit="ft/h")
    elif failure == "domain":
        source.depth_domain = DepthDomain.TVD
    elif failure == "well":
        source.headers["WELL"] = "different"
    elif failure == "duplicate":
        source.active_index.values[:] = [1, 1, 3]
    elif failure == "inside":
        source.active_index.values[:] = [1, 1.5, 3]
    else:
        source.curve_by_mnemonic("ROP").values[0] = np.inf
    before = dataset_append_state_sha256(target)
    with pytest.raises(DailyLasGrowthError):
        review(target, source)
    assert dataset_append_state_sha256(target) == before


@pytest.mark.parametrize("limit", [-1, 10_001, True, 1.5])
def test_preview_limit_is_validated(limit):
    with pytest.raises(DailyLasGrowthError):
        review(_dataset("t", [1, 2], [1, 2]), _dataset("s", [1, 2], [1, 2]),
               preview_limit=limit)


def test_preview_fingerprint_changes_for_nonoverlapping_edit():
    target = _dataset("target", [1, 2, 3], [1, 2, 3])
    source = _dataset("source", [3, 4], [3, 4])
    first = review(target, source)
    target.curve_by_mnemonic("ROP").values[0] = 99
    second = review(target, source)
    assert first.changes == second.changes
    assert first.target_state_sha256 != second.target_state_sha256
