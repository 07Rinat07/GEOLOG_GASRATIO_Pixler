from __future__ import annotations

import numpy as np

from geoworkbench.calculations.gas_ratio import calculate_basic_ratios
from geoworkbench.forms.a4_factory_templates import a4_factory_templates
from geoworkbench.forms.complex_gas import complex_gas_form
from geoworkbench.printing.form_width_advisor import FormWidthLevel, audit_form_width
from geoworkbench.tablet.models import TrackKind, XScale

SEVEN_COMPONENTS = ("C1", "C2", "C3", "IC4", "NC4", "IC5", "NC5")


def _track(form, track_id: str):
    return next(
        track
        for column in form.columns
        for track in column.tracks
        if track.track_id == track_id
    )


def _assert_layout(form, depth_width: int) -> None:
    assert len(form.columns) == 10
    assert all(
        form.columns[index].tracks[0].kind is TrackKind.DEPTH
        and form.columns[index + 1].tracks[0].kind is TrackKind.CURVE
        for index in range(0, len(form.columns), 2)
    )
    depth_columns = form.columns[::2]
    assert len({column.column_id for column in depth_columns}) == 5
    assert len({column.tracks[0].track_id for column in depth_columns}) == 5
    assert all(column.width == depth_width for column in depth_columns)
    assert all(column.tracks[0].show_interval_labels for column in depth_columns)


def test_builder_contains_every_requested_curve() -> None:
    form = complex_gas_form("ru")
    _assert_layout(form, 96)

    absolute = _track(form, "track-column-complex-absolute")
    assert tuple(binding.canonical_parameter_id for binding in absolute.bindings) == (
        "TG_CALC",
        *SEVEN_COMPONENTS,
    )
    assert all(binding.unit == "%" for binding in absolute.bindings)

    normalized = _track(form, "track-column-complex-normalized-components")
    assert tuple(binding.canonical_parameter_id for binding in normalized.bindings) == (
        "TG_NORM",
        "C1_NORM_REF",
        "C2_NORM",
        "C3_NORM",
        "IC4_NORM",
        "NC4_NORM",
        "IC5_NORM",
        "NC5_NORM",
    )
    assert all(binding.unit == "norm" for binding in normalized.bindings)

    relative = _track(form, "track-column-complex-relative")
    assert tuple(binding.canonical_parameter_id for binding in relative.bindings) == tuple(
        f"{component}_REL" for component in SEVEN_COMPONENTS
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
    assert all(binding.x_scale is XScale.LOGARITHMIC for binding in pixler.bindings)

    bindings = [
        binding
        for column in form.columns
        for track in column.tracks
        for binding in track.bindings
    ]
    assert all(binding.header_text_color == binding.style.color for binding in bindings)
    assert all(binding.header_line_color == binding.style.color for binding in bindings)


def test_both_a4_variants_fit_and_have_internal_depth_scales() -> None:
    forms = a4_factory_templates("ru")
    portrait = forms["factory-complex-gas-a4-portrait"]
    landscape = forms["factory-complex-gas-a4-landscape"]
    _assert_layout(portrait, 48)
    _assert_layout(landscape, 55)

    portrait_audit = audit_form_width(column.width for column in portrait.columns)
    landscape_audit = audit_form_width(column.width for column in landscape.columns)
    assert portrait_audit.level is FormWidthLevel.FITS_PORTRAIT
    assert landscape_audit.level is FormWidthLevel.FITS_LANDSCAPE


def test_split_isomers_take_priority_over_aggregate_c4_c5() -> None:
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
    relative_sum = sum(results[f"{name}_REL"].values for name in SEVEN_COMPONENTS)
    np.testing.assert_allclose(relative_sum, [100.0])
    np.testing.assert_allclose(results["WETNESS"].values, [20.0])
    np.testing.assert_allclose(results["BALANCE"].values, [9.0])
    np.testing.assert_allclose(results["CHARACTER"].values, [1.0])
    np.testing.assert_allclose(results["IC4_NC4"].values, [0.5])
    np.testing.assert_allclose(results["IC5_NC5"].values, [1.0])
    np.testing.assert_allclose(results["PIXLER_C1_C2"].values, [8.0])
    np.testing.assert_allclose(results["PIXLER_C1_C3"].values, [16.0])
    np.testing.assert_allclose(results["PIXLER_C1_C4"].values, [80.0 / 3.0])
    np.testing.assert_allclose(results["PIXLER_C1_C5"].values, [40.0])


def test_aggregate_c4_c5_are_supported_as_fallback() -> None:
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
