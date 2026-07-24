from pathlib import Path


def test_engineering_ruler_has_visible_caption_and_safe_pixel_fonts() -> None:
    source = Path("src/geoworkbench/tablet/tablet_view.py").read_text(encoding="utf-8")

    assert 'caption = f"{self._scale_caption}: {unit} · {mode}"' in source
    assert "caption_font.setPixelSize(8)" in source
    assert "value_font.setPixelSize(7)" in source
    assert "painter.setPen(QPen(color, 1.8))" in source
    assert "self.setMinimumHeight(24)" in source


def test_stale_plot_wrappers_are_skipped_during_navigation_and_cursor_updates() -> None:
    source = Path("src/geoworkbench/tablet/tablet_view.py").read_text(encoding="utf-8")

    assert "entry.plot is not None and _qt_object_is_alive(entry.plot)" in source
    assert "tablet.depth_range.stale_plot_skipped" in source
    assert "rendered.plot is None or not _qt_object_is_alive(rendered.plot)" in source
    assert "if not _qt_object_is_alive(watched):" in source
