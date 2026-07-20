import numpy as np

from geoworkbench.domain.models import CurveData, CurveMetadata, Dataset, DatasetKind, DepthDomain
from geoworkbench.project.las_range_editor import LasRangeEditingController
from geoworkbench.project.session import ProjectSession


def make_editor() -> tuple[LasRangeEditingController, Dataset]:
    dataset = Dataset(
        "dataset",
        "LAS",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.arange(100.0, 106.0),
    )
    for mnemonic, values in (
        ("C1", [10, 10, 10, 10, 10, 10]),
        ("C2", [2, 2, 2, 2, 2, 2]),
        ("C3", [1, 1, 1, 1, 1, 1]),
    ):
        curve_id = mnemonic.lower()
        dataset.curves[curve_id] = CurveData(
            CurveMetadata(curve_id, mnemonic, mnemonic, "%", None, dataset.dataset_id),
            np.asarray(values, dtype=np.float64),
        )
    session = ProjectSession()
    session.add_dataset(dataset)
    session.calculate_basic_gas_ratios()
    session.dirty = False
    return LasRangeEditingController(session), dataset


def test_constant_range_edit_recalculates_gas_outputs_and_undo() -> None:
    editor, dataset = make_editor()

    editor.set_constant(["c1"], 101.0, 103.0, 20.0)

    np.testing.assert_allclose(dataset.curves["c1"].values, [10, 20, 20, 20, 10, 10])
    total = dataset.curve_by_mnemonic("TG_CALC")
    ratio = dataset.curve_by_mnemonic("C1_C2")
    assert total is not None and ratio is not None
    np.testing.assert_allclose(total.values, [13, 23, 23, 23, 13, 13])
    np.testing.assert_allclose(ratio.values, [5, 10, 10, 10, 5, 5])

    editor.undo()

    np.testing.assert_allclose(dataset.curves["c1"].values, [10, 10, 10, 10, 10, 10])
    np.testing.assert_allclose(total.values, [13, 13, 13, 13, 13, 13])


def test_uniform_noise_is_bounded_and_reproducible_after_undo_redo() -> None:
    editor, dataset = make_editor()

    editor.fill_uniform_noise(["c2"], 100.0, 105.0, 0.5, 5.0, seed=42)
    generated = dataset.curves["c2"].values.copy()

    assert np.all((generated >= 0.5) & (generated <= 5.0))
    editor.undo()
    editor.redo()
    np.testing.assert_allclose(dataset.curves["c2"].values, generated)


def test_copy_and_paste_interval_updates_all_selected_curves() -> None:
    editor, dataset = make_editor()
    dataset.curves["c1"].values[:] = [1, 2, 3, 4, 5, 6]
    dataset.curves["c2"].values[:] = [10, 20, 30, 40, 50, 60]
    clipboard = editor.copy(["c1", "c2"], 100.0, 101.0)

    editor.paste(clipboard, 103.0)

    np.testing.assert_allclose(dataset.curves["c1"].values, [1, 2, 3, 1, 2, 6])
    np.testing.assert_allclose(dataset.curves["c2"].values, [10, 20, 30, 10, 20, 60])


def test_set_missing_and_interpolate_use_depth_and_support_undo() -> None:
    editor, dataset = make_editor()
    dataset.depth[:] = [100.0, 100.5, 102.0, 103.0, 104.0, 105.0]
    dataset.curves["c1"].values[:] = [10.0, 0.0, 0.0, 40.0, 50.0, 60.0]

    editor.set_missing(["c1"], 100.5, 102.0)
    assert np.isnan(dataset.curves["c1"].values[1:3]).all()

    editor.interpolate_missing(["c1"], 100.5, 102.0)
    np.testing.assert_allclose(dataset.curves["c1"].values, [10, 15, 30, 40, 50, 60])
    editor.undo()
    assert np.isnan(dataset.curves["c1"].values[1:3]).all()
    editor.undo()
    np.testing.assert_allclose(dataset.curves["c1"].values, [10, 0, 0, 40, 50, 60])


def test_interpolation_does_not_extrapolate_edge_gaps() -> None:
    editor, dataset = make_editor()
    dataset.curves["c1"].values[:] = [np.nan, 10, 20, 30, 40, 50]

    with np.testing.assert_raises_regex(ValueError, "ограниченных с двух сторон"):
        editor.interpolate_missing(["c1"], 100.0, 100.0)


def test_interpolation_groups_different_curve_gaps_in_one_undo_command() -> None:
    editor, dataset = make_editor()
    dataset.curves["c1"].values[:] = [10, np.nan, 30, 40, 50, 60]
    dataset.curves["c2"].values[:] = [2, 4, np.nan, 8, 10, 12]

    editor.interpolate_missing(["c1", "c2"], 101.0, 102.0)

    np.testing.assert_allclose(dataset.curves["c1"].values, [10, 20, 30, 40, 50, 60])
    np.testing.assert_allclose(dataset.curves["c2"].values, [2, 4, 6, 8, 10, 12])
    editor.undo()
    assert np.isnan(dataset.curves["c1"].values[1])
    assert np.isnan(dataset.curves["c2"].values[2])


def test_shift_and_multiply_ranges_preserve_missing_values_and_support_undo() -> None:
    editor, dataset = make_editor()
    dataset.curves["c1"].values[:] = [1, np.nan, 3, 4, 5, 6]

    editor.add_constant(["c1"], 100.0, 102.0, 2.0)
    np.testing.assert_allclose(dataset.curves["c1"].values, [3, np.nan, 5, 4, 5, 6], equal_nan=True)
    editor.multiply(["c1"], 101.0, 103.0, 10.0)
    np.testing.assert_allclose(
        dataset.curves["c1"].values, [3, np.nan, 50, 40, 5, 6], equal_nan=True
    )
    editor.undo()
    np.testing.assert_allclose(dataset.curves["c1"].values, [3, np.nan, 5, 4, 5, 6], equal_nan=True)


def test_moving_average_uses_selected_interval_and_keeps_gaps() -> None:
    editor, dataset = make_editor()
    dataset.curves["c1"].values[:] = [1, 2, np.nan, 8, 10, 12]

    editor.smooth_moving_average(["c1"], 100.0, 104.0, 3)

    np.testing.assert_allclose(
        dataset.curves["c1"].values,
        [1.5, 1.5, np.nan, 9.0, 9.0, 12.0],
        equal_nan=True,
    )


def test_moving_average_validates_window() -> None:
    editor, _ = make_editor()
    with np.testing.assert_raises_regex(ValueError, "нечётным"):
        editor.smooth_moving_average(["c1"], 100.0, 105.0, 4)
