from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_dense_curve_headers_use_row_aligned_scroll_geometry() -> None:
    source = (ROOT / "src/geoworkbench/tablet/tablet_view.py").read_text(
        encoding="utf-8"
    )
    assert "curve_header_content_height(" in source
    assert "curve_header_viewport_height(" in source
    assert "align_curve_header_band_height(" in source
    assert "self.curve_header.setFixedHeight(content_height)" in source
    assert "verticalScrollBar().setSingleStep(CURVE_HEADER_EDITOR_HEIGHT)" in source
    assert "min(360, content_height)" not in source


def test_interactive_curves_use_restrained_screen_profile() -> None:
    tablet = (ROOT / "src/geoworkbench/tablet/tablet_view.py").read_text(
        encoding="utf-8"
    )
    grid = (ROOT / "src/geoworkbench/tablet/grid_renderer.py").read_text(
        encoding="utf-8"
    )
    assert "muted_screen_curve_color" in tablet
    assert "screen_curve_width" in tablet
    assert "professional_curve_color" in tablet
    assert "pg.intColor(" not in tablet
    assert "minor_grid_is_readable" in grid
    assert "screen_grid_alpha" in grid
