import numpy as np
import pytest

from geoworkbench.calculations.gas_ratio import calculate_basic_ratios, safe_ratio
from geoworkbench.calculations.pixler import FormulaProfile, FormulaProfileRegistry
from geoworkbench.services.curve_editing import DrawPoint, interpolate_drawn_curve
from geoworkbench.services.cuttings import next_sample_interval
from geoworkbench.services.dependency_graph import DependencyGraph
from geoworkbench.tablet.depth_viewport import DepthViewport
from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind


def test_next_interval() -> None:
    assert next_sample_interval(1005.0, 5.0) == (1005.0, 1010.0)


def test_draw_interpolation() -> None:
    depth = np.array([0.0, 1.0, 2.0])
    result = interpolate_drawn_curve(depth, [DrawPoint(0, 10), DrawPoint(2, 20)])
    np.testing.assert_allclose(result, [10, 15, 20])


def test_dependency_graph() -> None:
    graph = DependencyGraph()
    graph.add_dependency("C1", "TG")
    graph.add_dependency("TG", "ANOMALY")
    assert graph.affected_outputs({"C1"}) == ["TG", "ANOMALY"]


def test_safe_ratio_handles_zero() -> None:
    result = safe_ratio(np.array([4.0, 2.0]), np.array([2.0, 0.0]))
    assert result[0] == 2.0
    assert np.isnan(result[1])


def test_basic_gas_ratios() -> None:
    results = calculate_basic_ratios(
        {
            "C1": np.array([10.0, 20.0]),
            "C2": np.array([2.0, 4.0]),
            "C3": np.array([1.0, 2.0]),
        }
    )
    np.testing.assert_allclose(results["C1_C2"].values, [5.0, 5.0])
    np.testing.assert_allclose(results["TG_CALC"].values, [13.0, 26.0])


def test_formula_profile_requires_source() -> None:
    registry = FormulaProfileRegistry()
    with pytest.raises(ValueError):
        registry.register(
            FormulaProfile("x", "X", "1", "", ("C1",), lambda inputs, params: inputs["C1"])
        )

def test_tablet_layout_can_move_tracks() -> None:
    layout = TabletLayout(
        [
            TrackDefinition("depth", "Глубина", TrackKind.DEPTH, width=100),
            TrackDefinition("gas", "Газ", TrackKind.GAS, ["C1"], width=250),
        ]
    )
    layout.move_track("gas", 0)
    assert [track.track_id for track in layout.tracks] == ["gas", "depth"]


def test_depth_viewport_zoom_and_pan_are_clamped() -> None:
    viewport = DepthViewport(0.0, 1000.0, 100.0, 200.0)
    viewport.zoom(2.0, 150.0)
    assert viewport.visible_top == pytest.approx(125.0)
    assert viewport.visible_bottom == pytest.approx(175.0)
    viewport.pan(-500.0)
    assert viewport.visible_top == pytest.approx(0.0)
    assert viewport.visible_bottom == pytest.approx(50.0)
