from dataclasses import asdict

from geoworkbench.domain.models import StratigraphyInterval


def test_stratigraphy_text_defaults_preserve_old_projects() -> None:
    interval = StratigraphyInterval("id", 100.0, 110.0, "K1")
    assert interval.text_orientation == "horizontal"
    assert interval.text_position == "center"


def test_stratigraphy_text_fields_round_trip_through_mapping() -> None:
    source = StratigraphyInterval(
        "id",
        100.0,
        110.0,
        "K1",
        text_orientation="vertical_bottom_to_top",
        text_position="bottom",
    )
    restored = StratigraphyInterval(**asdict(source))
    assert restored == source
