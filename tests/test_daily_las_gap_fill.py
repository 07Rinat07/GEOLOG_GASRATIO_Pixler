
import numpy as np
import pytest

from geoworkbench.services.daily_las_growth import (
    DailyLasGrowthError, analyze_daily_las_growth, apply_daily_las_growth,
)
from test_daily_las_growth import _dataset, _add_curve


def _plan(target, source, *, fill=True):
    return analyze_daily_las_growth(
        target, source, source_name="components.las", source_sha256="b" * 64,
        historical_policy="keep_existing", fill_missing_existing=fill,
    )


def test_fill_existing_depths_keeps_measurements_and_does_not_append_duplicate_rows():
    target = _dataset("target", [100, 101, 102], [10, np.nan, 12])
    source = _dataset("source", [100, 101, 102], [99, 11, 98])
    source_before = next(iter(source.curves.values())).values.copy()
    plan = _plan(target, source)
    assert plan.rows_added == 0 and plan.cells_filled == 1 and plan.changes_data
    apply_daily_las_growth(target, source, plan)
    np.testing.assert_array_equal(next(iter(target.curves.values())).values, [10, 11, 12])
    np.testing.assert_array_equal(next(iter(source.curves.values())).values, source_before)
    assert len(target.depth) == 3


def test_fill_can_add_depths_and_skip_incompatible_channels_explicitly():
    target = _dataset("target", [100, 101], [10, np.nan])
    source = _dataset("source", [100, 101, 102], [99, 11, 12])
    old = _add_curve(target, "CHEM", [1, 2], unit="g/cm3")
    _add_curve(source, "CHEM", [100, 200, 300], unit="ppm")
    with pytest.raises(DailyLasGrowthError, match="Единица"):
        _plan(target, source, fill=False)
    plan = _plan(target, source)
    assert plan.incompatible_curve_units == (("CHEM", "g/cm3", "ppm"),)
    assert plan.rows_added == 1 and plan.cells_filled == 1
    apply_daily_las_growth(target, source, plan)
    np.testing.assert_array_equal(next(iter(target.curves.values())).values, [10, 11, 12])
    np.testing.assert_array_equal(old.values[:2], [1, 2])
    assert np.isnan(old.values[-1])


def test_conflicting_duplicate_source_values_cannot_fill_one_empty_cell():
    target = _dataset("target", [100, 101], [10, np.nan])
    source = _dataset("source", [100, 101, 101], [10, 11, 12])
    with pytest.raises(DailyLasGrowthError, match="разные значения"):
        _plan(target, source)
    assert np.isnan(next(iter(target.curves.values())).values[-1])


def test_identical_duplicate_samples_count_one_fill_and_keep_measured_zero():
    target = _dataset("target", [100, 101], [0, np.nan])
    source = _dataset("source", [100, 101, 101], [10, 11, 11])
    plan = _plan(target, source)
    assert plan.cells_filled == 1
    apply_daily_las_growth(target, source, plan)
    np.testing.assert_array_equal(next(iter(target.curves.values())).values, [0, 11])


def test_fill_does_not_recompute_or_replace_local_derived_values():
    target = _dataset("target", [100, 101], [10, np.nan])
    source = _dataset("source", [100, 101], [10, 11])
    local = _add_curve(target, "TG_CALC", [1, np.nan], provenance="calculation:test")
    plan = _plan(target, source)
    apply_daily_las_growth(target, source, plan)
    assert np.isnan(local.values[-1])


def test_controller_fills_already_appended_depths_and_package_reopens_with_values(tmp_path):
    from pathlib import Path
    from geoworkbench.project.controller import ProjectController
    from test_daily_las_growth_dialog import _controller

    controller = _controller()
    target = controller.session.current_dataset
    assert target is not None
    fixture = Path(__file__).parent / "fixtures" / "las_sync" / "02_daily_append.las"
    # Prepare the same depth grid without receiving the component measurements.
    original = target.depth.copy()
    target.active_index.values = np.concatenate((original, [1002.5, 1003.0, 1003.5, 1004.0]))
    target.depth = target.active_index.values
    for curve in target.curves.values():
        curve.values = np.concatenate((curve.values, [np.nan] * 4))
    plan = controller.analyze(
        fixture, target.dataset_id, historical_policy="keep_existing", fill_missing_existing=True,
    )
    assert plan.rows_added == 0 and plan.cells_filled == 8
    controller.apply(plan)
    assert len(target.append_history) == 1
    package = tmp_path / "filled.geologpkg"
    ProjectController(session=controller.session).save_project(package)
    restored = ProjectController().open_project(package).current_dataset
    assert restored is not None and len(restored.depth) == len(target.depth)
    np.testing.assert_allclose(restored.curve_by_mnemonic("C1").values[-4:], [.6, .7, .8, .9])
