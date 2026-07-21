from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_interval_editor_exposes_direction_and_position() -> None:
    source = _source("src/geoworkbench/ui/stratigraphy_dialog.py")
    assert "text_orientation_input" in source
    assert "text_position_input" in source
    assert "vertical_bottom_to_top" in source
    assert "Ближе к кровле" in source
    assert "По центру интервала" in source
    assert "Ближе к подошве" in source


def test_screen_and_print_renderers_use_same_presentation_helpers() -> None:
    tablet = _source("src/geoworkbench/tablet/tablet_view.py")
    print_renderer = _source("src/geoworkbench/printing/masterlog_renderer.py")
    for helper in ("stratigraphy_text_angle", "stratigraphy_text_position_fraction"):
        assert helper in tablet
        assert helper in print_renderer


def test_reediting_restores_saved_presentation() -> None:
    source = _source("src/geoworkbench/ui/main_window.py")
    assert "dialog.set_text_presentation(" in source
    assert "interval.text_orientation" in source
    assert "interval.text_position" in source
