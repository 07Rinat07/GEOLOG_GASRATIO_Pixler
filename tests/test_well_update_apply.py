from dataclasses import replace

import numpy as np
import pytest

from test_daily_las_growth import _add_curve, _dataset
from test_well_update_plan import review
from geoworkbench.domain.models import CalculationState
from geoworkbench.services.daily_las_growth import DailyLasGrowthError, dataset_append_state_sha256
from geoworkbench.services.well_update_apply import apply_well_numerical_update


def apply(target, source, plan, **kwargs):
    return apply_well_numerical_update(
        target, source, plan, source_name="daily.las", source_sha256="a" * 64, **kwargs,
    )


@pytest.mark.parametrize("descending", [False, True])
@pytest.mark.parametrize("append", [False, True])
def test_selected_cells_and_suffix_preserve_ids_source_and_unselected_history(descending, append):
    axis = [4, 3, 2, 1] if descending else [1, 2, 3, 4]
    target = _dataset("target", axis[:3], [np.nan, 2, 0])
    source = _dataset("source", axis, [0, 9, np.nan, 4])
    _add_curve(target, "LOCAL", [10, 20, 30], provenance="calculation:test")
    curve = target.curve_by_mnemonic("ROP")
    local = target.curve_by_mnemonic("LOCAL")
    before_source = dataset_append_state_sha256(source)
    plan = review(target, source)
    outcome = apply(target, source, plan, append_rows=append, selected_changes=(plan.changes[0],))
    np.testing.assert_equal(curve.values, [0, 2, 0, 4] if append else [0, 2, 0])
    np.testing.assert_equal(local.values, [10, 20, 30, np.nan] if append else [10, 20, 30])
    assert target.curve_by_mnemonic("ROP") is curve
    assert local.state is CalculationState.STALE
    assert outcome.record.changes == (plan.changes[0],)
    assert outcome.record.rows_added == int(append)
    assert target.numerical_update_history == [outcome.record]
    assert before_source == dataset_append_state_sha256(source)
    assert target.append_history == []


def test_exact_correction_and_reanalysis_repeat_are_noop():
    target = _dataset("t", [1, 2], [1, 2])
    source = _dataset("s", [1, 2], [8, 2])
    plan = review(target, source)
    record = apply(target, source, plan, selected_changes=plan.changes).record
    assert (record.changes[0].before, record.changes[0].after) == (1, 8)
    state = dataset_append_state_sha256(target)
    with pytest.raises(DailyLasGrowthError):
        apply(target, source, plan, selected_changes=plan.changes)
    fresh = review(target, source)
    assert apply(target, source, fresh, selected_changes=fresh.changes).record is None
    assert state == dataset_append_state_sha256(target)


@pytest.mark.parametrize("failure", ["hidden", "tampered", "duplicate", "stale", "allocation", "audit"])
def test_failure_never_leaves_partial_apply(monkeypatch, failure):
    import geoworkbench.services.well_update_apply as module
    target = _dataset("t", [1, 2], [1, 2])
    source = _dataset("s", [1, 2, 3], [8, 9, 3])
    full = review(target, source)
    plan = review(target, source, preview_limit=1)
    selection = (plan.changes[0],)
    if failure == "hidden":
        selection = (full.changes[1],)
    elif failure == "tampered":
        selection = (replace(plan.changes[0], after=88),)
    elif failure == "duplicate":
        selection *= 2
    elif failure == "stale":
        target.curve_by_mnemonic("ROP").values[-1] = 77
    else:
        def fail(*args, **kwargs):
            raise MemoryError("injected failure")
        monkeypatch.setattr(module.np if failure == "allocation" else module,
                            "concatenate" if failure == "allocation" else "NumericalUpdateRecord", fail)
    before = dataset_append_state_sha256(target)
    with pytest.raises((DailyLasGrowthError, MemoryError)):
        apply(target, source, plan, append_rows=True, selected_changes=selection)
    assert before == dataset_append_state_sha256(target)


def test_append_all_missing_rows_and_truncated_selected_diff():
    target = _dataset("t", [1, 2], [1, 2])
    source = _dataset("s", [1, 2, 3], [8, 9, np.nan])
    plan = review(target, source, preview_limit=1)
    assert plan.preview_truncated
    apply(target, source, plan, append_rows=True, selected_changes=plan.changes)
    np.testing.assert_equal(target.curve_by_mnemonic("ROP").values, [8, 2, np.nan])
    assert target.numerical_update_history[0].rows_added == 1
