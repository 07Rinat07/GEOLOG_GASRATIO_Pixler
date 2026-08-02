from __future__ import annotations

import numpy as np

from geoworkbench.calculations.gas_ratio import calculate_basic_ratios
from geoworkbench.forms.templates import curated_factory_templates, factory_templates
from geoworkbench.tablet.models import TrackKind, XScale


SEVEN_COMPONENTS = ("C1", "C2", "C3", "IC4", "NC4", "IC5", "NC5")


def _track(form, track_id: str):
    return next(
        track
        for column in form.columns
        for track in column.tracks
        if track.track_id == track_id
    )


def test_complex_gas_form_contains_all_requested_tracks_and_internal_depth_scales() -> None:
    templates = factory_templates("ru")
    form = templates["factory-complex-gas-analysis"]

    assert form.name == "Комплексная газовая форма"
    assert "factory-complex-gas-analysis" in curated_factory_templates("ru")
    assert len(form.columns) == 14

    depth_columns = [
        column
        for column in form.columns
        if column.tracks and all(track.kind is TrackKind.DEPTH for track in column.tracks)
    ]
    assert len(depth_columns) == 7
    assert len({column.column_id for column in depth_columns}) == 7
    assert len({column.tracks[0].track_id for column in depth_columns}) == 7
    assert all(column.width == 48 for column in depth_columns)
    assert all(column.tracks[0].show_interval_labels for column in depth_columns)

    absolute = _track(form, "track-column-complex-absolute")
    assert tuple(binding.canonical_parameter_id for binding in absolute.bindings) == SEVEN_COMPONENTS
    assert all(binding.unit == "% abs" for binding in absolute.bindings)
    assert all((binding.x_min, binding.x_max) == (0.0, 100.0) for binding in absolute.bindings)

    relative = _track(form, "track-column-complex-relative")
    assert tuple(binding.canonical_parameter_id for binding in relative.bindings) == tuple(
        f"{component}_REL" for component in SEVEN_COMPONENTS
    )
    assert all(binding.unit == "% of ΣC1–C5" for binding in relative.bindings)
    assert all((binding.x_min, binding.x_max) == (0.0, 100.0) for binding in relative.bindings)

    normalized = _track(form, "track-column-complex-normalized-components")
    assert tuple(binding.canonical_parameter_id for binding in normalized.bindings) == (
        "C1_NORM_REF",
        "C2_NORM",
        "C3_NORM",
        "IC4_NORM",
        "NC4_NORM",
        "IC5_NORM",
        "NC5_NORM",
    )
    assert all(binding.unit == "normalized gas units" for binding in normalized.bindings)
    assert all(binding.x_min is None and binding.x_max is None for binding in normalized.bindings)

    ratio = _track(form, "track-column-complex-ratios")
    assert tuple(binding.canonical_parameter_id for binding in ratio.bindings) == (
        "WETNESS",
        "BALANCE",
        "CHARACTER",
        "IC4_NC4",
        "IC5_NC5",
    )
    assert ratio.bindings[0].x_scale is XScale.LINEAR
    assert all(binding.x_scale is XScale.LOGARITHMIC for binding in ratio.bindings[1:])

    pixler = _track(form, "track-column-complex-pixler")
    assert tuple(binding.canonical_parameter_id for binding in pixler.bindings) == (
        "PIXLER_C1_C2",
        "PIXLER_C1_C3",
        "PIXLER_C1_C4",
        "PIXLER_C1_C5",
    )
    assert all(binding.x_scale is XScale.LOGARITHMIC for binding in pixler.bindings)
    assert all((binding.x_min, binding.x_max) == (0.1, 1000.0) for binding in pixler.bindings)

    all_bindings = [
        binding
        for column in form.columns
        for track in column.tracks
        for binding in track.bindings
    ]
    assert all(binding.header_text_color == binding.style.color for binding in all_bindings)
    assert all(binding.header_line_color == binding.style.color for binding in all_bindings)


def test_seven_component_calculation_does_not_double_count_aggregate_c4_c5() -> None:
    results = calculate_basic_ratios(
        {
            "C1": np.array([80.0]),
            "C2": np.array([10.0]),
            "C3": np.array([5.0]),
            "IC4": np.array([1.0]),
            "NC4": np.array([2.0]),
            "IC5": np.array([1.0]),
            "NC5": np.array([1.0]),
            # Deliberately inconsistent aggregate channels must not be counted
            # when complete split isomer pairs are available.
            "C4": np.array([999.0]),
            "C5": np.array([999.0]),
        }
    )

    np.testing.assert_allclose(results["TG_CALC"].values, [100.0])
    relative_sum = sum(results[f"{component}_REL"].values for component in SEVEN_COMPONENTS)
    np.testing.assert_allclose(relative_sum, [100.0])
    np.testing.assert_allclose(results["C4_REL"].values, [3.0])
    np.testing.assert_allclose(results["C5_REL"].values, [2.0])

    np.testing.assert_allclose(results["WETNESS"].values, [20.0])
    np.testing.assert_allclose(results["BALANCE"].values, [9.0])
    np.testing.assert_allclose(results["CHARACTER"].values, [1.0])
    np.testing.assert_allclose(results["WH"].values, results["WETNESS"].values)
    np.testing.assert_allclose(results["BH"].values, results["BALANCE"].values)
    np.testing.assert_allclose(results["CH"].values, results["CHARACTER"].values)

    np.testing.assert_allclose(results["IC4_NC4"].values, [0.5])
    np.testing.assert_allclose(results["IC5_NC5"].values, [1.0])
    np.testing.assert_allclose(results["PIXLER_C1_C2"].values, [8.0])
    np.testing.assert_allclose(results["PIXLER_C1_C3"].values, [16.0])
    np.testing.assert_allclose(results["PIXLER_C1_C4"].values, [80.0 / 3.0])
    np.testing.assert_allclose(results["PIXLER_C1_C5"].values, [40.0])


def test_aggregate_c4_c5_remain_supported_as_fallback() -> None:
    results = calculate_basic_ratios(
        {
            "C1": np.array([80.0]),
            "C2": np.array([10.0]),
            "C3": np.array([5.0]),
            "C4": np.array([3.0]),
            "C5": np.array([2.0]),
        }
    )

    np.testing.assert_allclose(results["TG_CALC"].values, [100.0])
    np.testing.assert_allclose(results["C4_REL"].values, [3.0])
    np.testing.assert_allclose(results["C5_REL"].values, [2.0])
    np.testing.assert_allclose(results["PIXLER_C1_C4"].values, [80.0 / 3.0])
    np.testing.assert_allclose(results["PIXLER_C1_C5"].values, [40.0])
