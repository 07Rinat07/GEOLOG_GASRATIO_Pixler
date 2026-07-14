from geoworkbench.domain.models import LithologyInterval
from geoworkbench.project.lithotype_catalog_controller import CatalogLithotype
from geoworkbench.tablet.lithology_legend import build_lithology_legend


def test_legend_contains_used_lithotypes_once_in_depth_order() -> None:
    catalog = (
        CatalogLithotype(
            "sandstone", "SS", "Песчаник", "Sandstone", "rock", "#e7cf8b", "dots", True
        ),
        CatalogLithotype(
            "clay", "CL", "Глина", "Clay", "rock", "#888888", "clay_dash", True
        ),
    )
    intervals = [
        LithologyInterval("1", 10.0, 20.0, "sandstone", None),
        LithologyInterval("2", 20.0, 30.0, "clay", None),
        LithologyInterval("3", 30.0, 40.0, "sandstone", None),
    ]

    legend = build_lithology_legend(intervals, catalog)

    assert [item.code for item in legend] == ["SS", "CL"]


def test_legend_preserves_unknown_lithotype() -> None:
    legend = build_lithology_legend(
        [LithologyInterval("1", 10.0, 20.0, "legacy_rock", "Старая порода")], ()
    )

    assert legend[0].code == "legacy_rock"
    assert legend[0].name == "Старая порода"
    assert legend[0].color == "#b0b0b0"
