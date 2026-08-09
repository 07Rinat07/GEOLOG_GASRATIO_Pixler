from __future__ import annotations

import numpy as np

from geoworkbench.calculations.gas_ratio import calculate_basic_ratios
from geoworkbench.forms.a4_factory_templates import a4_factory_templates
from geoworkbench.forms.complex_gas import complex_gas_form
from geoworkbench.tablet.models import TrackKind, XScale


SEVEN_COMPONENTS = ("C1", "C2", "C3", "IC4", "NC4", "IC5", "NC5")


def _track(form, track_id: str):
    return next(
        track
        for column in form.columns
        for track in column.tracks
        if track.track_id == track_id
    )


def _assert_complete_layout(form, expected_depth_width: int) -> None:
    assert len(form.columns) == 14
    assert all(
        form.columns[index].tracks[0].kind is TrackKind.DEPTH
        and form.columns[index + 1].tracks[0].kind is TrackKind.CURVE
        for index in range(0, len(form.columns), 2)
    )
    depth_columns = form.columns[::2]
    assert len({column.column_id for column in depth_columns}) == 7
    assert len({column.tracks[0].track_id for column in depth_columns}) == 7
    assert all(column.width == expected_depth_width for column in depth_columns)
    assert all(column.tracks[0].show_interval_labels for column in depth_columns)


def _assert_a4_layout(
    form,
    expected_depth_width: int,
    expected_graph_widths: tuple[int, ...],
) -> None:
    _assert_complete_layout(form, expected_depth_width)
    depth_columns = form.columns[::2]
    graph_columns = form.columns[1::2]

    assert [column.visible for column in depth_columns] == [
        True,
        False,
        False,
        False,
        False,
        False,
        False,
    ]
    assert all(column.visible for column in graph_columns)
    assert tuple(column.width for column in graph_columns) == expected_graph_widths
    assert [column.tracks[0].kind for column in form.columns if column.visible] == [
        TrackKind.DEPTH,
        TrackKind.CURVE,
        TrackKind.CURVE,
        TrackKind.CURVE,
        TrackKind.CURVE,
        TrackKind.CURVE,
        TrackKind.CURVE,
        TrackKind.CURVE,
    ]


def test_complex_gas_builder_contains_all_requested_tracks() -> None:
    form = complex_gas_form("ru")
    assert form.name == "Интегрированный газовый каротаж C1–C5"
    _assert_complete_layout(form, 96)

    rop = _track(form, "track-column-complex-rop")
    assert tuple(binding.canonical_parameter_id for binding in rop.bindings) == ("ROP",)

    absolute = _track(form, "track-column-complex-absolute")
    assert tuple(binding.canonical_parameter_id for binding in absolute.bindings) == SEVEN_COMPONENTS
    assert all(binding.unit == "" for binding in absolute.bindings)

    relative = _track(form, "track-column-complex-relative")
    assert tuple(binding.canonical_parameter_id for binding in relative.bindings) == tuple(
        f"{component}_REL" for component in SEVEN_COMPONENTS
    )

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

    ratios = _track(form, "track-column-complex-ratios")
    assert tuple(binding.canonical_parameter_id for binding in ratios.bindings) == (
        "WETNESS",
        "BALANCE",
        "CHARACTER",
        "IC4_NC4",
        "IC5_NC5",
    )
    assert ratios.bindings[0].x_scale is XScale.LINEAR
    assert all(binding.x_scale is XScale.LOGARITHMIC for binding in ratios.bindings[1:])

    pixler = _track(form, "track-column-complex-pixler")
    assert tuple(binding.canonical_parameter_id for binding in pixler.bindings) == (
        "PIXLER_C1_C2",
        "PIXLER_C1_C3",
        "PIXLER_C1_C4",
        "PIXLER_C1_C5",
    )


def test_both_a4_complex_gas_forms_keep_all_graphs_with_one_shared_depth() -> None:
    forms = a4_factory_templates("ru")
    portrait = forms["factory-complex-gas-a4-portrait"]
    landscape = forms["factory-complex-gas-a4-landscape"]
    assert portrait.name == "Интегрированный газовый каротаж C1–C5 — A4 книжная"
    assert landscape.name == "Интегрированный газовый каротаж C1–C5 — A4 альбомная"
    _assert_a4_layout(portrait, 48, (80, 110, 80, 110, 100, 90, 86))
    _assert_a4_layout(landscape, 55, (100, 160, 110, 160, 150, 140, 130))


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
    np.testing.assert_allclose(results["PIXLER_C1_C4"].values, [80.0 / 3.0])
    np.testing.assert_allclose(results["PIXLER_C1_C5"].values, [40.0])
