from geoworkbench.printing.auto_pagination import automatic_tablet_first_page_geometry
from geoworkbench.tablet.header_geometry import CURVE_HEADER_PRINT_ROW_HEIGHT


def test_seven_component_print_header_keeps_a_useful_graph_body() -> None:
    assert CURVE_HEADER_PRINT_ROW_HEIGHT <= 52
    header_height = 7 * CURVE_HEADER_PRINT_ROW_HEIGHT + 44
    geometry = automatic_tablet_first_page_geometry(
        canonical_content_height_px=2400,
        column_header_height_px=header_height,
        regular_units_per_page=120.0,
        regular_body_height_mm=175.0,
        first_body_height_mm=145.0,
    )
    assert geometry.units_per_page >= 65.0
    assert geometry.target_content_height_px > header_height + 1000
