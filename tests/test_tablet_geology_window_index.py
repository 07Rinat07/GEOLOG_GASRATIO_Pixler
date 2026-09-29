from geoworkbench.domain.models import CuttingsSample, LithologyInterval, StratigraphyInterval
from geoworkbench.tablet.tablet_view import TabletView


def test_tablet_geology_indexes_limit_prefetched_window(qapp) -> None:
    view = TabletView()
    view.set_cuttings(
        [
            CuttingsSample("cut-above", 0.0, 10.0),
            CuttingsSample("cut-visible", 95.0, 105.0, calcite_percent=25.0),
            CuttingsSample("cut-below", 200.0, 210.0),
        ],
        refresh=False,
    )
    view.set_lithology(
        [
            LithologyInterval("lith-above", 0.0, 10.0, "sandstone"),
            LithologyInterval("lith-visible", 90.0, 110.0, "limestone"),
            LithologyInterval("lith-below", 200.0, 210.0, "clay"),
        ],
        (),
        refresh=False,
    )
    view.set_stratigraphy(
        [
            StratigraphyInterval("strat-above", 0.0, 10.0, "J"),
            StratigraphyInterval("strat-visible", 80.0, 120.0, "K"),
            StratigraphyInterval("strat-below", 200.0, 210.0, "Pg"),
        ],
        refresh=False,
    )
    view._geology_window = (90.0, 120.0)

    assert [item.sample_id for item in view._loaded_cuttings()] == ["cut-visible"]
    assert [item.interval_id for item in view._loaded_lithology()] == ["lith-visible"]
    assert [item.interval_id for item in view._loaded_stratigraphy()] == ["strat-visible"]
    assert view._calcimetry_presence == (True, False, False)
    view.close()


def test_tablet_geology_indexes_rebuild_when_saved_data_changes(qapp) -> None:
    view = TabletView()
    view._geology_window = (90.0, 120.0)
    view.set_cuttings([CuttingsSample("old", 95.0, 105.0)], refresh=False)

    assert [item.sample_id for item in view._loaded_cuttings()] == ["old"]

    view.set_cuttings(
        [
            CuttingsSample("outside", 0.0, 10.0),
            CuttingsSample("updated", 100.0, 110.0, dolomite_percent=15.0),
        ],
        refresh=False,
    )

    assert [item.sample_id for item in view._loaded_cuttings()] == ["updated"]
    assert view._calcimetry_presence == (False, True, False)
    view.close()


def test_indexed_geology_hit_tests_preserve_deeper_shared_boundary(qapp) -> None:
    view = TabletView()
    view.set_cuttings(
        [
            CuttingsSample("cut-upper", 0.0, 10.0),
            CuttingsSample("cut-lower", 10.0, 20.0),
        ],
        refresh=False,
    )
    view.set_lithology(
        [
            LithologyInterval("lith-upper", 0.0, 10.0, "sandstone"),
            LithologyInterval("lith-lower", 10.0, 20.0, "clay"),
        ],
        (),
        refresh=False,
    )
    view.set_stratigraphy(
        [
            StratigraphyInterval("strat-upper", 0.0, 10.0, "K1"),
            StratigraphyInterval("strat-lower", 10.0, 20.0, "K2"),
        ],
        refresh=False,
    )

    assert view.cuttings_sample_at_depth(10.0).sample_id == "cut-lower"
    assert view.lithology_interval_at_depth(10.0).interval_id == "lith-lower"
    assert view.stratigraphy_interval_at_depth(10.0).interval_id == "strat-lower"
    view.close()
